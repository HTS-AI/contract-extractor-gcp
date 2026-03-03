"""
Professional document intelligence extraction for cash bills / receipts / invoices.

Uses GPT-4o-mini exclusively — fast, cost-effective, supports multimodal (image + text)
and text-only modes.
"""

import os
import json
import re
import base64
from typing import Dict, Any, Optional
from pathlib import Path

VISION_SYSTEM_PROMPT = """You are a professional invoice/receipt document intelligence system with computer vision.

You are given:
1. The actual IMAGE of the document (you can see it)
2. Raw OCR text extracted from the image (may have errors)

You can SEE the document. Use your vision to:
- Read handwritten text directly from the image
- Verify numbers against what you see in the image
- Understand table structure from visual column alignment
- Read amounts from R.O. and Bz. columns correctly
- Detect stamps, signatures, and ignore decorative elements

Your task is to extract accurate data using BOTH your vision AND the OCR text."""

TEXT_SYSTEM_PROMPT = """You are a professional invoice document intelligence system.

You are given raw OCR output from an invoice image.
The OCR may contain spelling mistakes, handwritten text, Arabic/English mixed text,
misaligned columns, broken numbers, and incorrect decimal placements.

Your task is to extract accurate invoice data using structured reasoning."""

EXTRACTION_PROMPT = """
---------------------------------------
STEP 1 — DOCUMENT LAYOUT ANALYSIS
---------------------------------------

{vision_instruction}

Identify these sections:

1. Header section
   - Vendor name (company/business name, often in large or bold text at the top)
   - Full address (P.O. Box, City, Country, Tel, Fax, Email)
   - VAT / VATIN number
   - C.R. NO (Commercial Registration)
   - Invoice/Receipt/Quotation number
   - Date and time

2. Customer section
   - "Mr./M/s." or "Customer" field — extract the name
   - If customer is "Cash", set payment_method = "CASH"

3. Table section
   - Detect column headers: Sl. No / Description / Qty / Unit Price / Total Amount
   - CRITICAL: Omani receipts often have SEPARATE "R.O." and "Bz." sub-columns
     under both "Unit Price" and "Total Amount". These are NOT units of measure.
     R.O. = Rial Omani (whole currency), Bz. = Baisa (1/1000 of a Rial).
     Combine them: value = RO_column + (Bz_column / 1000)
     Example: R.O. column shows "01", Bz. column shows "300" → 1.300 OMR
     Example: R.O. column shows "9", Bz. column shows "100" → 9.100 OMR
   - Read each data row carefully, especially handwritten entries
   - "unit" field should ONLY be a unit of measure (pcs, kg, lt, nos, box).
     NEVER put R.O., Bz., ريال, or بيسة in the "unit" field.

4. Footer section
   - Subtotal (before tax)
   - VAT rate (e.g., 5%)
   - VAT amount
   - Grand Total / Total R.O.
   - Look for "Total" row with R.O./Bz. values (e.g. "Total 9-100" = 9.100 OMR)

---------------------------------------
STEP 2 — CURRENCY ARITHMETIC (CRITICAL)
---------------------------------------

Omani Rial (OMR) uses R.O. (Rial Omani) and Bz. (Baisa):
- 1 R.O. = 1000 Bz. (like 1 Dollar = 100 Cents, but Oman uses 1000)
- OMR amounts have 3 decimal places

Conversion rules:
  "R.O. 01  Bz. 300"  →  1.300 OMR
  "R.O. 9   Bz. 100"  →  9.100 OMR
  "1-660"              →  1.660 OMR
  "7/650"              →  7.650 OMR
  "0.350"              →  0.350 OMR (350 Baisa)

ALL output amounts MUST be a single decimal number (e.g. 9.100, never "9 RO 100 Bz").

---------------------------------------
STEP 3 — INTELLIGENT NORMALIZATION
---------------------------------------

- Fix spelling mistakes from handwriting (e.g., "Dinnes" → "Dinner", "Gloupes" → "Gloves")
- Fix broken/split numbers from OCR
- Normalize date to YYYY-MM-DD (Omani dates are DD/MM/YYYY)
- Remove stamps, signatures, decorative text
- Validate: subtotal + VAT = total (if applicable)
- If VAT row exists but is empty, set vat_amount to null (not 0)
- Cross-check: qty × unit_price should equal line_total

---------------------------------------
STEP 4 — LINE ITEM STRUCTURING
---------------------------------------

For EACH row in the table:
- description: the item name (fix handwriting spelling)
- quantity: numeric value
- unit: ONLY measurement unit (pcs, kg, lt, nos, box). Leave "" if only currency columns exist.
- unit_price: single OMR decimal (combine R.O. + Bz. columns if separate)
- line_total: single OMR decimal (combine R.O. + Bz. columns if separate)
- confidence: 0.0 to 1.0 (lower for unclear handwriting)

If unit_price or line_total are 0 or missing but subtotal/total is known:
- Single item: line_total = subtotal, unit_price = subtotal / quantity
- Multiple items: infer from total minus other items

---------------------------------------
STEP 5 — VALIDATION
---------------------------------------

- Verify qty × unit_price ≈ line_total for each item
- Verify sum of line_totals ≈ subtotal
- Verify subtotal + vat_amount ≈ total_amount
- If values conflict, explain in validation_notes

---------------------------------------
STEP 6 — EXPENSE TYPE CLASSIFICATION
---------------------------------------

Based on the vendor name, line item descriptions, and overall document context,
classify this expense into ONE of these categories:
  Fuel & Gas, Food & Beverage, Office Supplies, Vehicle Maintenance,
  Travel & Transport, Utilities, Medical & Health, IT & Telecom,
  Building & Construction, Cleaning & Maintenance, Stationery & Printing,
  Safety Equipment, General Services, Miscellaneous

Choose the most specific matching category. If none fits well, use "Miscellaneous".

---------------------------------------
FINAL OUTPUT (STRICT JSON ONLY)
---------------------------------------

{{
  "vendor_name": "",
  "vendor_address": "",
  "document_type": "",
  "expense_type": "",
  "invoice_number": "",
  "receipt_number": "",
  "invoice_date": "",
  "invoice_time": "",
  "vat_number": "",
  "cr_no": "",
  "customer_name": "",
  "site_name": "",
  "site_code": "",
  "pump_no": "",
  "currency": "OMR",
  "line_items": [
    {{
      "description": "",
      "quantity": 0,
      "unit": "",
      "unit_price": 0.0,
      "line_total": 0.0,
      "confidence": 0.0
    }}
  ],
  "subtotal": 0.0,
  "vat_amount": 0.0,
  "vat_percentage": 0,
  "total_amount": 0.0,
  "payment_method": "",
  "plate_number": "",
  "confidence_score": 0.0,
  "validation_notes": ""
}}

RULES:
- Use null for truly missing values
- All amounts as single OMR decimals (3 decimal places)
- "unit" must NEVER contain R.O., Bz., ريال, بيسة, or any currency
- Return ONLY valid JSON, no markdown, no explanation

EXAMPLE — Omani Quotation (separate R.O./Bz. columns):
  Image shows: No. 4852, Date 3/9/2025, Mr./M/s. Cash
  Table: 1 | Double dotted Gloves | 7 | R.O. 01 Bz. 300 | R.O. 9 Bz. 100
  Total: 9-100
  Correct: invoice_number="4852", line_items=[{{"description":"Double dotted Gloves","quantity":7,"unit":"","unit_price":1.300,"line_total":9.100}}], total_amount=9.100
  Validation: 7 × 1.300 = 9.100 ✓

{ocr_section}"""


