"""
Purchase Order Extractor Module
Extracts structured information from Purchase Order documents.
Uses the same extraction pipeline as invoices (OCR, Vision API, etc.)
"""

import os
import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path


def get_po_extraction_system_prompt() -> str:
    """Get the system prompt for PO extraction."""
    return """You are an AI Purchase Order Data Extraction Engine.
You MUST extract ALL relevant purchase order details with high precision and zero hallucinations.

EXTRACTION RULES:
1. If any data is missing or not present → return null or empty string.
2. NEVER hallucinate or invent PO details.
3. Extract exact amounts, dates, and identifiers as they appear.
4. CRITICAL: Preserve ALL decimal places in amounts - NEVER round.
5. Convert all dates to ISO format: YYYY-MM-DD.
6. Return EXACT JSON — no explanation, no markdown, no notes.
7. Extract all tax details (GST, VAT, CGST, SGST, IGST, etc.) if present.
8. Parse line items with description, quantity, rate, and amount.
9. CRITICAL: Identify buyer/customer and vendor/supplier accurately."""


def create_po_extraction_prompt(document_text: str) -> str:
    """Create extraction prompt specifically for Purchase Orders."""
    return f"""Analyze the following PURCHASE ORDER document and extract ALL relevant information:

DOCUMENT TEXT:
{document_text}

REQUIRED OUTPUT FORMAT (STRICT JSON):
{{
  "document_type": "PURCHASE_ORDER",
  "po_type": "",
  "party_names": {{
    "vendor": "",
    "vendor_address": "",
    "vendor_tax_ids": {{
      "gstin": "",
      "pan": "",
      "vat": "",
      "tax_id": "",
      "tin": "",
      "trn": "",
      "cr_number": ""
    }},
    "customer": "",
    "customer_address": "",
    "customer_tax_ids": {{
      "gstin": "",
      "pan": "",
      "vat": "",
      "tax_id": "",
      "tin": "",
      "trn": "",
      "cr_number": ""
    }},
    "party_1": "",
    "party_2": "",
    "additional_parties": []
  }},
  "document_ids": {{
    "po_number": "",
    "order_number": "",
    "reference_id": "",
    "document_number": "",
    "quotation_number": "",
    "contract_id": "",
    "project_id": "",
    "other_ids": []
  }},
  "dates": {{
    "po_date": "",
    "delivery_date": "",
    "due_date": "",
    "valid_until": "",
    "ship_date": ""
  }},
  "start_date": "",
  "due_date": "",
  "amounts": {{
    "subtotal": "",
    "additional_charges": [
      {{
        "label": "",
        "amount": ""
      }}
    ],
    "taxes": [
      {{
        "label": "",
        "percent": "",
        "amount": ""
      }}
    ],
    "discount": "",
    "discount_percent": "",
    "total": "",
    "advance_payment": "",
    "balance_due": ""
  }},
  "amount": "",
  "amount_explanation": "",
  "currency": "",
  "line_items": [
    {{
      "item_number": "",
      "description": "",
      "sku": "",
      "hsn_sac_code": "",
      "quantity": "",
      "unit": "",
      "rate": "",
      "amount": "",
      "tax_rate": "",
      "delivery_date": ""
    }}
  ],
  "tax_details": {{
    "gst": "",
    "cgst": "",
    "sgst": "",
    "igst": "",
    "vat": "",
    "other_taxes": []
  }},
  "shipping_details": {{
    "ship_to_address": "",
    "ship_to_contact": "",
    "shipping_method": "",
    "shipping_terms": "",
    "incoterms": ""
  }},
  "payment_details": {{
    "payment_terms": "",
    "payment_method": "",
    "bank_name": "",
    "account_number": "",
    "ifsc_code": "",
    "swift_code": "",
    "iban": ""
  }},
  "frequency": "",
  "account_type": "Accounts Payable",
  "notes": "",
  "terms_and_conditions": "",
  "special_instructions": "",
  "approval_status": "",
  "authorized_signatory": "",
  "rules_and_compliance_violation": "",
  "risk_score": null
}}

EXTRACTION INSTRUCTIONS:
1. PO Type: Identify type (Standard PO, Blanket PO, Contract PO, Planned PO, etc.)

2. PO NUMBER EXTRACTION (CRITICAL - MOST IMPORTANT):
   - This is the PRIMARY identifier of the Purchase Order
   - Look for labels: "PO Number:", "PO #:", "PO:", "PO No:", "P.O. Number:", "Purchase Order Number:", "Order No:"
   - EXTRACT THE COMPLETE VALUE after the label, including ALL prefixes
   
   ⚠️ CRITICAL RULE: The PO number value often STARTS WITH "PO-" - this is PART OF THE VALUE, NOT the label!
   - When you see "PO #: PO-2025-0092", the label is "PO #:" and the VALUE is "PO-2025-0092" (including the "PO-" prefix)
   - Do NOT confuse the "PO-" in the value with the "PO" in the label - they are DIFFERENT!
   
   - CORRECT EXAMPLES:
     * "PO Number: PO-NEX-2026-11" → po_number: "PO-NEX-2026-11" ✓
     * "PO #: PO-2025-0092" → po_number: "PO-2025-0092" ✓ (NOT "-2025-0092")
     * "PO: PO-GLO-2026-8841" → po_number: "PO-GLO-2026-8841" ✓
     * "PO No: PO-SPC-2026-0091" → po_number: "PO-SPC-2026-0091" ✓
     * "Purchase Order Number: 12345" → po_number: "12345" ✓
     
   - WRONG EXAMPLES (DO NOT DO THIS):
     * "PO #: PO-2025-0092" → po_number: "-2025-0092" ✗ (WRONG! Missing "PO" prefix)
     * "PO Number: PO-NEX-2026-11" → po_number: "-NEX-2026-11" ✗ (WRONG!)
     * "PO #: PO-2025-0092" → po_number: "2025-0092" ✗ (WRONG! Missing "PO-" prefix)
   
   - CRITICAL: When you see "PO Number: PO-NEX-2026-11":
     * The label is: "PO Number:"
     * The VALUE is: "PO-NEX-2026-11" (the ENTIRE string after the colon, including "PO-")
     * Do NOT remove "PO-" thinking it's part of the label - it's PART OF THE VALUE!
   
   - NEVER truncate or remove parts of the PO number
   - Include the full alphanumeric string (with hyphens, underscores, etc.)
   - If PO number starts with "PO-" include it completely - it is PART OF THE VALUE, NOT the label

3. Vendor/Supplier: The company receiving the order (look for "VENDOR", "SUPPLIER", "SELLER", "TO", "SHIP FROM")
   - Vendor Address: Extract full address from vendor section
4. Customer/Buyer: The company placing the order (look for "BUYER", "CUSTOMER", "FROM", "ORDERED BY", "PURCHASER")
   - Customer Address: Extract billing/company address
5. Tax Identifiers: Extract for BOTH vendor and customer
   - GSTIN, PAN, VAT, TIN, TRN, Tax ID, CR Number
6. Document IDs: Extract ALL identification numbers
   - po_number: Main PO identifier (MOST IMPORTANT - see rule 2 above)
   - order_number: Alternative order number
   - reference_id: Any reference number
   - quotation_number: Quote reference if present
   - contract_id: Contract reference
   - project_id: Project reference
7. Dates: Extract all dates as YYYY-MM-DD
   - po_date: Date PO was created/issued
   - delivery_date: Expected delivery date
   - due_date: Payment due date
   - valid_until: PO validity date
8. Amounts and Currency:
   - Extract ALL monetary values EXACTLY as shown
   - Preserve ALL decimal places
   - Detect currency from symbols or codes
9. Line Items: Extract EACH product/service with:
   - Item number/SKU
   - Description
   - HSN/SAC code if present
   - Quantity and Unit
   - Rate/Unit price
   - Amount/Total for that line
   - Tax rate if shown
   - Delivery date if per-item
10. Shipping Details: Ship-to address, contact, method, terms, incoterms
11. Payment Details: Payment terms, method, bank details
12. For party_1, use customer/buyer name; for party_2, use vendor/supplier name
13. For amount field, use the total/grand total
14. amount_explanation: Brief explanation of how total was derived
15. For start_date, use po_date; for due_date, use payment due date or delivery date

IMPORTANT NOTES:
- PO NUMBER is the most critical field for matching with invoices
- Different POs use different formats: alphanumeric, with prefixes, with dashes
- Customer is who issues the PO (buyer), Vendor is who receives it (seller)
- Look carefully at the document structure to identify buyer vs seller
- Extract ALL line items, don't skip any
- Be flexible with terminology

Return ONLY valid JSON."""


