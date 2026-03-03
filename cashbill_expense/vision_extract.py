"""
Extract data from cash bill / receipt using GCP Vision API + GPT-4o-mini.

Pipeline:
  1. GCP Vision OCR → raw text
  2. Regex parser → structured fields (baseline)
  3. GPT-4o-mini LLM extraction (multimodal for images, text-only for PDFs)
  4. LLM-primary merge (LLM is authoritative, parser fills gaps)
  5. Clean units, infer missing amounts
"""

import os
import uuid
from pathlib import Path

DEFAULT_GCS_BUCKET = "data-pdf-extractor"
GCS_INPUT_PREFIX = f"gs://{DEFAULT_GCS_BUCKET}/cashbill-expense/input/"
GCS_OUTPUT_PREFIX = f"gs://{DEFAULT_GCS_BUCKET}/cashbill-expense/processed/"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def _ocr_pdf_via_vision(file_path: str, filename: str) -> str:
    """Use existing vision_gcp.vision_ocr_pdf for PDF."""
    from vision_gcp import vision_ocr_pdf
    from gcs_utils import upload_file_to_gcs

    gcs_input_uri = f"{GCS_INPUT_PREFIX.rstrip('/')}/{filename}"
    upload_file_to_gcs(file_path, gcs_input_uri, None)
    doc_id = Path(file_path).stem or str(uuid.uuid4())[:8]
    gcs_output_uri = f"{GCS_OUTPUT_PREFIX.rstrip('/')}/{doc_id}/"
    text = vision_ocr_pdf(
        gcs_input_uri,
        gcs_output_uri,
        gcs_input_path=GCS_INPUT_PREFIX,
        service_account_file=None,
    )
    return text or ""


def _ocr_image_via_vision(file_path: str) -> str:
    """Use Vision API document_text_detection for a single image (PNG/JPEG)."""
    from google.cloud import vision_v1 as vision

    with open(file_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    credentials = _get_vision_credentials()
    client = vision.ImageAnnotatorClient(credentials=credentials)
    response = client.document_text_detection(image=image)
    if response.error.message:
        raise RuntimeError(response.error.message)
    if response.full_text_annotation:
        return response.full_text_annotation.text or ""
    return ""


def _get_vision_credentials():
    """GCP credentials from env."""
    import json
    from google.oauth2 import service_account

    credentials_json = os.getenv("GCP_CREDENTIALS_JSON")
    if not credentials_json or not credentials_json.strip():
        raise ValueError("GCP_CREDENTIALS_JSON environment variable is required for Cash bill to Expense.")
    sa_info = json.loads(credentials_json)
    return service_account.Credentials.from_service_account_info(sa_info)


def _is_image_file(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in IMAGE_EXTENSIONS


def extract_text_from_file(file_path: str, filename: str) -> str:
    """Extract text from a cash bill/receipt file using GCP Vision API."""
    ext = (Path(filename or file_path).suffix or "").lower()
    if ext == ".pdf":
        return _ocr_pdf_via_vision(file_path, filename or Path(file_path).name)
    if ext in IMAGE_EXTENSIONS:
        return _ocr_image_via_vision(file_path)
    if "pdf" in (filename or ""):
        return _ocr_pdf_via_vision(file_path, filename or Path(file_path).name)
    return _ocr_image_via_vision(file_path)


def _merge_llm_into_record(record: dict, llm_data: dict) -> dict:
    """
    LLM-primary merge: use LLM result as the authoritative source,
    only backfill empty/missing fields from the regex parser.
    This matches the Streamlit test flow where LLM output is used directly.
    """
    if not llm_data:
        return record

    SKIP_KEYS = {"raw_text", "description", "document_name"}

    merged = {}

    for k, v in llm_data.items():
        if k.startswith("_"):
            continue
        merged[k] = v

    for k, v in record.items():
        if k in SKIP_KEYS:
            merged[k] = v
            continue
        if k.startswith("_"):
            continue

        existing = merged.get(k)
        is_empty = existing is None or existing == "" or existing == [] or existing == 0 or existing == 0.0
        if is_empty and v is not None and v != "" and v != []:
            merged[k] = v

    return merged


def extract_expense_from_file(file_path: str, document_name: str = "") -> dict:
    """
    Full extraction pipeline:
      1. GCP Vision OCR → raw text
      2. Regex parser → baseline structured fields
      3. GPT-4o-mini LLM extraction (multimodal for images, text-only for PDFs)
      4. LLM-primary merge, clean, infer
    """
    from cashbill_expense.expense_parser import (
        parse_expense_from_text, _clean_unit_field, _infer_missing_line_item_amounts
    )

    name = document_name or Path(file_path).name
    raw_text = extract_text_from_file(file_path, name)
    record = parse_expense_from_text(raw_text, document_name=name)
    record["raw_text"] = (raw_text or "")[:15000]
    record["description"] = (raw_text or "")[:2000]

    is_image = _is_image_file(file_path)
    llm_data = None
    extraction_model = "regex-only"

    # GPT-4o-mini LLM extraction
    if is_image:
        try:
            from cashbill_expense.llm_extract import extract_expense_with_vision_llm
            llm_data = extract_expense_with_vision_llm(file_path, raw_text)
        except Exception as e:
            print(f"[EXPENSE] Vision LLM failed: {e}")
    else:
        try:
            from cashbill_expense.llm_extract import extract_expense_with_llm
            llm_data = extract_expense_with_llm(raw_text)
        except Exception as e:
            print(f"[EXPENSE] Text LLM failed: {e}")

    if llm_data:
        extraction_model = llm_data.pop("_extraction_model", "LLM")

    # LLM-primary merge: LLM result is authoritative, parser fills gaps
    record = _merge_llm_into_record(record, llm_data)

    # Clean unit fields and infer missing amounts
    for it in record.get("line_items") or []:
        if it.get("unit"):
            it["unit"] = _clean_unit_field(it["unit"])
    _infer_missing_line_item_amounts(record)

    return record
