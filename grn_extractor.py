"""
GRN (Goods Received Note) Extractor.
Extracts PO reference, vendor, amounts, line items using same schema as PO for matching.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Tuple


def extract_grn_from_file(file_path: str, api_key: str = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Extract GRN data from a file. Returns (extracted_data, metadata).
    Uses same document_type and structure as PO for three-way matching (PO number, vendor, amounts).
    """
    from document_parser import DocumentParser

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    parser = DocumentParser(use_gcs_vision=True)
    document_text, page_map = parser.parse_with_pages(file_path, use_ocr=False)

    if not document_text or len(document_text.strip()) < 30:
        return (
            {"document_type": "GRN", "error": "Could not extract text from document"},
            {"file_path": file_path, "extraction_method": "failed"},
        )

    # Use LLM to extract GRN fields (PO reference, vendor, amounts, line items)
    text_sample = document_text[:6000] if len(document_text) > 6000 else document_text
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You extract data from Goods Received Note (GRN) / Delivery Note documents. "
                    "Return ONLY valid JSON. Extract PO number/reference, vendor/supplier, buyer, amounts, line items."
                },
                {
                    "role": "user",
                    "content": f"""Extract from this GRN/delivery document. Return JSON with:
- document_type: "GRN"
- document_ids: {{ "po_number": "", "order_number": "", "reference_id": "", "document_number": "" }}
- party_names: {{ "vendor": "", "customer": "", "party_1": "", "party_2": "" }}
- dates: {{ "po_date": "", "delivery_date": "" }}
- amounts: {{ "subtotal": "", "total": "" }}, amount: "", currency: ""
- line_items: [ {{ "description": "", "quantity": "", "unit": "", "amount": "" }} ]

DOCUMENT TEXT:
{text_sample}
"""
                },
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = response.choices[0].message.content
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        data = json.loads(raw.strip())
        data["document_type"] = "GRN"
        if not data.get("document_ids"):
            data["document_ids"] = {}
        if not data.get("party_names"):
            data["party_names"] = {}
        if not data.get("line_items"):
            data["line_items"] = []
        if not data.get("amounts"):
            data["amounts"] = {}
        metadata = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "document_text": document_text,
            "page_map": page_map,
            "total_pages": len(page_map),
            "extraction_method": "grn_extractor",
        }
        return data, metadata
    except Exception as e:
        return (
            {"document_type": "GRN", "error": str(e), "document_ids": {}, "party_names": {}, "line_items": [], "amounts": {}},
            {"file_path": file_path, "extraction_method": "failed"},
        )
