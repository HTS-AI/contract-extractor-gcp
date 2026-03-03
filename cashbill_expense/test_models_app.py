"""
Streamlit app to test and compare LLM model capabilities for cash bill extraction.

Models available:
  - GPT-4o-mini   (fast, cheap — good for computer-generated bills)
  - GPT-4.1-nano  (lightweight text-only)
  - GPT-4.1       (most capable — best for handwriting/ICR)

Modes:
  - Vision (multimodal): sends image + OCR text to the model
  - Text-only: sends only OCR text

Run:  streamlit run cashbill_expense/test_models_app.py
"""

import os
import sys
import json
import time
import base64
import tempfile
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

import streamlit as st

sys.path.insert(0, str(PROJECT_ROOT))

from cashbill_expense.llm_extract import (
    _encode_image_base64,
    _get_image_media_type,
    _build_prompt,
    _parse_llm_response,
    _normalize_llm_output,
    VISION_SYSTEM_PROMPT,
    TEXT_SYSTEM_PROMPT,
)

MODELS = {
    "GPT-4o-mini": "gpt-4o-mini",
    "GPT-4.1-nano": "gpt-4.1-nano",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def run_ocr(file_path: str, filename: str) -> str:
    """Run GCP Vision OCR on the file."""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        from cashbill_expense.vision_extract import _ocr_image_via_vision
        return _ocr_image_via_vision(file_path)
    elif ext == ".pdf":
        from cashbill_expense.vision_extract import _ocr_pdf_via_vision
        return _ocr_pdf_via_vision(file_path, filename)
    return ""


def call_model(model_id: str, api_key: str, image_path: str = None, raw_text: str = "") -> dict:
    """Call a specific model and return the raw + normalized result with timing."""
    from openai import OpenAI

    is_vision = image_path is not None and Path(image_path).suffix.lower() in IMAGE_EXTENSIONS
    can_do_vision = model_id != "gpt-4.1-nano"

    use_vision = is_vision and can_do_vision

    prompt, _ = _build_prompt(vision_mode=use_vision, raw_text=raw_text)
    system_prompt = VISION_SYSTEM_PROMPT if use_vision else TEXT_SYSTEM_PROMPT

    client = OpenAI(api_key=api_key)

    if use_vision:
        img_b64 = _encode_image_base64(image_path)
        media_type = _get_image_media_type(image_path)
        messages = [
            {"role": "system", "content": system_prompt},
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
        ]
    else:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

    start = time.time()
    response = client.chat.completions.create(
        model=model_id,
        temperature=0.1,
        max_tokens=4096,
        messages=messages,
    )
    elapsed = round(time.time() - start, 2)

    raw_content = response.choices[0].message.content or ""
    tokens_in = response.usage.prompt_tokens if response.usage else 0
    tokens_out = response.usage.completion_tokens if response.usage else 0

    try:
        parsed = _parse_llm_response(raw_content)
        normalized = _normalize_llm_output(parsed) if parsed else None
    except Exception as e:
        parsed = None
        normalized = {"_error": str(e)}

    return {
        "model": model_id,
        "mode": "vision" if use_vision else "text-only",
        "elapsed_sec": elapsed,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "raw_response": raw_content,
        "normalized": normalized,
    }


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Cash Bill LLM Model Tester", layout="wide", page_icon="🧪")

st.title("🧪 Cash Bill Extraction — Model Comparison")
st.caption("Upload a cash bill image or PDF. Select models to test. Compare extraction quality side-by-side.")

api_key = os.getenv("OPENAI_API_KEY", "")

# Sidebar
with st.sidebar:
    st.header("Settings")

    if api_key:
        st.success("OpenAI API key loaded from .env")
    else:
        st.error("OPENAI_API_KEY not found in .env file")

    st.divider()
    st.subheader("Select Models to Test")
    selected_models = []
    for label, model_id in MODELS.items():
        note = ""
        if model_id == "gpt-4o-mini":
            note = " (multimodal, fast)"
        elif model_id == "gpt-4.1-nano":
            note = " (text-only, cheapest)"
        if st.checkbox(f"{label}{note}", value=True, key=f"cb_{model_id}"):
            selected_models.append((label, model_id))

    st.divider()
    run_ocr_flag = st.checkbox("Run GCP Vision OCR", value=True, help="Uncheck to paste OCR text manually")

    st.divider()
    st.markdown("""
    **Model Guide**
    | Model | Vision | Cost |
    |-------|--------|------|
    | GPT-4o-mini | Yes | Low |
    | GPT-4.1-nano | No | Lowest |
    """)

# Main area
uploaded = st.file_uploader("Upload a cash bill (image or PDF)", type=["jpg", "jpeg", "png", "gif", "bmp", "webp", "pdf"])

col_img, col_ocr = st.columns([1, 1])

temp_path = None
raw_text = ""

if uploaded:
    suffix = Path(uploaded.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getvalue())
        temp_path = tmp.name

    with col_img:
        st.subheader("Uploaded Document")
        if suffix.lower() in IMAGE_EXTENSIONS:
            st.image(uploaded, use_container_width=True)
        else:
            st.info(f"PDF file: {uploaded.name} ({len(uploaded.getvalue()) / 1024:.1f} KB)")

    with col_ocr:
        st.subheader("OCR Text")
        if run_ocr_flag:
            with st.spinner("Running GCP Vision OCR..."):
                try:
                    raw_text = run_ocr(temp_path, uploaded.name)
                    st.text_area("Raw OCR output", value=raw_text, height=300, key="ocr_out")
                except Exception as e:
                    st.error(f"OCR failed: {e}")
                    raw_text = ""
                    st.text_area("Paste OCR text manually", value="", height=300, key="ocr_manual")
                    raw_text = st.session_state.get("ocr_manual", "")
        else:
            raw_text = st.text_area("Paste OCR text manually", value="", height=300, key="ocr_paste")

# Run extraction
if uploaded and api_key and selected_models:
    if st.button("🚀 Run Extraction on Selected Models", type="primary", use_container_width=True):
        results = {}
        progress = st.progress(0, text="Starting...")

        for i, (label, model_id) in enumerate(selected_models):
            progress.progress((i) / len(selected_models), text=f"Running {label}...")
            with st.spinner(f"Calling {label} ({model_id})..."):
                try:
                    result = call_model(
                        model_id=model_id,
                        api_key=api_key,
                        image_path=temp_path if suffix.lower() in IMAGE_EXTENSIONS else None,
                        raw_text=raw_text,
                    )
                    results[label] = result
                except Exception as e:
                    results[label] = {
                        "model": model_id,
                        "mode": "error",
                        "elapsed_sec": 0,
                        "tokens_in": 0,
                        "tokens_out": 0,
                        "raw_response": "",
                        "normalized": {"_error": str(e)},
                    }

        progress.progress(1.0, text="Done!")

        # --- Comparison Summary ---
        st.divider()
        st.subheader("📊 Comparison Summary")

        summary_cols = st.columns(len(results))
        for idx, (label, res) in enumerate(results.items()):
            with summary_cols[idx]:
                norm = res.get("normalized") or {}
                conf = norm.get("confidence_score")
                conf_str = f"{float(conf) * 100:.0f}%" if conf else "N/A"
                st.metric(label, conf_str, delta=f"{res['elapsed_sec']}s")
                st.caption(f"Mode: {res['mode']} | Tokens: {res['tokens_in']}→{res['tokens_out']}")

        # --- Detailed Results ---
        st.divider()
        st.subheader("📋 Detailed Results")

        tabs = st.tabs([label for label in results.keys()])
        for tab, (label, res) in zip(tabs, results.items()):
            with tab:
                norm = res.get("normalized") or {}
                if norm.get("_error"):
                    st.error(f"Error: {norm['_error']}")
                    with st.expander("Raw response"):
                        st.code(res.get("raw_response", ""), language="text")
                    continue

                info_col, items_col = st.columns([1, 1])
                with info_col:
                    st.markdown("**Document Info**")
                    info_fields = [
                        ("Vendor", "vendor"),
                        ("Address", "vendor_address"),
                        ("Document Type", "document_type"),
                        ("Invoice No", "invoice_no"),
                        ("Receipt No", "receipt_no"),
                        ("Date", "receipt_date"),
                        ("Time", "receipt_time"),
                        ("VAT Number", "site_vat_no"),
                        ("C.R. No", "cr_no"),
                        ("Customer", "customer_name"),
                        ("Currency", "currency"),
                        ("Payment Method", "payment_method"),
                        ("Plate Number", "plate_number"),
                    ]
                    for field_label, field_key in info_fields:
                        val = norm.get(field_key)
                        if val:
                            st.text(f"  {field_label}: {val}")

                    st.markdown("**Amounts**")
                    for field_label, field_key in [
                        ("Subtotal", "subtotal"),
                        ("VAT Rate", "vat_rate"),
                        ("VAT Amount", "vat_amount"),
                        ("Total Amount", "total_amount"),
                    ]:
                        val = norm.get(field_key)
                        if val is not None:
                            display = f"{val}%" if field_key == "vat_rate" else f"{val} OMR"
                            st.text(f"  {field_label}: {display}")

                    conf = norm.get("confidence_score")
                    if conf is not None:
                        pct = conf * 100 if conf <= 1 else conf
                        st.text(f"  Confidence: {pct:.0f}%")

                    vnotes = norm.get("validation_notes")
                    if vnotes:
                        st.info(f"Validation: {vnotes}")

                with items_col:
                    st.markdown("**Line Items**")
                    items = norm.get("line_items") or []
                    if items:
                        for it in items:
                            if not isinstance(it, dict):
                                continue
                            desc = it.get("description", "-")
                            qty = it.get("qty", "-")
                            up = it.get("unit_price")
                            amt = it.get("amount")
                            conf = it.get("confidence")
                            up_str = f"{up:.3f}" if up is not None else "-"
                            amt_str = f"{amt:.3f}" if amt is not None else "-"
                            conf_str = f"{conf * 100:.0f}%" if conf is not None and conf <= 1 else (f"{conf:.0f}%" if conf else "-")
                            st.text(f"  {desc}")
                            st.text(f"    Qty: {qty}  |  Unit Price: {up_str}  |  Amount: {amt_str}  |  Conf: {conf_str}")
                    else:
                        st.warning("No line items extracted")

                with st.expander("Raw JSON response"):
                    st.code(res.get("raw_response", ""), language="json")

                with st.expander("Normalized output"):
                    st.json(norm)

        # --- Side-by-side field comparison ---
        if len(results) > 1:
            st.divider()
            st.subheader("🔍 Field-by-Field Comparison")

            compare_fields = [
                "vendor", "document_type", "invoice_no", "receipt_no",
                "receipt_date", "currency", "subtotal", "vat_rate",
                "vat_amount", "total_amount", "payment_method", "customer_name",
                "confidence_score",
            ]

            header_row = ["Field"] + list(results.keys())
            rows = []
            for field in compare_fields:
                row = [field]
                for label in results:
                    norm = results[label].get("normalized") or {}
                    val = norm.get(field)
                    row.append(str(val) if val is not None else "-")
                rows.append(row)

            st.table({"": [r[0] for r in rows], **{h: [r[i+1] for r in rows] for i, h in enumerate(list(results.keys()))}})

elif uploaded and not api_key:
    st.error("OPENAI_API_KEY not found. Please add it to the .env file in the project root.")
elif uploaded and not selected_models:
    st.warning("Please select at least one model to test.")
else:
    st.info("Upload a cash bill image or PDF to get started.")

# Cleanup
if temp_path and os.path.exists(temp_path):
    pass  # kept for the session; OS cleans tempdir