def extract_po_data(document_text: str, api_key: str = None) -> Dict[str, Any]:
    """
    Extract data from a Purchase Order document.
    
    Args:
        document_text: The text content of the PO document
        api_key: OpenAI API key (optional, uses env var if not provided)
        
    Returns:
        Dictionary with extracted PO data
    """
    if not api_key:
        api_key = os.getenv('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OpenAI API key not configured")
    
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        prompt = create_po_extraction_prompt(document_text)
        
        response = llm.invoke([
            SystemMessage(content=get_po_extraction_system_prompt()),
            HumanMessage(content=prompt)
        ])
        
        return _parse_po_extraction_response(response.content, document_text)
        
    except ImportError:
        # Fallback to direct OpenAI API
        from openai import OpenAI
        
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": get_po_extraction_system_prompt()},
                {"role": "user", "content": create_po_extraction_prompt(document_text)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        return _parse_po_extraction_response(response.choices[0].message.content, document_text)


def _parse_po_extraction_response(content: str, document_text: str = "") -> Dict[str, Any]:
    """Parse extraction response from LLM."""
    try:
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        result = json.loads(content.strip())
        
        # Ensure document_type is set
        result["document_type"] = "PURCHASE_ORDER"
        
        # Normalize PO data (pass document_text for PO number fix)
        result = _normalize_po_data(result, document_text)
        
        return result
        
    except json.JSONDecodeError as e:
        print(f"[PO_EXTRACTOR] JSON parse error: {e}")
        return {
            "document_type": "PURCHASE_ORDER",
            "error": f"Failed to parse extraction response: {str(e)}",
            "raw_content": content[:500] if content else ""
        }


def _normalize_po_data(extracted_data: Dict[str, Any], document_text: str = "") -> Dict[str, Any]:
    """Normalize PO extracted data for consistency."""
    
    # Ensure document_ids exists and has po_number
    doc_ids = extracted_data.get("document_ids", {})
    if not isinstance(doc_ids, dict):
        doc_ids = {}
    
    # Normalize PO number - check multiple fields
    po_number = (
        doc_ids.get("po_number", "").strip() or
        doc_ids.get("order_number", "").strip() or
        ""
    )
    
    # Clean PO number - remove labels
    if po_number:
        po_number = _clean_id_value(po_number)
        
        # Fix PO number if it starts with "-" (missing "PO" prefix)
        # Check if document text contains "PO-" followed by the rest of the number
        if po_number.startswith("-") and document_text:
            # Extract the part after the hyphen
            rest_of_number = po_number[1:]  # e.g., "NEX-2026-11"
            # Check if document contains "PO-" followed by this number
            if f"PO-{rest_of_number}" in document_text or f"PO {rest_of_number}" in document_text:
                po_number = f"PO{po_number}"  # Prepend "PO" to "-NEX-2026-11" → "PO-NEX-2026-11"
                print(f"[PO_EXTRACTOR] Fixed PO number: added 'PO' prefix → '{po_number}'")
        
        doc_ids["po_number"] = po_number
    
    extracted_data["document_ids"] = doc_ids
    
    # Ensure party_names exists
    party_names = extracted_data.get("party_names", {})
    if not isinstance(party_names, dict):
        party_names = {}
    
    # Normalize vendor/customer
    vendor = party_names.get("vendor", "") or party_names.get("party_2", "") or ""
    customer = party_names.get("customer", "") or party_names.get("party_1", "") or ""
    
    # For PO: customer is the buyer (party_1), vendor is the seller (party_2)
    if not party_names.get("party_1") and customer:
        party_names["party_1"] = customer
    if not party_names.get("party_2") and vendor:
        party_names["party_2"] = vendor
    
    extracted_data["party_names"] = party_names
    
    # Ensure amounts
    if not extracted_data.get("amount"):
        amounts = extracted_data.get("amounts", {})
        if isinstance(amounts, dict):
            extracted_data["amount"] = amounts.get("total", "") or amounts.get("subtotal", "")
    
    # Ensure line_items is a list
    if not isinstance(extracted_data.get("line_items"), list):
        extracted_data["line_items"] = []
    
    return extracted_data


def _clean_id_value(value: str) -> str:
    """Clean ID value by removing common labels, but preserve PO- prefix in the value."""
    # Only remove labels that end with colon or are followed by space
    # Do NOT remove "PO-" prefix from the actual value
    labels_to_remove = [
        "po no:", "po no ", "p.o. no:", "p.o. no ",
        "po number:", "po number ", "po #:", "po # ",
        "purchase order:", "purchase order no:", "purchase order no ",
        "order no:", "order no ", "order:",
        "p.o.:", "p.o. "
    ]
    
    value_lower = value.lower().strip()
    original_value = value.strip()
    
    # Remove labels (only if they're actual labels, not part of the value)
    for label in labels_to_remove:
        if value_lower.startswith(label):
            # Check if what comes after is a valid PO number (starts with PO- or alphanumeric)
            remaining = original_value[len(label):].strip()
            if remaining.startswith("PO-") or remaining.startswith("po-") or remaining[0].isalnum():
                value = remaining
                break
    
    # If value starts with just "po" (not "po-"), it might be a label - check context
    value_stripped = value.strip()
    if value_stripped.lower() == "po" or (len(value_stripped) > 2 and value_stripped[:2].lower() == "po" and value_stripped[2] not in ["-", " "]):
        # This might be just the label "PO", return as is and let normalization handle it
        pass
    
    return value_stripped


class POExtractor:
    """Purchase Order Extractor using the same pipeline as invoice extraction."""
    
    def __init__(self, api_key: str = None, use_gcs_vision: bool = True):
        """
        Initialize PO extractor.
        
        Args:
            api_key: OpenAI API key
            use_gcs_vision: Whether to use GCS Vision API for OCR
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.use_gcs_vision = use_gcs_vision
    
    def extract_from_file(self, file_path: str, use_ocr: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract PO data from a file.
        
        Args:
            file_path: Path to the PO file (PDF, DOCX, etc.)
            use_ocr: Whether to force OCR processing
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        from document_parser import DocumentParser
        
        # Parse document (uses same pipeline as invoices)
        parser = DocumentParser(use_gcs_vision=self.use_gcs_vision)
        document_text, page_map = parser.parse_with_pages(file_path, use_ocr=use_ocr)
        
        if not document_text or len(document_text.strip()) < 50:
            return {
                "document_type": "PURCHASE_ORDER",
                "error": "Could not extract text from document"
            }, {
                "file_path": file_path,
                "extraction_method": "failed"
            }
        
        # Extract PO data
        extracted_data = extract_po_data(document_text, self.api_key)
        
        metadata = {
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "document_text": document_text,
            "page_map": page_map,
            "total_pages": len(page_map),
            "total_characters": len(document_text),
            "extraction_method": "vision_api" if self.use_gcs_vision else "text_based"
        }
        
        return extracted_data, metadata
    
    def extract_from_text(self, document_text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract PO data from text.
        
        Args:
            document_text: Text content of the PO
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        extracted_data = extract_po_data(document_text, self.api_key)
        
        metadata = {
            "extraction_method": "text_input",
            "total_characters": len(document_text)
        }
        
        return extracted_data, metadata


def get_po_extractor(api_key: str = None, use_gcs_vision: bool = True) -> POExtractor:
    """Get or create a PO extractor instance."""
    return POExtractor(api_key=api_key, use_gcs_vision=use_gcs_vision)