# ---------------------------------------------------------------------------
# Image encoding helpers
# ---------------------------------------------------------------------------

def _encode_image_base64(file_path: str) -> Optional[str]:
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None


def _get_image_media_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".gif": "image/gif",
        ".bmp": "image/bmp", ".webp": "image/webp",
    }.get(ext, "image/jpeg")


def _build_prompt(vision_mode: bool, raw_text: str = "") -> tuple:
    """Build the prompt and vision instruction for the extraction."""
    if vision_mode:
        vision_instruction = (
            "Look at the IMAGE provided. You can see the actual document.\n"
            "Use your vision to read handwritten text, table structure, and amounts directly.\n"
            "The OCR text below is supplementary — trust the IMAGE when OCR text is garbled."
        )
        if raw_text and raw_text.strip():
            ocr_section = (
                "---------------------------------------\n"
                "SUPPLEMENTARY OCR TEXT (may have errors):\n"
                "---------------------------------------\n"
                + raw_text.strip()[:12000]
            )
        else:
            ocr_section = "(No OCR text available — extract everything from the image)"
    else:
        vision_instruction = (
            "You do NOT have access to the image. Use ONLY the OCR text below.\n"
            "The OCR may have errors — use reasoning to correct them."
        )
        ocr_section = (
            "---------------------------------------\n"
            "OCR TEXT TO EXTRACT:\n"
            "---------------------------------------\n"
            + (raw_text or "").strip()[:15000]
        )

    prompt = EXTRACTION_PROMPT.replace("{vision_instruction}", vision_instruction)
    prompt = prompt.replace("{ocr_section}", ocr_section)
    return prompt, vision_instruction


def _parse_llm_response(content: str) -> Optional[Dict[str, Any]]:
    """Parse JSON from LLM response, stripping markdown fences if present."""
    content = (content or "").strip()
    if "```" in content:
        content = re.sub(r"^.*?```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```.*$", "", content)
    data = json.loads(content)
    if not isinstance(data, dict):
        return None
    return data


# ---------------------------------------------------------------------------
# GPT-4o-mini — primary extraction (fast, cost-effective)
# ---------------------------------------------------------------------------

def _call_gpt4o_mini_vision(image_path: str, raw_text: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Send image + OCR text to GPT-4o-mini (multimodal)."""
    img_b64 = _encode_image_base64(image_path)
    if not img_b64:
        return None

    from openai import OpenAI

    prompt, _ = _build_prompt(vision_mode=True, raw_text=raw_text)
    media_type = _get_image_media_type(image_path)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{img_b64}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            },
        ],
    )
    data = _parse_llm_response(response.choices[0].message.content)
    return _normalize_llm_output(data) if data else None


def _call_gpt4o_mini_text(raw_text: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Send OCR text only to GPT-4o-mini (no image)."""
    from openai import OpenAI

    prompt, _ = _build_prompt(vision_mode=False, raw_text=raw_text)

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.1,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": TEXT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    data = _parse_llm_response(response.choices[0].message.content)
    return _normalize_llm_output(data) if data else None


# ---------------------------------------------------------------------------
# Public API — GPT-4o-mini only
# ---------------------------------------------------------------------------

def extract_expense_with_vision_llm(
    image_path: str, raw_text: str = "", api_key: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    MULTIMODAL extraction: sends image + OCR text to GPT-4o-mini.
    Returns normalized result with _extraction_model tag.
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key or not image_path:
        return None

    try:
        result = _call_gpt4o_mini_vision(image_path, raw_text, api_key)
        if result:
            result["_extraction_model"] = "GPT-4o-mini"
        return result
    except Exception as e:
        print(f"[EXPENSE] GPT-4o-mini vision failed: {e}")
        return None


def extract_expense_with_llm(
    raw_text: str, api_key: Optional[str] = None, image_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    TEXT-ONLY extraction: sends OCR text to GPT-4o-mini (for PDFs or when no image).
    Returns normalized result with _extraction_model tag.
    """
    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key or not raw_text or len(raw_text.strip()) < 20:
        return None

    try:
        result = _call_gpt4o_mini_text(raw_text, api_key)
        if result:
            result["_extraction_model"] = "GPT-4o-mini"
        return result
    except Exception as e:
        print(f"[EXPENSE] GPT-4o-mini text failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------

def _normalize_llm_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map the LLM JSON output to our internal expense store schema."""
    out = {}

    field_map = {
        "vendor_name": "vendor",
        "vendor_address": "vendor_address",
        "document_type": "document_type",
        "expense_type": "expense_type",
        "invoice_number": "invoice_no",
        "receipt_number": "receipt_no",
        "invoice_date": "receipt_date",
        "invoice_time": "receipt_time",
        "vat_number": "site_vat_no",
        "cr_no": "cr_no",
        "customer_name": "customer_name",
        "site_name": "site_name",
        "site_code": "site_code",
        "pump_no": "pump_no",
        "currency": "currency",
        "subtotal": "subtotal",
        "vat_amount": "vat_amount",
        "vat_percentage": "vat_rate",
        "total_amount": "total_amount",
        "payment_method": "payment_method",
        "plate_number": "plate_number",
        "confidence_score": "confidence_score",
        "validation_notes": "validation_notes",
    }
    for llm_key, store_key in field_map.items():
        v = data.get(llm_key)
        if v is not None and v != "":
            out[store_key] = v

    raw_items = data.get("line_items")
    if isinstance(raw_items, list) and len(raw_items) > 0:
        from cashbill_expense.expense_parser import _clean_unit_field
        items = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            unit_val = item.get("unit") or ""
            items.append({
                "sl_no": str(len(items) + 1),
                "description": item.get("description") or "",
                "qty": item.get("quantity"),
                "unit": _clean_unit_field(unit_val),
                "unit_price": item.get("unit_price"),
                "amount": item.get("line_total"),
                "confidence": item.get("confidence"),
            })
        if items:
            out["line_items"] = items

    if out.get("total_amount") is not None:
        out["amount"] = out["total_amount"]
    if out.get("vat_amount") is not None:
        out["tax_amount"] = out["vat_amount"]

    return out if out else None
