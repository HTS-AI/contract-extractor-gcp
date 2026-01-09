"""
LangGraph-based Contract Extraction Agent
Replaces traditional orchestrator with a stateful, graph-based agent workflow.
"""

import os
import re
import json
from typing import Dict, Any, Optional, Literal, Annotated, TypedDict, List
from pathlib import Path
from datetime import datetime

# LangGraph imports
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

# Local imports
from document_parser import DocumentParser


# ============== State Definition ==============

class ExtractionState(TypedDict):
    """State that flows through the extraction graph."""
    # Input
    file_path: Optional[str]
    document_text: Optional[str]
    page_map: Dict[int, str]
    use_ocr: bool
    use_gcs_vision: bool
    
    # Processing state
    document_type: Optional[str]
    classification_confidence: Optional[str]
    classification_reasoning: Optional[str]
    
    # Extraction results
    extracted_data: Dict[str, Any]
    
    # Metadata
    error: Optional[str]
    status: str  # "pending", "parsing", "classifying", "extracting", "enhancing", "completed", "failed"
    
    # Messages for agent reasoning
    messages: Annotated[List, add_messages]


# ============== Agent Tools ==============

def create_extraction_tools(api_key: str):
    """Create tools for the extraction agent."""
    
    @tool
    def classify_document(document_text: str) -> Dict[str, Any]:
        """
        Classify the document type (LEASE, NDA, or CONTRACT).
        
        Args:
            document_text: The text content of the document
            
        Returns:
            Dictionary with document_type, confidence, and reasoning
        """
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        # Truncate text if too long
        text_sample = document_text[:3000] if len(document_text) > 3000 else document_text
        
        prompt = f"""Analyze the following document and classify it as one of these four types:
1. INVOICE - A bill or invoice for goods/services (includes purchase invoices, sales invoices, tax invoices, proforma invoices, etc.)
2. LEASE - A lease agreement for property, equipment, or assets
3. NDA - A Non-Disclosure Agreement (also known as Confidentiality Agreement)
4. CONTRACT - A general contract or agreement (service agreement, employment contract, etc.)

DOCUMENT TEXT (sample):
{text_sample}

CLASSIFICATION GUIDELINES:
- If the document contains invoice number, bill number, itemized charges, tax details, GST/VAT, or payment due information → classify as INVOICE
- If the document discusses rental/lease terms, lessor/lessee, rental payments → classify as LEASE
- If the document is about confidentiality, non-disclosure, protecting information → classify as NDA
- For other agreements, service contracts, employment contracts → classify as CONTRACT

Return your response in JSON format:
{{
    "document_type": "INVOICE" | "LEASE" | "NDA" | "CONTRACT",
    "confidence": "HIGH" | "MEDIUM" | "LOW",
    "reasoning": "Brief explanation of why this classification was chosen"
}}"""
        
        response = llm.invoke([
            SystemMessage(content="You are a document classification expert. Return only valid JSON."),
            HumanMessage(content=prompt)
        ])
        
        try:
            # Try to parse JSON from response
            content = response.content
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            result = json.loads(content.strip())
            doc_type = result.get("document_type", "CONTRACT").upper()
            if doc_type not in ["INVOICE", "LEASE", "NDA", "CONTRACT"]:
                doc_type = "CONTRACT"
            
            return {
                "document_type": doc_type,
                "confidence": result.get("confidence", "MEDIUM"),
                "reasoning": result.get("reasoning", "Document analyzed and classified")
            }
        except json.JSONDecodeError:
            # Fallback to keyword-based classification
            text_lower = document_text.lower()
            # Check for invoice keywords first
            if any(kw in text_lower for kw in ["invoice", "bill to", "invoice number", "inv no", "bill no", "tax invoice", "proforma", "gst", "vat", "subtotal", "total due", "amount due", "payment due"]):
                return {"document_type": "INVOICE", "confidence": "MEDIUM", "reasoning": "Invoice keywords detected"}
            elif any(kw in text_lower for kw in ["non-disclosure", "nondisclosure", "confidentiality agreement"]):
                return {"document_type": "NDA", "confidence": "MEDIUM", "reasoning": "NDA keywords detected"}
            elif any(kw in text_lower for kw in ["lease agreement", "lessor", "lessee", "rental"]):
                return {"document_type": "LEASE", "confidence": "MEDIUM", "reasoning": "Lease keywords detected"}
            else:
                return {"document_type": "CONTRACT", "confidence": "LOW", "reasoning": "Default classification"}
    
    @tool
    def extract_lease_data(document_text: str) -> Dict[str, Any]:
        """
        Extract data from a LEASE document.
        
        Args:
            document_text: The text content of the lease document
            
        Returns:
            Dictionary with extracted lease data
        """
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        prompt = _create_extraction_prompt("LEASE", document_text)
        
        response = llm.invoke([
            SystemMessage(content=_get_extraction_system_prompt()),
            HumanMessage(content=prompt)
        ])
        
        return _parse_extraction_response(response.content)
    
    @tool
    def extract_nda_data(document_text: str) -> Dict[str, Any]:
        """
        Extract data from an NDA document.
        
        Args:
            document_text: The text content of the NDA document
            
        Returns:
            Dictionary with extracted NDA data
        """
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        prompt = _create_extraction_prompt("NDA", document_text)
        
        response = llm.invoke([
            SystemMessage(content=_get_extraction_system_prompt()),
            HumanMessage(content=prompt)
        ])
        
        return _parse_extraction_response(response.content)
    
    @tool
    def extract_contract_data(document_text: str) -> Dict[str, Any]:
        """
        Extract data from a CONTRACT document.
        
        Args:
            document_text: The text content of the contract document
            
        Returns:
            Dictionary with extracted contract data
        """
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        prompt = _create_extraction_prompt("CONTRACT", document_text)
        
        response = llm.invoke([
            SystemMessage(content=_get_extraction_system_prompt()),
            HumanMessage(content=prompt)
        ])
        
        return _parse_extraction_response(response.content)
    
    @tool
    def extract_invoice_data(document_text: str) -> Dict[str, Any]:
        """
        Extract data from an INVOICE document (any type of invoice).
        
        Args:
            document_text: The text content of the invoice document
            
        Returns:
            Dictionary with extracted invoice data
        """
        from langchain_openai import ChatOpenAI
        
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        prompt = _create_invoice_extraction_prompt(document_text)
        
        response = llm.invoke([
            SystemMessage(content=_get_invoice_extraction_system_prompt()),
            HumanMessage(content=prompt)
        ])
        
        return _parse_extraction_response(response.content)
    
    @tool
    def calculate_risk_score(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate risk score based on extracted data.
        
        Args:
            extracted_data: The extracted contract/invoice data
            
        Returns:
            Risk score information
        """
        risk_factors = []
        risk_score = 0
        max_risk = 100
        
        doc_type = extracted_data.get("document_type", "CONTRACT")
        
        # Missing Document Type
        if not doc_type:
            risk_score += 5
            risk_factors.append({"factor": "Missing document type", "severity": "Low", "impact": 5})
        
        # Different risk calculations for INVOICE vs other documents
        if doc_type == "INVOICE":
            # Invoice-specific risk factors
            parties = extracted_data.get("party_names", {})
            vendor = parties.get("vendor") or parties.get("party_1")
            customer = parties.get("customer") or parties.get("party_2")
            
            if not vendor and not customer:
                risk_score += 15
                risk_factors.append({"factor": "Missing vendor/customer information", "severity": "High", "impact": 15})
            
            # Check invoice number
            doc_ids = extracted_data.get("document_ids", {})
            invoice_id = doc_ids.get("invoice_id") or doc_ids.get("invoice_number")
            if not invoice_id:
                risk_score += 10
                risk_factors.append({"factor": "Missing invoice number", "severity": "Medium", "impact": 10})
            
            # Check dates
            dates = extracted_data.get("dates", {})
            invoice_date = dates.get("invoice_date") or extracted_data.get("start_date")
            if not invoice_date:
                risk_score += 10
                risk_factors.append({"factor": "Missing invoice date", "severity": "Medium", "impact": 10})
            
            due_date = dates.get("due_date") or extracted_data.get("due_date")
            if not due_date:
                risk_score += 15
                risk_factors.append({"factor": "Missing payment due date", "severity": "High", "impact": 15})
            
            # Check amounts
            amounts = extracted_data.get("amounts", {})
            total_amount = amounts.get("total") or amounts.get("amount_due") or extracted_data.get("amount")
            if not total_amount:
                risk_score += 20
                risk_factors.append({"factor": "Missing total amount", "severity": "High", "impact": 20})
            
            # Check line items
            line_items = extracted_data.get("line_items", [])
            if not line_items or len(line_items) == 0:
                risk_score += 5
                risk_factors.append({"factor": "No line items extracted", "severity": "Low", "impact": 5})
            
            # Check currency
            if not extracted_data.get("currency"):
                risk_score += 5
                risk_factors.append({"factor": "Missing currency information", "severity": "Low", "impact": 5})
            
            # Note: Frequency defaults to "1" (one-time payment) if not mentioned, so it's not flagged as missing
        else:
            # Contract/NDA/Lease risk factors
            parties = extracted_data.get("party_names", {})
            if not parties.get("party_1") and not parties.get("party_2"):
                risk_score += 15
                risk_factors.append({"factor": "Missing party information", "severity": "High", "impact": 15})
            
            # Missing Dates
            if not extracted_data.get("start_date"):
                risk_score += 10
                risk_factors.append({"factor": "Missing start date", "severity": "High", "impact": 10})
            
            due_date_missing = not extracted_data.get("due_date")
            if due_date_missing:
                risk_score += 20
                risk_factors.append({"factor": "Missing due date", "severity": "High", "impact": 20})
            
            # Missing Payment Information
            amount_missing = not extracted_data.get("amount")
            if amount_missing:
                risk_score += 20
                risk_factors.append({"factor": "Missing payment amount", "severity": "High", "impact": 20})
            
            # Combined High Risk
            if amount_missing and due_date_missing:
                risk_score += 15
                risk_factors.append({"factor": "Missing both payment amount and due date (Critical)", "severity": "High", "impact": 15})
            
            # Note: Frequency defaults to "1" (one-time payment) if not mentioned, so it's not flagged as missing
        
        # Compliance Violations (for all document types)
        compliance_violation = extracted_data.get("rules_and_compliance_violation", "")
        if compliance_violation and compliance_violation.strip().lower() != "no violation of rules and compliance":
            risk_score += 20
            risk_factors.append({"factor": "Compliance violations detected", "severity": "High", "impact": 20})
        
        # PRIORITY CHECK: Due Date and Amount are critical attributes
        # Check if due_date and amount are missing (handle both INVOICE and other document types)
        due_date_missing = False
        amount_missing = False
        
        if doc_type == "INVOICE":
            dates = extracted_data.get("dates", {})
            due_date_missing = not (dates.get("due_date") or extracted_data.get("due_date"))
            amounts = extracted_data.get("amounts", {})
            amount_missing = not (amounts.get("total") or amounts.get("amount_due") or extracted_data.get("amount"))
        else:
            due_date_missing = not extracted_data.get("due_date")
            amount_missing = not extracted_data.get("amount")
        
        # Apply priority rules: Both missing = High risk (>=60), One missing = Medium risk (>=30)
        if due_date_missing and amount_missing:
            # Both critical attributes missing - ensure High risk minimum
            if risk_score < 60:
                risk_score = 60
                risk_factors.append({"factor": "Priority: Both due date and amount missing - High risk enforced", "severity": "High", "impact": 0})
        elif due_date_missing or amount_missing:
            # One critical attribute missing - ensure Medium risk minimum
            if risk_score < 30:
                risk_score = 30
                risk_factors.append({"factor": "Priority: One critical attribute (due date or amount) missing - Medium risk enforced", "severity": "Medium", "impact": 0})
        
        # Cap risk score
        risk_score = min(risk_score, max_risk)
        
        # Determine risk level
        if risk_score < 30:
            risk_level, risk_category = "Low", "🟢 Low Risk"
        elif risk_score < 60:
            risk_level, risk_category = "Medium", "🟡 Medium Risk"
        elif risk_score < 80:
            risk_level, risk_category = "High", "🟠 High Risk"
        else:
            risk_level, risk_category = "Critical", "🔴 Critical Risk"
        
        return {
            "score": risk_score,
            "level": risk_level,
            "category": risk_category,
            "risk_factors": risk_factors
        }
    
    return [classify_document, extract_lease_data, extract_nda_data, extract_contract_data, extract_invoice_data, calculate_risk_score]


# ============== Helper Functions ==============

def _get_extraction_system_prompt() -> str:
    """Get the system prompt for extraction."""
    return """You are an AI Contract Document Extraction Engine.
You MUST extract ALL relevant contract details with high precision and zero hallucinations.

EXTRACTION RULES:
1. If any data is missing or not present → return null.
2. NEVER hallucinate or invent contract clauses.
3. Preserve original clause wording exactly.
4. Convert all dates to ISO format: YYYY-MM-DD.
5. CRITICAL: Preserve ALL decimal places in amounts - NEVER round (e.g., 12688.76 stays 12688.76, NOT 12689).
6. Return EXACT JSON — no explanation, no markdown, no notes.
7. CRITICAL: Extract party names from the document header, "PARTIES" section, or signature block."""


def _get_invoice_extraction_system_prompt() -> str:
    """Get the system prompt for invoice extraction."""
    return """You are an AI Invoice Data Extraction Engine.
You MUST extract ALL relevant invoice details with high precision and zero hallucinations.

EXTRACTION RULES:
1. If any data is missing or not present → return null or empty string.
2. NEVER hallucinate or invent invoice details.
3. Extract exact amounts, dates, and identifiers as they appear.
4. CRITICAL: Preserve ALL decimal places in amounts - NEVER round (e.g., 12688.76 must stay 12688.76, NOT 12689).
5. Convert all dates to ISO format: YYYY-MM-DD.
6. Return EXACT JSON — no explanation, no markdown, no notes.
7. Extract all tax details (GST, VAT, CGST, SGST, IGST, etc.) if present.
8. Parse line items with description, quantity, rate, and amount.
9. CRITICAL: Identify vendor/supplier and customer/buyer accurately."""

def _create_extraction_prompt(doc_type: str, document_text: str) -> str:
    """Create extraction prompt for document type."""
    return f"""Analyze the following {doc_type} document and extract the following information:

DOCUMENT TEXT:
{document_text}

REQUIRED OUTPUT FORMAT (STRICT JSON):
{{
  "document_type": "{doc_type}",
  "party_names": {{
    "party_1": "",
    "party_2": "",
    "additional_parties": []
  }},
  "start_date": "",
  "due_date": "",
  "amount": "",
  "frequency": "",
  "account_type": "",
  "document_ids": {{
    "invoice_id": "",
    "contract_id": "",
    "agreement_id": "",
    "reference_id": "",
    "document_number": "",
    "lease_id": "",
    "nda_id": "",
    "po_number": "",
    "project_id": "",
    "other_ids": []
  }},
  "rules_and_compliance_violation": "",
  "risk_score": null
}}

EXTRACTION INSTRUCTIONS:
1. Document Type: Set to "{doc_type}"
2. Party Names: Extract all party names from document header, "PARTIES" section, or signature block
3. Start Date: Extract the effective/start date. Format as YYYY-MM-DD.
4. Due Date: Extract payment due date or deadline. Format as YYYY-MM-DD.
5. Amount: Extract the payment amount EXACTLY with all decimals (e.g., 12688.76 NOT 12689). Do NOT round. Do NOT extract percentages as amounts.
6. Frequency: Extract payment frequency (e.g., "Monthly", "Quarterly", "Annual")
7. Account Type: Extract account type if mentioned
8. Document IDs (Extract ALL identification numbers):
   - Look for: Contract ID, Agreement Number, Reference Number, Document Number, Lease ID, NDA Number
   - Look for: Invoice Number, PO Number, Project ID, File Number
   - Extract ANY alphanumeric identifier that identifies this document
   - Common labels: "Contract No", "Agreement #", "Ref No", "Doc #", "ID", "Number"
9. Rules and Compliance Violation: Analyze for violations. If none found, return "No violation of rules and compliance"

Return ONLY valid JSON."""


def _create_invoice_extraction_prompt(document_text: str) -> str:
    """Create extraction prompt specifically for invoices."""
    return f"""Analyze the following INVOICE document and extract ALL relevant information:

DOCUMENT TEXT:
{document_text}

REQUIRED OUTPUT FORMAT (STRICT JSON):
{{
  "document_type": "INVOICE",
  "invoice_type": "",
  "party_names": {{
    "vendor": "",
    "vendor_address": "",
    "vendor_gstin": "",
    "vendor_pan": "",
    "customer": "",
    "customer_address": "",
    "customer_gstin": "",
    "party_1": "",
    "party_2": "",
    "additional_parties": []
  }},
  "document_ids": {{
    "invoice_id": "",
    "invoice_number": "",
    "bill_number": "",
    "po_number": "",
    "order_number": "",
    "reference_id": "",
    "document_number": "",
    "quotation_number": "",
    "receipt_number": "",
    "transaction_id": "",
    "other_ids": []
  }},
  "dates": {{
    "invoice_date": "",
    "due_date": "",
    "supply_date": "",
    "delivery_date": ""
  }},
  "start_date": "",
  "due_date": "",
  "amounts": {{
    "subtotal": "",
    "discount": "",
    "taxable_amount": "",
    "cgst": "",
    "sgst": "",
    "igst": "",
    "gst": "",
    "vat": "",
    "tax_amount": "",
    "total": "",
    "amount_due": "",
    "amount_paid": "",
    "balance_due": ""
  }},
  "amount": "",
  "amount_explanation": "",
  "currency": "",
  "line_items": [
    {{
      "description": "",
      "hsn_sac_code": "",
      "quantity": "",
      "unit": "",
      "rate": "",
      "amount": "",
      "tax_rate": ""
    }}
  ],
  "payment_details": {{
    "payment_terms": "",
    "payment_method": "",
    "bank_name": "",
    "account_holder_name": "",
    "account_number": "",
    "account_number_iban": "",
    "ifsc_code": "",
    "swift_code": "",
    "branch": "",
    "bank_address": "",
    "upi_id": ""
  }},
  "frequency": "",
  "account_type": "Accounts Payable",
  "notes": "",
  "rules_and_compliance_violation": "",
  "risk_score": null
}}

EXTRACTION INSTRUCTIONS:
1. Invoice Type: Identify type (Tax Invoice, Proforma, Commercial, Construction, Lease, Service, etc.)
2. Vendor/Supplier: Extract company name issuing the invoice (look for "FROM", "BILLED BY", "VENDOR", "SUPPLIER", "SELLER", company name at top)
   - Vendor Address: Extract vendor address carefully. Look for address in these locations:
     * FOOTER SECTION: Look at the bottom of the document, after signature blocks, in contact information sections
     * Look for addresses that include: Office number, Floor, Building name, Street, City, Country, PO Box
     * Look for addresses that appear with contact details like Tel, Fax, Email, Phone
     * Look for addresses BELOW red lines, separators, or horizontal lines
     * Look in a separate "From" section if present
     * The vendor address is typically the company's registered/business address, not the bank address
   - CRITICAL: If an address contains the word "bank" (case-insensitive), it is a BANK ADDRESS, NOT a vendor address. Do NOT extract it as vendor_address.
   - CRITICAL: Vendor address often appears in the footer with contact information (Tel, Fax, Email, Phone numbers). Extract the full address including office number, building, street, city, country, and PO Box if present.
   - Example: "Risin Ventures W.L.L, Office No 12, 3rd Floor, Al Reem Tower, West Bay, Doha, Qatar, PO Box- 4969" would be a vendor address
3. Customer/Buyer: Extract company/person being billed (look for "TO", "BILL TO", "BILLED TO", "CUSTOMER", "BUYER")
   - Customer Address: Extract customer address from "Bill To", "Ship To", or "Customer" sections
   - CRITICAL: If an address contains the word "bank" (case-insensitive), it is a BANK ADDRESS, NOT a customer address. Do NOT extract it as customer_address.
4. Document IDs (CRITICAL - Extract ALL of these if present):
   - invoice_id: Main invoice identifier. Look for:
     * "INVOICE ID", "INVOICE NO", "INVOICE #", "INV NO", "INV #", "INVOICE NUMBER"
     * "QUOTE NUMBER", "QUOTATION NUMBER", "QUOTE NO", "QUO #", "QUOTATION REF NO", "QUOTATION REF"
     * CRITICAL: Extract the ACTUAL VALUE/NUMBER, NOT the label. 
       - If you see "Invoice No: INV-123", extract "INV-123" (NOT "Invoice No")
       - If you see "Quote No: ENT-20251217-10", extract "ENT-20251217-10" (NOT "Quote No")
       - If you see "Quote No ENT-20251217-10" (without colon), extract "ENT-20251217-10"
       - Look for the alphanumeric value that appears AFTER or NEXT TO labels like "Invoice No:", "Quote No:", etc.
       - The value is typically in the same row/box as the label, or in an adjacent cell/field
     * IMPORTANT: If you find a "Quote Number" or "Quotation Number" label, ALSO check the NEXT box/field or adjacent area for the actual number or alphanumeric value - this is often the actual invoice/quote number
     * If quotation_number is found and it's the same as invoice number, extract it ONLY ONCE (prefer invoice_id/invoice_number, not quotation_number)
     * NEVER extract labels like "Quote No", "Invoice No", "Quotation Number" - only extract the actual alphanumeric identifier
   - invoice_number: Same as invoice_id if not separately specified. Extract the ACTUAL VALUE, not the label. If invoice and quote numbers are identical, extract only once
   - bill_number: Bill identifier (look for "BILL NO", "BILL #", "BILL NUMBER")
   - po_number: Purchase order number (look for "PO", "P.O.", "PURCHASE ORDER", "PO NUMBER", "PO #")
   - order_number: Order reference (look for "ORDER NO", "ORDER #", "ORDER NUMBER", "ORD NO")
   - reference_id: Any reference number (look for "REF", "REF NO", "REFERENCE", "REF #")
   - document_number: Generic document number (look for "DOC NO", "DOCUMENT NO", "DOC #")
   - quotation_number: Quote reference (look for "QUOTE", "QUOTATION", "QUOTE NO", "QUO #", "QUOTATION REF NO", "QUOTATION REF")
     * CRITICAL: Extract the ACTUAL VALUE/NUMBER, NOT the label. 
       - If you see "Quote No: ENT-20251217-10", extract "ENT-20251217-10" (NOT "Quote No")
       - If you see "Quote No ENT-20251217-10" (without colon), extract "ENT-20251217-10"
       - Look for the alphanumeric value that appears AFTER or NEXT TO labels like "Quote No:", "Quote Number:", "Quotation No:", etc.
       - The value is typically in the same row/box as the label, or in an adjacent cell/field
       - NEVER extract labels like "Quote No", "Quotation Number" - only extract the actual alphanumeric identifier
     * CRITICAL: If quotation_number is found, ALSO check adjacent boxes/fields for numbers or alphanumeric values that might be the invoice number
     * IMPORTANT: If quotation_number is the SAME as invoice_id/invoice_number (e.g., "Invoice: EST-007471; Quote: EST-007471"), extract it ONLY ONCE - do NOT duplicate. Prefer storing it in invoice_id/invoice_number and leave quotation_number empty
     * Only extract quotation_number if it's DIFFERENT from the invoice number
   - receipt_number: Receipt identifier (look for "RECEIPT", "RECEIPT NO", "REC #")
   - transaction_id: Transaction reference (look for "TRANSACTION", "TXN", "TRANS ID")
   - other_ids: Any other identifiers found in the document
   NOTE: The primary document identifier should go in both invoice_id AND invoice_number. If quotation_number is the primary identifier, use it for both invoice_id and invoice_number as well.
5. Dates: Extract invoice date, due date, delivery date as YYYY-MM-DD (be flexible with date formats)
6. Amounts and Currency: Extract ALL monetary values including taxes
   - Look for: Subtotal, Discount, Taxable Amount, Tax, CGST, SGST, IGST, GST, VAT, Total, Grand Total, Amount Due, Balance
   - CRITICAL: Extract amounts EXACTLY as shown - preserve ALL decimal places (e.g., 12688.76 NOT 12689)
   - Strip currency symbols but keep the complete numeric value with decimals
   - IMPORTANT: Detect currency from:
     * Currency symbols: $, ₹, €, £, ¥, ﷼, etc.
     * Currency codes: USD, INR, EUR, GBP, AED, CAD, AUD, QAR, SAR, KWD, BHD, OMR, JPY, CNY, SGD, MYR, THB, CHF, etc.
     * Currency words: Dollars, Rupees, Euros, Pounds, Dirhams, Riyals, Yen, Yuan, Francs, etc.
     * "Currency: XXX" patterns (e.g., "Currency: QAR" means Qatari Riyal)
     * "TOTAL XXX" patterns (e.g., "TOTAL QAR 33,480.00" means currency is QAR)
     * Country/city names to infer currency:
       - Qatar/Doha → QAR (Qatari Riyal)
       - Saudi Arabia/Riyadh → SAR (Saudi Riyal)
       - UAE/Dubai → AED (UAE Dirham)
       - Kuwait → KWD (Kuwaiti Dinar)
       - Bahrain → BHD (Bahraini Dinar)
       - Oman/Muscat → OMR (Omani Rial)
       - India → INR, USA → USD, UK → GBP, etc.
     * If currency symbol is missing due to OCR, look for currency mentioned ANYWHERE in the document
   - Set "currency" field with the detected 3-letter currency code (USD, INR, EUR, QAR, SAR, etc.)
7. Line Items: Extract EACH product/service listed with:
   - Description/Item name
   - HSN/SAC code if present
   - Quantity
   - Unit (pcs, kg, hours, etc.)
   - Rate/Unit price
   - Amount/Total for that line
   - Tax rate (if shown per item)
8. Tax Details: Extract GST, VAT, CGST, SGST, IGST as applicable (may be shown as percentage or amount)
9. Payment Details: Extract ALL bank and account details:
   - Account Holder Name: Name of the account holder (look for "Account Name", "Name", "Beneficiary Name", "Payee Name", "Payment in the name of")
   - Account Number: For Indian accounts, extract account number (look for "Account No", "A/C No", "Account Number", "A/C Number")
   - Account Number/IBAN: For international accounts, extract IBAN or account number (look for "IBAN", "Account No/IBAN", "Account Number", "A/C No")
   - IFSC Code: For Indian accounts, extract IFSC code (look for "IFSC", "IFSC Code", "IFSC CODE")
   - SWIFT Code: For international accounts, extract SWIFT code (look for "SWIFT", "SWIFT Code", "BIC", "BIC Code")
   - Branch: Extract branch name/location (look for "Branch", "Branch Name", "Branch Location")
   - Bank Name: Extract bank name (look for bank name near account details, payment instructions)
   - Bank Address: Extract full bank address. This is typically the address that appears near bank account details, payment instructions, or below account information. 
     * Look for addresses that contain bank name, branch name, or are clearly associated with banking/payment information
     * Bank addresses often appear after account numbers, IBAN, SWIFT codes, or in payment instruction sections
     * Example: "Qatar National Bank, Shoumoukh Corporate Branch, Doha, Qatar" would be a bank address
   - Payment Terms: Extract payment terms if mentioned
   - Payment Method: Extract payment method if mentioned
   - UPI ID: Extract UPI ID if present (for Indian payments)
10. For party_1, use vendor name; for party_2, use customer name
11. For amount field, use the total/grand total/amount due (the final payable amount)
12. amount_explanation: Provide a brief one-line explanation of how the total amount was derived from the document.
   - If taxes are mentioned as extra (e.g., "GST 18% Extra"), explain: "Base amount X + 18% GST = Total Y"
   - If subtotal + tax breakdown is shown, explain: "Subtotal X + Tax Y = Total Z"
   - If total is directly stated without calculation, explain: "Total as stated in document"
   - Examples:
     * "56,450.00 + 18% GST (10,161.00) = 66,611.00"
     * "Subtotal 50,000 + CGST 9% + SGST 9% = 59,000"
     * "Grand Total as stated in invoice"
13. For start_date, use invoice_date; for due_date, use payment due date
13. If any field is not found in the document, leave it as empty string ""
14. Extract ALL line items, don't skip any
15. Be flexible with terminology - different invoices use different terms for the same fields

IMPORTANT NOTES:
- Construction invoices may have labor, materials, equipment as line items
- Service invoices may have service descriptions and hourly rates
- Some invoices show tax separately, some include it in total
- Invoice numbers can be in various formats: alphanumeric, with prefixes, with dashes, etc.
- Dates can be in multiple formats: DD/MM/YYYY, MM/DD/YYYY, YYYY-MM-DD, etc. - convert all to YYYY-MM-DD
- Amounts may have currency symbols ($, ₹, €, etc.) - extract EXACT numeric value with ALL decimals (12688.76 NOT 12689)
- NEVER round amounts - keep them exactly as shown in the document
- Look carefully at the document structure to identify vendor vs customer
- ADDRESS EXTRACTION CRITICAL RULES:
  * Vendor address: 
    - Look in FOOTER sections at the bottom of the document
    - Look BELOW signature blocks, after "Authorized Signatory", "For [Company Name]", or similar signature text
    - Look for addresses that appear with contact information (Tel, Fax, Email, Phone numbers)
    - Look for addresses that include: Office number, Floor number, Building name, Street/Area, City, Country, PO Box
    - Look BELOW red lines, separators, or horizontal lines
    - Typically appears after company name in footer or in a separate "From" section
    - Example format: "Company Name, Office No X, Floor Y, Building Name, Area, City, Country, PO Box- Z"
    - Example: "Risin Ventures W.L.L, Office No 12, 3rd Floor, Al Reem Tower, West Bay, Doha, Qatar, PO Box- 4969"
    - IMPORTANT: If you see multiple addresses, the one with contact details (Tel, Fax, Email) in the footer is usually the vendor address
  * Customer address: Look in "Bill To", "Ship To", or "Customer" sections
  * Bank address: Any address containing "bank" (case-insensitive) or appearing near payment/account details should go to bank_address, NOT vendor_address or customer_address
  * If an address contains words like "Bank", "Branch", "IBAN", "SWIFT", "Account", it's likely a bank address
  * Bank addresses often appear in payment instruction sections, near account numbers, or below payment details
  * CRITICAL: The vendor address is the company's business/registered address (usually in footer with contact info), NOT the bank address
- OCR ISSUES: Currency symbols ($, ₹, €, £, ¥) may be missing or misread - look for currency mentioned ANYWHERE in document (text, headers, footers)
- If currency symbol is missing, search for currency codes (QAR, SAR, USD, INR, etc.) or words (Riyal, Dollar, Rupee, etc.)
- Look for patterns like "Currency: QAR", "TOTAL QAR", "Amount in QAR", etc.
- Common OCR errors: $ → S, ₹ → Rs, € → C, £ → L - be flexible in detection
- For Gulf currencies (QAR, SAR, AED, KWD, BHD, OMR), look for country/city names (Qatar, Saudi, Dubai, etc.)

Return ONLY valid JSON."""


def _parse_extraction_response(content: str) -> Dict[str, Any]:
    """Parse extraction response from LLM."""
    try:
        # Handle markdown code blocks
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        return json.loads(content.strip())
    except json.JSONDecodeError:
        return {
            "document_type": "CONTRACT",
            "party_names": {"party_1": "", "party_2": "", "additional_parties": []},
            "start_date": "",
            "due_date": "",
            "amount": "",
            "frequency": "",
            "account_type": "",
            "document_ids": {},
            "rules_and_compliance_violation": "No violation of rules and compliance",
            "error": "Failed to parse extraction response"
        }


# ============== Graph Nodes ==============

def parse_document_node(state: ExtractionState) -> ExtractionState:
    """Node: Parse the document and extract text."""
    print("\n[AGENT NODE] Parsing document...")
    
    try:
        # Use the use_gcs_vision setting from state
        use_gcs = state.get("use_gcs_vision", False)
        parser = DocumentParser(use_gcs_vision=use_gcs)
        
        if state.get("file_path"):
            # For hybrid documents, always try OCR to detect OCR text
            # The parser will intelligently combine native text with OCR text
            document_text, page_map = parser.parse_with_pages(
                state["file_path"], 
                use_ocr=True  # Always enable OCR detection for hybrid documents
            )
            state["document_text"] = document_text
            state["page_map"] = page_map
            state["status"] = "parsing_complete"
            
            state["messages"] = [
                AIMessage(content=f"Document parsed successfully. Extracted {len(document_text)} characters from {len(page_map)} pages.")
            ]
        elif state.get("document_text"):
            state["page_map"] = {}
            state["status"] = "parsing_complete"
            state["messages"] = [
                AIMessage(content="Using provided document text directly.")
            ]
        else:
            raise ValueError("No file path or document text provided")
            
    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        state["messages"] = [AIMessage(content=f"Error parsing document: {str(e)}")]
    
    return state


def classify_document_node(state: ExtractionState) -> ExtractionState:
    """Node: Classify the document type."""
    print("\n[AGENT NODE] Classifying document type...")
    
    if state.get("error"):
        return state
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        tools = create_extraction_tools(api_key)
        classify_tool = tools[0]  # classify_document tool
        
        result = classify_tool.invoke({"document_text": state["document_text"]})
        
        state["document_type"] = result["document_type"]
        state["classification_confidence"] = result["confidence"]
        state["classification_reasoning"] = result["reasoning"]
        state["status"] = "classified"
        
        state["messages"] = [
            AIMessage(content=f"Document classified as {result['document_type']} with {result['confidence']} confidence. Reason: {result['reasoning']}")
        ]
        
        print(f"    → Document Type: {result['document_type']} (Confidence: {result['confidence']})")
        
    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        state["messages"] = [AIMessage(content=f"Error classifying document: {str(e)}")]
    
    return state


def extract_data_node(state: ExtractionState) -> ExtractionState:
    """Node: Extract data based on document type."""
    print(f"\n[AGENT NODE] Extracting data using {state.get('document_type', 'CONTRACT')} extractor...")
    
    if state.get("error"):
        return state
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        tools = create_extraction_tools(api_key)
        
        doc_type = state.get("document_type", "CONTRACT")
        
        # Select the appropriate extraction tool
        # Tools order: [classify_document, extract_lease_data, extract_nda_data, extract_contract_data, extract_invoice_data, calculate_risk_score]
        if doc_type == "LEASE":
            extract_tool = tools[1]  # extract_lease_data
        elif doc_type == "NDA":
            extract_tool = tools[2]  # extract_nda_data
        elif doc_type == "INVOICE":
            extract_tool = tools[4]  # extract_invoice_data
        else:
            extract_tool = tools[3]  # extract_contract_data
        
        result = extract_tool.invoke({"document_text": state["document_text"]})
        
        state["extracted_data"] = result
        state["status"] = "extracted"
        
        # Count extracted fields
        non_empty = sum(1 for k, v in result.items() if v and v != "null" and v != {})
        
        state["messages"] = [
            AIMessage(content=f"Extracted {non_empty} fields from {doc_type} document.")
        ]
        
        print(f"    → Extracted {non_empty} fields")
        
    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        state["messages"] = [AIMessage(content=f"Error extracting data: {str(e)}")]
    
    return state


def enhance_data_node(state: ExtractionState) -> ExtractionState:
    """Node: Enhance extracted data with additional processing."""
    print("\n[AGENT NODE] Enhancing extracted data...")
    
    if state.get("error"):
        return state
    
    try:
        extracted_data = state.get("extracted_data", {})
        doc_type = state.get("document_type", "CONTRACT")
        
        # For invoices, flatten the nested structure for compatibility
        if doc_type == "INVOICE":
            extracted_data = _normalize_invoice_data(extracted_data)
        
        # Extract and normalize currency
        extracted_data = _extract_currency(extracted_data, state.get("document_text", ""))
        
        # Calculate per-period amount
        extracted_data = _calculate_period_amount(extracted_data)
        
        # Assign account type based on content analysis
        document_text = state.get("document_text", "")
        extracted_data = _assign_account_type(extracted_data, doc_type, document_text)
        
        state["extracted_data"] = extracted_data
        state["status"] = "enhanced"
        
        state["messages"] = [
            AIMessage(content="Data enhanced with currency normalization and period calculations.")
        ]
        
    except Exception as e:
        # Don't fail on enhancement errors, just log
        print(f"    → Warning: Enhancement error: {str(e)}")
        state["messages"] = [AIMessage(content=f"Enhancement warning: {str(e)}")]
    
    return state


def calculate_risk_node(state: ExtractionState) -> ExtractionState:
    """Node: Calculate risk score."""
    print("\n[AGENT NODE] Calculating risk score...")
    
    if state.get("error"):
        return state
    
    try:
        api_key = os.getenv('OPENAI_API_KEY')
        tools = create_extraction_tools(api_key)
        # Tools order: [classify_document, extract_lease_data, extract_nda_data, extract_contract_data, extract_invoice_data, calculate_risk_score]
        risk_tool = tools[5]  # calculate_risk_score (was incorrectly set to 4, which was extract_invoice_data)
        
        result = risk_tool.invoke({"extracted_data": state.get("extracted_data", {})})
        
        state["extracted_data"]["risk_score"] = result
        state["status"] = "completed"
        
        state["messages"] = [
            AIMessage(content=f"Risk score calculated: {result['score']} ({result['level']})")
        ]
        
        print(f"    → Risk Score: {result['score']} ({result['level']})")
        
    except Exception as e:
        # Don't fail on risk calculation errors
        print(f"    → Warning: Risk calculation error: {str(e)}")
        state["status"] = "completed"
        state["messages"] = [AIMessage(content=f"Risk calculation warning: {str(e)}")]
    
    return state


def _find_page_references(extracted_data: Dict[str, Any], page_map: Dict[int, str]) -> Dict[str, Any]:
    """
    Find which page each extracted field came from by searching page_map.
    
    Args:
        extracted_data: The extracted data
        page_map: Dictionary mapping page numbers to page text
        
    Returns:
        Dictionary with page references for each field
    """
    if not page_map:
        return {}
    
    references = {}
    
    # Helper function to find which page contains a value
    def find_page_for_value(value, field_name=""):
        if not value or not isinstance(value, str) or len(value.strip()) == 0:
            return None
        
        # Clean value for searching
        search_value = str(value).strip()
        if len(search_value) < 2:  # Skip very short values
            return None
        
        # For dates, try multiple format variations
        if field_name in ["start_date", "due_date", "invoice_date", "delivery_date", "supply_date", "effective_date", "end_date"]:
            try:
                for page_num, page_text in page_map.items():
                    # Search for the exact date
                    if search_value in page_text:
                        return page_num
                    
                    # Try parsing the date and searching for different formats
                    if '-' in search_value:
                        parts = search_value.split('-')
                        if len(parts) == 3:
                            year, month, day = parts[0], parts[1], parts[2]
                            
                            # Try multiple date format variations
                            date_variations = [
                                f"{month}/{day}/{year}",  # MM/DD/YYYY
                                f"{day}/{month}/{year}",  # DD/MM/YYYY
                                f"{day}-{month}-{year}",  # DD-MM-YYYY
                                f"{month}-{day}-{year}",  # MM-DD-YYYY
                                f"{day}.{month}.{year}",  # DD.MM.YYYY
                                f"{month}.{day}.{year}",  # MM.DD.YYYY
                                f"{int(month)}/{int(day)}/{year}",  # M/D/YYYY (no leading zeros)
                                f"{int(day)}/{int(month)}/{year}",  # D/M/YYYY
                                year + month + day,  # YYYYMMDD
                                day + month + year,  # DDMMYYYY
                            ]
                            
                            # Remove leading zeros for more variations
                            month_no_zero = str(int(month))
                            day_no_zero = str(int(day))
                            date_variations.extend([
                                f"{month_no_zero}/{day_no_zero}/{year}",
                                f"{day_no_zero}/{month_no_zero}/{year}",
                                f"{month_no_zero}-{day_no_zero}-{year}",
                                f"{day_no_zero}-{month_no_zero}-{year}",
                            ])
                            
                            for date_var in date_variations:
                                if date_var in page_text:
                                    return page_num
            except:
                # If date parsing fails, just do standard search below
                pass
        
        # For amounts, try with and without decimals, commas, currency symbols
        if field_name == "amount":
            try:
                for page_num, page_text in page_map.items():
                    # Try exact match
                    if search_value in page_text:
                        return page_num
                    
                    # Try with comma formatting and currency symbols
                    try:
                        num_val = float(search_value.replace(',', ''))
                        
                        # Try various formats with 2 decimals
                        formatted = f"{num_val:,.2f}"
                        if formatted in page_text:
                            return page_num
                        
                        # Try with $ symbol
                        if f"${formatted}" in page_text:
                            return page_num
                        
                        # Try with rupee symbol
                        if f"₹{formatted}" in page_text or f"Rs. {formatted}" in page_text:
                            return page_num
                        
                        # Try without decimals if it's a round number
                        if num_val == int(num_val):
                            formatted_int = f"{int(num_val):,}"
                            if formatted_int in page_text or f"${formatted_int}" in page_text:
                                return page_num
                        
                        # Try just the number without formatting
                        if str(num_val) in page_text:
                            return page_num
                    except:
                        pass
            except:
                pass
        
        # Standard search for all other fields
        for page_num, page_text in page_map.items():
            if search_value.lower() in page_text.lower():
                return page_num
        
        return None
    
    # Track document IDs
    doc_ids = extracted_data.get("document_ids", {})
    if isinstance(doc_ids, dict):
        for id_type, id_value in doc_ids.items():
            if id_value:
                page = find_page_for_value(id_value, id_type)
                if page:
                    references[f"document_ids_{id_type}"] = {"page": page}
    
    # Track party names
    party_names = extracted_data.get("party_names", {})
    if isinstance(party_names, dict):
        for party_key, party_value in party_names.items():
            if party_value and not party_key.endswith("_address"):  # Skip addresses
                page = find_page_for_value(party_value, party_key)
                if page:
                    references[f"party_{party_key}"] = {"page": page}
    
    # Track dates - check nested dates structure too
    dates = extracted_data.get("dates", {})
    if isinstance(dates, dict):
        if dates.get("invoice_date") and "start_date" not in references:
            page = find_page_for_value(dates["invoice_date"], "invoice_date")
            if page:
                references["start_date"] = {"page": page}
                references["invoice_date"] = {"page": page}
        if dates.get("due_date") and "due_date" not in references:
            page = find_page_for_value(dates["due_date"], "due_date")
            if page:
                references["due_date"] = {"page": page}
        if dates.get("supply_date"):
            page = find_page_for_value(dates["supply_date"], "supply_date")
            if page:
                references["supply_date"] = {"page": page}
        if dates.get("delivery_date"):
            page = find_page_for_value(dates["delivery_date"], "delivery_date")
            if page:
                references["delivery_date"] = {"page": page}
    
    # Track dates from top level
    if extracted_data.get("start_date") and "start_date" not in references:
        page = find_page_for_value(extracted_data["start_date"], "start_date")
        if page:
            references["start_date"] = {"page": page}
    
    if extracted_data.get("due_date") and "due_date" not in references:
        page = find_page_for_value(extracted_data["due_date"], "due_date")
        if page:
            references["due_date"] = {"page": page}
    
    # Track execution/effective date
    if extracted_data.get("execution_date"):
        page = find_page_for_value(extracted_data["execution_date"], "effective_date")
        if page:
            references["execution_date"] = {"page": page}
            if "start_date" not in references:
                references["start_date"] = {"page": page}
    
    if extracted_data.get("effective_date"):
        page = find_page_for_value(extracted_data["effective_date"], "effective_date")
        if page:
            references["effective_date"] = {"page": page}
    
    # Track amounts - check nested amounts structure too
    amounts = extracted_data.get("amounts", {})
    if isinstance(amounts, dict):
        # Check for total amount in nested structure
        total = amounts.get("total") or amounts.get("amount_due")
        if total:
            amount_str = str(total).replace(",", "")
            page = find_page_for_value(amount_str, "amount")
            if page:
                references["amount"] = {"page": page}
    
    # Track amounts from top level
    if extracted_data.get("amount") and "amount" not in references:
        amount_str = str(extracted_data["amount"]).replace(",", "")
        page = find_page_for_value(amount_str, "amount")
        if page:
            references["amount"] = {"page": page}
    
    # Track frequency
    if extracted_data.get("frequency"):
        page = find_page_for_value(extracted_data["frequency"], "frequency")
        if page:
            references["frequency"] = {"page": page}
        elif references.get("amount"):
            # Frequency usually near payment terms/amount
            references["frequency"] = {"page": references["amount"]["page"]}
    
    # Track currency - search more thoroughly
    if extracted_data.get("currency"):
        currency = extracted_data["currency"]
        page = None
        
        # Try finding currency code or symbol
        for page_num, page_text in page_map.items():
            # Check for currency code (USD, INR, EUR, etc.)
            if currency.upper() in page_text.upper():
                page = page_num
                break
            
            # Check for currency symbol or word
            currency_patterns = {
                "USD": ["$", "USD", "US DOLLAR", "DOLLAR"],
                "INR": ["₹", "INR", "RUPEE", "Rs.", "Rs "],
                "EUR": ["€", "EUR", "EURO"],
                "GBP": ["£", "GBP", "POUND", "STERLING"],
                "AED": ["AED", "DIRHAM", "UAE DIRHAM"],
                "QAR": ["QAR", "QATARI RIYAL", "QATARI RIYALS", "Q.R."],
                "SAR": ["SAR", "SAUDI RIYAL", "SAUDI RIYALS", "﷼"],
                "KWD": ["KWD", "KUWAITI DINAR"],
                "BHD": ["BHD", "BAHRAINI DINAR"],
                "OMR": ["OMR", "OMANI RIAL"],
                "CAD": ["CAD", "C$", "CANADIAN DOLLAR"],
                "AUD": ["AUD", "A$", "AUSTRALIAN DOLLAR"],
                "JPY": ["JPY", "YEN", "¥"],
                "CNY": ["CNY", "RMB", "YUAN", "RENMINBI"],
                "SGD": ["SGD", "S$", "SINGAPORE DOLLAR"],
                "CHF": ["CHF", "SWISS FRANC"],
                "MYR": ["MYR", "RM", "RINGGIT"]
            }
            
            if currency.upper() in currency_patterns:
                for pattern in currency_patterns[currency.upper()]:
                    if pattern in page_text.upper():
                        page = page_num
                        break
                if page:
                    break
        
        if page:
            references["currency"] = {"page": page}
        elif references.get("amount"):
            # If currency not found but amount was found, assume same page
            references["currency"] = {"page": references["amount"]["page"]}
    
    # Track invoice type
    if extracted_data.get("invoice_type"):
        page = find_page_for_value(extracted_data["invoice_type"], "invoice_type")
        if page:
            references["invoice_type"] = {"page": page}
    
    # Track account type
    if extracted_data.get("account_type"):
        page = find_page_for_value(extracted_data["account_type"], "account_type")
        if page:
            references["account_type"] = {"page": page}
    
    # Track payment details
    payment_details = extracted_data.get("payment_details", {})
    if isinstance(payment_details, dict):
        if payment_details.get("payment_terms"):
            page = find_page_for_value(payment_details["payment_terms"], "payment_terms")
            if page:
                references["payment_terms"] = {"page": page}
    
    # Track line items (find first line item description)
    line_items = extracted_data.get("line_items", [])
    if line_items and isinstance(line_items, list) and len(line_items) > 0:
        first_item = line_items[0]
        if isinstance(first_item, dict) and first_item.get("description"):
            page = find_page_for_value(first_item["description"], "line_items")
            if page:
                references["line_items"] = {"page": page}
    
    # Track governing law
    if extracted_data.get("governing_law"):
        page = find_page_for_value(extracted_data["governing_law"], "governing_law")
        if page:
            references["governing_law"] = {"page": page}
    
    # Track confidentiality clause
    if extracted_data.get("confidentiality_clause"):
        clause = extracted_data["confidentiality_clause"]
        if len(clause) > 20:  # Only search if substantial text
            page = find_page_for_value(clause[:100], "confidentiality_clause")
            if page:
                references["confidentiality_clause"] = {"page": page}
    
    # FALLBACK: If document is only 1 page, all extracted fields should reference Page 1
    if len(page_map) == 1:
        single_page = list(page_map.keys())[0]
        
        # Add Page 1 reference to critical fields that are missing it
        critical_fields = [
            "start_date", "due_date", "execution_date", "effective_date",
            "amount", "currency", "frequency"
        ]
        
        for field in critical_fields:
            if field not in references:
                # Check if the field has a value
                field_value = extracted_data.get(field)
                if not field_value:
                    # Check nested structures
                    if field in ["start_date", "due_date"]:
                        dates = extracted_data.get("dates", {})
                        if isinstance(dates, dict):
                            field_value = dates.get(field) or dates.get("invoice_date")
                    elif field == "amount":
                        amounts = extracted_data.get("amounts", {})
                        if isinstance(amounts, dict):
                            field_value = amounts.get("total") or amounts.get("amount_due")
                
                # If field has a value, assign Page 1
                if field_value:
                    references[field] = {"page": single_page}
    
    return references


def finalize_node(state: ExtractionState) -> ExtractionState:
    """Node: Finalize extraction and add metadata."""
    print("\n[AGENT NODE] Finalizing extraction...")
    
    extracted_data = state.get("extracted_data", {})
    
    # Find page references for extracted fields
    page_map = state.get("page_map", {})
    if page_map:
        print(f"    → Finding page references for extracted fields...")
        print(f"    → Page map has {len(page_map)} pages")
        references = _find_page_references(extracted_data, page_map)
        extracted_data["references"] = references
        print(f"    → Found {len(references)} page references:")
        for key, value in references.items():
            print(f"       - {key}: Page {value.get('page', '?')}")
    
    # Add extraction metadata
    extracted_data["_extraction_metadata"] = {
        "agent_version": "langgraph-v1",
        "extraction_method": "agent_based",
        "document_type": state.get("document_type", "CONTRACT"),
        "classification_confidence": state.get("classification_confidence", "UNKNOWN"),
        "status": state.get("status", "unknown"),
        "timestamp": datetime.now().isoformat()
    }
    
    state["extracted_data"] = extracted_data
    
    if state.get("error"):
        state["status"] = "failed"
    else:
        state["status"] = "completed"
    
    print(f"\n[AGENT] Extraction completed with status: {state['status']}")
    
    return state


# ============== Enhancement Helpers ==============

def _extract_currency(extracted_data: Dict[str, Any], document_text: str) -> Dict[str, Any]:
    """Extract and normalize currency from amount and document text.
    
    Supports a comprehensive list of currencies including:
    - Major currencies: USD, EUR, GBP, INR, etc.
    - Gulf currencies: QAR, SAR, AED, KWD, BHD, OMR
    - Asian currencies: JPY, CNY, SGD, MYR, THB, PHP, IDR, VND, KRW, HKD, TWD
    - Other currencies: CHF, SEK, NOK, DKK, PLN, CZK, HUF, ZAR, BRL, MXN, NZD, etc.
    """
    # Comprehensive currency mapping: code -> (keywords, symbols, country/city indicators)
    CURRENCY_MAP = {
        # Gulf/Middle East currencies
        "QAR": {
            "keywords": ["QAR", "QATARI RIYAL", "QATARI RIYALS", "Q.R.", "QR "],
            "symbols": [],
            "locations": ["QATAR", "DOHA", "QATARI"]
        },
        "SAR": {
            "keywords": ["SAR", "SAUDI RIYAL", "SAUDI RIYALS", "S.R.", "SR "],
            "symbols": ["﷼"],
            "locations": ["SAUDI", "SAUDI ARABIA", "RIYADH", "JEDDAH", "MECCA", "MEDINA"]
        },
        "AED": {
            "keywords": ["AED", "DIRHAM", "DIRHAMS", "UAE DIRHAM", "EMIRATI DIRHAM"],
            "symbols": ["د.إ"],
            "locations": ["UAE", "UNITED ARAB EMIRATES", "DUBAI", "ABU DHABI", "SHARJAH", "EMIRATI"]
        },
        "KWD": {
            "keywords": ["KWD", "KUWAITI DINAR", "KUWAITI DINARS", "K.D."],
            "symbols": ["د.ك"],
            "locations": ["KUWAIT", "KUWAITI"]
        },
        "BHD": {
            "keywords": ["BHD", "BAHRAINI DINAR", "BAHRAINI DINARS", "B.D."],
            "symbols": ["د.ب"],
            "locations": ["BAHRAIN", "BAHRAINI", "MANAMA"]
        },
        "OMR": {
            "keywords": ["OMR", "OMANI RIAL", "OMANI RIALS", "O.R."],
            "symbols": ["ر.ع."],
            "locations": ["OMAN", "OMANI", "MUSCAT"]
        },
        # Major Western currencies
        "USD": {
            "keywords": ["USD", "US DOLLAR", "US DOLLARS", "DOLLAR", "DOLLARS", "US$"],
            "symbols": ["$"],
            "locations": ["USA", "UNITED STATES", "AMERICA", "NEW YORK", "CALIFORNIA", "TEXAS", "FLORIDA"]
        },
        "EUR": {
            "keywords": ["EUR", "EURO", "EUROS"],
            "symbols": ["€"],
            "locations": ["EUROPE", "EUROPEAN", "GERMANY", "FRANCE", "ITALY", "SPAIN", "NETHERLANDS", "BELGIUM"]
        },
        "GBP": {
            "keywords": ["GBP", "POUND", "POUNDS", "BRITISH POUND", "STERLING", "POUND STERLING"],
            "symbols": ["£"],
            "locations": ["UK", "UNITED KINGDOM", "BRITAIN", "BRITISH", "LONDON", "ENGLAND", "SCOTLAND", "WALES"]
        },
        "CHF": {
            "keywords": ["CHF", "SWISS FRANC", "SWISS FRANCS", "FRANKEN"],
            "symbols": ["Fr.", "SFr."],
            "locations": ["SWITZERLAND", "SWISS", "ZURICH", "GENEVA", "BERN"]
        },
        # Indian currency
        "INR": {
            "keywords": ["INR", "RUPEE", "RUPEES", "INDIAN RUPEE", "RS.", "RS ", "RS"],
            "symbols": ["₹"],
            "locations": ["INDIA", "INDIAN", "MUMBAI", "DELHI", "BANGALORE", "CHENNAI", "KOLKATA", "HYDERABAD", "PUNE"]
        },
        # Other major currencies
        "CAD": {
            "keywords": ["CAD", "CANADIAN DOLLAR", "CANADIAN DOLLARS", "C$", "CA$"],
            "symbols": ["C$"],
            "locations": ["CANADA", "CANADIAN", "TORONTO", "VANCOUVER", "MONTREAL", "OTTAWA"]
        },
        "AUD": {
            "keywords": ["AUD", "AUSTRALIAN DOLLAR", "AUSTRALIAN DOLLARS", "A$", "AU$"],
            "symbols": ["A$"],
            "locations": ["AUSTRALIA", "AUSTRALIAN", "SYDNEY", "MELBOURNE", "BRISBANE", "PERTH"]
        },
        "NZD": {
            "keywords": ["NZD", "NEW ZEALAND DOLLAR", "NZ$"],
            "symbols": ["NZ$"],
            "locations": ["NEW ZEALAND", "AUCKLAND", "WELLINGTON"]
        },
        # Asian currencies
        "JPY": {
            "keywords": ["JPY", "YEN", "JAPANESE YEN"],
            "symbols": ["¥", "円"],
            "locations": ["JAPAN", "JAPANESE", "TOKYO", "OSAKA", "KYOTO"]
        },
        "CNY": {
            "keywords": ["CNY", "RMB", "YUAN", "RENMINBI", "CHINESE YUAN"],
            "symbols": ["¥", "元"],
            "locations": ["CHINA", "CHINESE", "BEIJING", "SHANGHAI", "SHENZHEN", "GUANGZHOU"]
        },
        "SGD": {
            "keywords": ["SGD", "SINGAPORE DOLLAR", "S$"],
            "symbols": ["S$"],
            "locations": ["SINGAPORE", "SINGAPOREAN"]
        },
        "MYR": {
            "keywords": ["MYR", "RINGGIT", "MALAYSIAN RINGGIT", "RM"],
            "symbols": ["RM"],
            "locations": ["MALAYSIA", "MALAYSIAN", "KUALA LUMPUR"]
        },
        "THB": {
            "keywords": ["THB", "BAHT", "THAI BAHT"],
            "symbols": ["฿"],
            "locations": ["THAILAND", "THAI", "BANGKOK"]
        },
        "PHP": {
            "keywords": ["PHP", "PESO", "PHILIPPINE PESO"],
            "symbols": ["₱"],
            "locations": ["PHILIPPINES", "PHILIPPINE", "MANILA"]
        },
        "IDR": {
            "keywords": ["IDR", "RUPIAH", "INDONESIAN RUPIAH"],
            "symbols": ["Rp"],
            "locations": ["INDONESIA", "INDONESIAN", "JAKARTA", "BALI"]
        },
        "VND": {
            "keywords": ["VND", "DONG", "VIETNAMESE DONG"],
            "symbols": ["₫"],
            "locations": ["VIETNAM", "VIETNAMESE", "HANOI", "HO CHI MINH"]
        },
        "KRW": {
            "keywords": ["KRW", "WON", "KOREAN WON"],
            "symbols": ["₩"],
            "locations": ["KOREA", "KOREAN", "SOUTH KOREA", "SEOUL"]
        },
        "HKD": {
            "keywords": ["HKD", "HONG KONG DOLLAR", "HK$"],
            "symbols": ["HK$"],
            "locations": ["HONG KONG"]
        },
        "TWD": {
            "keywords": ["TWD", "TAIWAN DOLLAR", "NT$", "NEW TAIWAN DOLLAR"],
            "symbols": ["NT$"],
            "locations": ["TAIWAN", "TAIPEI"]
        },
        # European currencies (non-Euro)
        "SEK": {
            "keywords": ["SEK", "KRONA", "SWEDISH KRONA"],
            "symbols": ["kr"],
            "locations": ["SWEDEN", "SWEDISH", "STOCKHOLM"]
        },
        "NOK": {
            "keywords": ["NOK", "NORWEGIAN KRONE"],
            "symbols": ["kr"],
            "locations": ["NORWAY", "NORWEGIAN", "OSLO"]
        },
        "DKK": {
            "keywords": ["DKK", "DANISH KRONE"],
            "symbols": ["kr"],
            "locations": ["DENMARK", "DANISH", "COPENHAGEN"]
        },
        "PLN": {
            "keywords": ["PLN", "ZLOTY", "POLISH ZLOTY"],
            "symbols": ["zł"],
            "locations": ["POLAND", "POLISH", "WARSAW"]
        },
        # Other currencies
        "ZAR": {
            "keywords": ["ZAR", "RAND", "SOUTH AFRICAN RAND"],
            "symbols": ["R"],
            "locations": ["SOUTH AFRICA", "JOHANNESBURG", "CAPE TOWN"]
        },
        "BRL": {
            "keywords": ["BRL", "REAL", "BRAZILIAN REAL"],
            "symbols": ["R$"],
            "locations": ["BRAZIL", "BRAZILIAN", "SAO PAULO", "RIO"]
        },
        "MXN": {
            "keywords": ["MXN", "MEXICAN PESO"],
            "symbols": ["$"],
            "locations": ["MEXICO", "MEXICAN", "MEXICO CITY"]
        },
        "TRY": {
            "keywords": ["TRY", "TURKISH LIRA", "LIRA"],
            "symbols": ["₺"],
            "locations": ["TURKEY", "TURKISH", "ISTANBUL", "ANKARA"]
        },
        "RUB": {
            "keywords": ["RUB", "RUBLE", "RUSSIAN RUBLE"],
            "symbols": ["₽"],
            "locations": ["RUSSIA", "RUSSIAN", "MOSCOW"]
        },
        "EGP": {
            "keywords": ["EGP", "EGYPTIAN POUND"],
            "symbols": ["E£", "ج.م"],
            "locations": ["EGYPT", "EGYPTIAN", "CAIRO"]
        },
        "PKR": {
            "keywords": ["PKR", "PAKISTANI RUPEE"],
            "symbols": ["Rs"],
            "locations": ["PAKISTAN", "PAKISTANI", "KARACHI", "LAHORE", "ISLAMABAD"]
        },
        "LKR": {
            "keywords": ["LKR", "SRI LANKAN RUPEE"],
            "symbols": ["Rs", "රු"],
            "locations": ["SRI LANKA", "COLOMBO"]
        },
        "BDT": {
            "keywords": ["BDT", "TAKA", "BANGLADESHI TAKA"],
            "symbols": ["৳"],
            "locations": ["BANGLADESH", "BANGLADESHI", "DHAKA"]
        },
        "NPR": {
            "keywords": ["NPR", "NEPALESE RUPEE"],
            "symbols": ["Rs", "रू"],
            "locations": ["NEPAL", "NEPALESE", "KATHMANDU"]
        }
    }
    
    amount_str = extracted_data.get("amount", "")
    
    if not amount_str:
        extracted_data["currency"] = ""
        return extracted_data
    
    # Check for percentage-only values
    amount_lower = str(amount_str).lower().strip()
    is_percentage_only = bool(re.match(r'^\s*\d+\.?\d*\s*%\s*$|^\s*\d+\.?\d*\s*percent\s*$', amount_lower))
    
    if is_percentage_only:
        extracted_data["amount"] = ""
        extracted_data["currency"] = ""
        return extracted_data
    
    # Extract numeric value - keep original formatting from document
    amount_match = re.search(r'[\d,]+\.?\d*', str(amount_str))
    
    if amount_match:
        try:
            # Keep the original matched string, just remove commas for storage
            original_amount = amount_match.group()
            numeric_amount = float(original_amount.replace(',', ''))
            
            # Detect currency from multiple sources
            currency = ""
            amount_upper = str(amount_str).upper()
            doc_text_upper = document_text.upper() if document_text else ""
            
            # 1. Check amount string for currency codes/keywords
            for curr_code, curr_info in CURRENCY_MAP.items():
                # Check keywords in amount string
                for keyword in curr_info["keywords"]:
                    if keyword.upper() in amount_upper:
                        currency = curr_code
                        break
                # Check symbols in amount string
                if not currency:
                    for symbol in curr_info["symbols"]:
                        if symbol in amount_str:
                            currency = curr_code
                            break
                if currency:
                    break
            
            # 2. If no currency found in amount, check amounts field for nested currency
            if not currency:
                amounts = extracted_data.get("amounts", {})
                if isinstance(amounts, dict):
                    for key, value in amounts.items():
                        if value and isinstance(value, str):
                            value_upper = value.upper()
                            for curr_code, curr_info in CURRENCY_MAP.items():
                                for keyword in curr_info["keywords"]:
                                    if keyword.upper() in value_upper:
                                        currency = curr_code
                                        break
                                if not currency:
                                    for symbol in curr_info["symbols"]:
                                        if symbol in value:
                                            currency = curr_code
                                            break
                                if currency:
                                    break
                        if currency:
                            break
            
            # 3. If still no currency, check extracted currency field
            if not currency:
                extracted_currency = extracted_data.get("currency", "")
                if extracted_currency:
                    extracted_upper = extracted_currency.upper().strip()
                    if extracted_upper in CURRENCY_MAP:
                        currency = extracted_upper
            
            # 4. If still no currency, search document text for currency keywords
            if not currency and document_text:
                # First check for explicit "Currency: XXX" pattern
                currency_pattern = re.search(r'CURRENCY[:\s]+([A-Z]{3})', doc_text_upper)
                if currency_pattern:
                    found_code = currency_pattern.group(1)
                    if found_code in CURRENCY_MAP:
                        currency = found_code
                
                # Check for currency codes/keywords in document
                if not currency:
                    for curr_code, curr_info in CURRENCY_MAP.items():
                        for keyword in curr_info["keywords"]:
                            if keyword.upper() in doc_text_upper:
                                currency = curr_code
                                break
                        if currency:
                            break
                
                # Check for country/location mentions to infer currency
                if not currency:
                    for curr_code, curr_info in CURRENCY_MAP.items():
                        for location in curr_info["locations"]:
                            if location in doc_text_upper:
                                currency = curr_code
                                break
                        if currency:
                            break
            
            # 5. Default to USD if no currency detected (common default for international invoices)
            if not currency:
                currency = "USD"
            
            # Keep the exact amount as it appears in the document (just remove commas)
            extracted_data["amount"] = original_amount.replace(',', '')
            extracted_data["currency"] = currency
            
        except (ValueError, AttributeError):
            pass
    
    return extracted_data


def _calculate_period_amount(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate per-period amount from total and frequency."""
    amount_str = extracted_data.get("amount", "")
    frequency = extracted_data.get("frequency", "")
    
    if not amount_str or not frequency:
        return extracted_data
    
    try:
        amount_match = re.search(r'[\d,]+\.?\d*', str(amount_str).replace(',', ''))
        if not amount_match:
            return extracted_data
        
        total_amount = float(amount_match.group().replace(',', ''))
        frequency_lower = str(frequency).lower().strip()
        
        # Determine periods per year
        if any(term in frequency_lower for term in ['monthly', 'month']):
            periods_per_year = 12
            period_name = "month"
        elif any(term in frequency_lower for term in ['quarterly', 'quarter']):
            periods_per_year = 4
            period_name = "quarter"
        elif any(term in frequency_lower for term in ['annual', 'yearly', 'year']):
            periods_per_year = 1
            period_name = "year"
        else:
            return extracted_data
        
        per_period_amount = total_amount / periods_per_year
        per_month_amount = total_amount / 12
        
        # Keep exact decimal values without rounding
        extracted_data["per_period_amount"] = f"{per_period_amount:.2f}"
        extracted_data["per_month_amount"] = f"{per_month_amount:.2f}"
        extracted_data["period_name"] = period_name
        
    except (ValueError, AttributeError):
        pass
    
    return extracted_data


def _classify_account_head(extracted_data: Dict[str, Any], document_text: str) -> str:
    """
    Classify account head based on document content analysis.
    Uses AI to intelligently determine the appropriate account head.
    """
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        from account_heads_taxonomy import get_account_head_list
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return "General Expense"
        
        # Prepare context for classification
        doc_type = extracted_data.get("document_type", "")
        invoice_type = extracted_data.get("invoice_type", "")
        
        # Get vendor/customer info
        party_names = extracted_data.get("party_names", {})
        vendor = party_names.get("vendor") or party_names.get("party_1", "")
        
        # Get line items
        line_items = extracted_data.get("line_items", [])
        line_items_text = ""
        if line_items:
            for item in line_items[:5]:  # Use first 5 items
                if isinstance(item, dict):
                    desc = item.get("description", "")
                    if desc:
                        line_items_text += f"  - {desc}\n"
        
        # Get notes/description
        notes = extracted_data.get("notes", "")
        
        # Get document excerpt (first 500 chars for context)
        doc_excerpt = document_text[:500] if document_text else ""
        
        # Create classification prompt
        prompt = f"""Analyze this invoice/document and classify it into the MOST APPROPRIATE account head category.

DOCUMENT INFORMATION:
- Document Type: {doc_type}
- Invoice Type: {invoice_type or "Not specified"}
- Vendor/Provider: {vendor or "Not specified"}
- Line Items:
{line_items_text if line_items_text else "  (No line items)"}
- Notes: {notes or "None"}

DOCUMENT EXCERPT:
{doc_excerpt}

AVAILABLE ACCOUNT HEAD CATEGORIES:
{get_account_head_list()}

CLASSIFICATION INSTRUCTIONS:
1. Analyze the document content, invoice type, line items, and vendor information
2. Select the SINGLE MOST APPROPRIATE account head from the list above
3. Consider:
   - What service/product is being billed?
   - What is the nature of the expense/revenue?
   - Industry/category keywords in descriptions
4. If no specific category matches well, use "General Expense"
5. Return ONLY the account head name, exactly as shown in the list

RETURN FORMAT:
Return only the account head name (e.g., "IT & Technical Services" or "Construction Expense")
NO explanation, NO extra text."""

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, api_key=api_key)
        
        response = llm.invoke([
            SystemMessage(content="You are an accounting classification expert. Return only the account head name."),
            HumanMessage(content=prompt)
        ])
        
        # Extract account head from response
        account_head = response.content.strip()
        
        # Clean up response (remove quotes, extra whitespace)
        account_head = account_head.replace('"', '').replace("'", "").strip()
        
        # Validate it's in our taxonomy
        from account_heads_taxonomy import ALL_ACCOUNT_HEADS
        if account_head in ALL_ACCOUNT_HEADS.values():
            return account_head
        
        # If not exact match, try to find partial match
        for key, name in ALL_ACCOUNT_HEADS.items():
            if name.lower() in account_head.lower() or account_head.lower() in name.lower():
                return name
        
        # Default fallback
        return "General Expense"
        
    except Exception as e:
        print(f"    → Warning: Account head classification error: {str(e)}")
        return "General Expense"


def _assign_account_type(extracted_data: Dict[str, Any], document_type: str, document_text: str = "") -> Dict[str, Any]:
    """Assign account type based on content analysis."""
    account_type = extracted_data.get("account_type")
    
    # If account type is already set and looks valid, keep it
    if account_type and account_type.strip() != "" and account_type.lower() not in ["null", "accounts payable", "general expense"]:
        return extracted_data
    
    # For invoices and contracts, use AI-based classification
    if document_type.upper() in ["INVOICE", "CONTRACT", "LEASE"]:
        print(f"    → Classifying account head based on document content...")
        classified_account = _classify_account_head(extracted_data, document_text)
        extracted_data["account_type"] = classified_account
        print(f"    → Account Head: {classified_account}")
    else:
        # For NDA and others, use simple mapping
        account_head_mapping = {
            "NDA": "Legal & Professional Fees",
            "CONTRACT": "Service Revenue"
        }
        extracted_data["account_type"] = account_head_mapping.get(document_type.upper(), "General Expense")
    
    return extracted_data


def _normalize_invoice_data(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize invoice data to ensure compatibility with the standard format."""
    
    # Flatten dates if nested
    dates = extracted_data.get("dates", {})
    if dates:
        if not extracted_data.get("start_date"):
            extracted_data["start_date"] = dates.get("invoice_date", "")
        if not extracted_data.get("due_date"):
            extracted_data["due_date"] = dates.get("due_date", "")
    
    # Flatten amounts if nested
    amounts = extracted_data.get("amounts", {})
    if amounts:
        # Set main amount from total or amount_due
        if not extracted_data.get("amount"):
            extracted_data["amount"] = (
                amounts.get("total") or 
                amounts.get("amount_due") or 
                amounts.get("balance_due") or
                amounts.get("taxable_amount") or
                ""
            )
        
        # Extract tax details to top level
        extracted_data["tax_details"] = {
            "subtotal": amounts.get("subtotal", ""),
            "cgst": amounts.get("cgst", ""),
            "sgst": amounts.get("sgst", ""),
            "igst": amounts.get("igst", ""),
            "gst": amounts.get("gst", ""),
            "vat": amounts.get("vat", ""),
            "tax_amount": amounts.get("tax_amount", ""),
            "discount": amounts.get("discount", "")
        }
    
    # Normalize party names for invoices
    party_names = extracted_data.get("party_names", {})
    if party_names:
        # Map vendor/customer to party_1/party_2 if not set
        if not party_names.get("party_1") and party_names.get("vendor"):
            party_names["party_1"] = party_names["vendor"]
        if not party_names.get("party_2") and party_names.get("customer"):
            party_names["party_2"] = party_names["customer"]
        extracted_data["party_names"] = party_names
    
    # Normalize document IDs - ensure primary ID is captured
    doc_ids = extracted_data.get("document_ids", {})
    if doc_ids:
        # Helper function to clean labels from extracted values
        def clean_label_from_value(value):
            """Remove common labels like 'Quote No', 'Invoice No', etc. from extracted values."""
            if not value or not isinstance(value, str):
                return value
            value = value.strip()
            # Remove common label patterns
            label_patterns = [
                r'^invoice\s*:?\s*quote\s*no\s*;?\s*quote\s*:?\s*quote\s*no\s*$',
                r'^invoice\s*:?\s*quote\s*no\s*$',
                r'^quote\s*:?\s*quote\s*no\s*$',
                r'^quote\s*no\s*:?\s*$',
                r'^invoice\s*no\s*:?\s*$',
                r'^quotation\s*no\s*:?\s*$',
                r'^quote\s*number\s*:?\s*$',
                r'^invoice\s*number\s*:?\s*$',
            ]
            for pattern in label_patterns:
                if re.match(pattern, value, re.IGNORECASE):
                    return ""
            # Remove label prefixes if value contains both label and value
            # Pattern: "Label: Value" -> extract "Value"
            match = re.match(r'^(?:invoice|quote|quotation)\s*(?:no|number)\s*:?\s*(.+)$', value, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            # Pattern: "Invoice: Value; Quote: Value" -> extract "Value"
            match = re.match(r'^invoice\s*:?\s*(.+?)\s*;?\s*quote\s*:?\s*(.+?)$', value, re.IGNORECASE)
            if match:
                val1 = match.group(1).strip()
                val2 = match.group(2).strip()
                # If both are the same, return one; if different, prefer the first
                if val1 == val2:
                    return val1
                # If one is just "Quote No", return the other
                if re.match(r'^quote\s*no\s*$', val2, re.IGNORECASE):
                    return val1
                if re.match(r'^quote\s*no\s*$', val1, re.IGNORECASE):
                    return val2
                return val1  # Default to first value
            return value
        
        invoice_id = clean_label_from_value(doc_ids.get("invoice_id", ""))
        invoice_number = clean_label_from_value(doc_ids.get("invoice_number", ""))
        quotation_number = clean_label_from_value(doc_ids.get("quotation_number", ""))
        
        # Update doc_ids with cleaned values
        if invoice_id != doc_ids.get("invoice_id", ""):
            doc_ids["invoice_id"] = invoice_id
        if invoice_number != doc_ids.get("invoice_number", ""):
            doc_ids["invoice_number"] = invoice_number
        if quotation_number != doc_ids.get("quotation_number", ""):
            doc_ids["quotation_number"] = quotation_number
        
        invoice_id = invoice_id.strip() if invoice_id else ""
        invoice_number = invoice_number.strip() if invoice_number else ""
        quotation_number = quotation_number.strip() if quotation_number else ""
        
        # If invoice_id/invoice_number and quotation_number are the same, remove duplicate from quotation_number
        if quotation_number:
            if quotation_number == invoice_id or quotation_number == invoice_number:
                # Same value, remove from quotation_number to avoid duplication
                doc_ids["quotation_number"] = ""
                quotation_number = ""
        
        # Find the primary document identifier (try multiple fields, including quotation_number if different)
        primary_id = (
            invoice_id or 
            invoice_number or 
            quotation_number or  # Quote number can be invoice number if different
            doc_ids.get("bill_number", "").strip() or
            doc_ids.get("document_number", "").strip() or
            doc_ids.get("reference_id", "").strip() or
            ""
        )
        
        # Set both invoice_id and invoice_number to the primary ID if either is empty
        if primary_id:
            if not invoice_id:
                doc_ids["invoice_id"] = primary_id
            if not invoice_number:
                doc_ids["invoice_number"] = primary_id
        
        # If quotation_number exists and is different from invoice_id/invoice_number, 
        # it should also be considered as a valid invoice identifier (only if invoice_id is empty)
        if quotation_number and quotation_number != primary_id:
            # If invoice_id is empty, use quotation_number
            if not doc_ids.get("invoice_id"):
                doc_ids["invoice_id"] = quotation_number
            if not doc_ids.get("invoice_number"):
                doc_ids["invoice_number"] = quotation_number
        
        extracted_data["document_ids"] = doc_ids
    
    # Ensure currency is set - look in amounts if not in main currency field
    if not extracted_data.get("currency"):
        # Check amounts for currency information
        amounts = extracted_data.get("amounts", {})
        if amounts:
            for key, value in amounts.items():
                if value and isinstance(value, str):
                    # Look for currency symbols/codes in amount values
                    if "$" in value or "USD" in value.upper():
                        extracted_data["currency"] = "USD"
                        break
                    elif "₹" in value or "INR" in value.upper() or "Rs" in value:
                        extracted_data["currency"] = "INR"
                        break
                    elif "€" in value or "EUR" in value.upper():
                        extracted_data["currency"] = "EUR"
                        break
                    elif "£" in value or "GBP" in value.upper():
                        extracted_data["currency"] = "GBP"
                        break
    
    return extracted_data


# ============== Conditional Edge Functions ==============

def should_continue(state: ExtractionState) -> Literal["continue", "error"]:
    """Determine if processing should continue or stop on error."""
    if state.get("error"):
        return "error"
    return "continue"


# ============== Main Agent Class ==============

class ExtractionAgent:
    """
    LangGraph-based Contract Extraction Agent.
    
    This agent uses a graph-based workflow to:
    1. Parse documents (PDF, DOCX, TXT)
    2. Classify document type (LEASE, NDA, CONTRACT)
    3. Extract relevant data using type-specific prompts
    4. Enhance data with currency/period calculations
    5. Calculate risk scores
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        use_gcs_vision: bool = True,  # Default to True - Vision API enabled for OCR
        service_account_file: Optional[str] = None,
        use_semantic_search: bool = True,  # Kept for backwards compatibility
        document_id: Optional[str] = None   # Kept for backwards compatibility
    ):
        """
        Initialize the extraction agent.
        
        Args:
            api_key: OpenAI API key (uses env var if not provided)
            use_gcs_vision: Whether to use Google Cloud Vision for scanned PDFs (default True)
            service_account_file: Path to GCP service account JSON
            use_semantic_search: Kept for backwards compatibility (agent has built-in semantic capabilities)
            document_id: Kept for backwards compatibility
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.use_gcs_vision = use_gcs_vision
        self.service_account_file = service_account_file
        self.use_semantic_search = use_semantic_search  # Stored but agent uses LLM-based extraction
        self.document_id = document_id
        
        # Build the graph
        self.graph = self._build_graph()
        self.app = self.graph.compile()
    
    def _build_graph(self) -> StateGraph:
        """Build the extraction workflow graph."""
        
        # Create the graph
        workflow = StateGraph(ExtractionState)
        
        # Add nodes
        workflow.add_node("parse", parse_document_node)
        workflow.add_node("classify", classify_document_node)
        workflow.add_node("extract", extract_data_node)
        workflow.add_node("enhance", enhance_data_node)
        workflow.add_node("risk", calculate_risk_node)
        workflow.add_node("finalize", finalize_node)
        
        # Add edges
        workflow.set_entry_point("parse")
        
        # Parse → Classify (with error check)
        workflow.add_conditional_edges(
            "parse",
            should_continue,
            {
                "continue": "classify",
                "error": "finalize"
            }
        )
        
        # Classify → Extract (with error check)
        workflow.add_conditional_edges(
            "classify",
            should_continue,
            {
                "continue": "extract",
                "error": "finalize"
            }
        )
        
        # Extract → Enhance (with error check)
        workflow.add_conditional_edges(
            "extract",
            should_continue,
            {
                "continue": "enhance",
                "error": "finalize"
            }
        )
        
        # Enhance → Risk (always continue)
        workflow.add_edge("enhance", "risk")
        
        # Risk → Finalize
        workflow.add_edge("risk", "finalize")
        
        # Finalize → END
        workflow.add_edge("finalize", END)
        
        return workflow
    
    def extract_from_file(
        self,
        file_path: str,
        use_ocr: bool = False
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract data from a file.
        
        Args:
            file_path: Path to the document file
            use_ocr: Whether to use OCR for scanned PDFs
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        print("\n" + "=" * 60)
        print("[LANGGRAPH AGENT] Starting extraction workflow")
        print("=" * 60)
        print(f"  File: {Path(file_path).name}")
        
        # Initialize state
        initial_state: ExtractionState = {
            "file_path": file_path,
            "document_text": None,
            "page_map": {},
            "use_ocr": use_ocr,
            "use_gcs_vision": self.use_gcs_vision,
            "document_type": None,
            "classification_confidence": None,
            "classification_reasoning": None,
            "extracted_data": {},
            "error": None,
            "status": "pending",
            "messages": []
        }
        
        # Run the graph
        final_state = self.app.invoke(initial_state)
        
        # Extract results
        extracted_data = final_state.get("extracted_data", {})
        
        metadata = {
            "document_type": final_state.get("document_type", "CONTRACT"),
            "classification_confidence": final_state.get("classification_confidence", "UNKNOWN"),
            "classification_reasoning": final_state.get("classification_reasoning", ""),
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "extraction_method": "langgraph_agent",
            "document_text": final_state.get("document_text", ""),  # Store for chatbot reuse
            "page_map": final_state.get("page_map", {}),
            "status": final_state.get("status", "unknown"),
            "error": final_state.get("error")
        }
        
        print("\n" + "=" * 60)
        print(f"[LANGGRAPH AGENT] Extraction completed: {final_state.get('status', 'unknown')}")
        print("=" * 60 + "\n")
        
        return extracted_data, metadata
    
    def extract_from_text(
        self,
        document_text: str,
        page_map: Optional[Dict[int, str]] = None
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract data from raw text.
        
        Args:
            document_text: Raw text from document
            page_map: Optional page mapping
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        print("\n" + "=" * 60)
        print("[LANGGRAPH AGENT] Starting extraction workflow (from text)")
        print("=" * 60)
        
        # Initialize state
        initial_state: ExtractionState = {
            "file_path": None,
            "document_text": document_text,
            "page_map": page_map or {},
            "use_ocr": False,
            "use_gcs_vision": self.use_gcs_vision,
            "document_type": None,
            "classification_confidence": None,
            "classification_reasoning": None,
            "extracted_data": {},
            "error": None,
            "status": "pending",
            "messages": []
        }
        
        # Run the graph
        final_state = self.app.invoke(initial_state)
        
        # Extract results
        extracted_data = final_state.get("extracted_data", {})
        
        metadata = {
            "document_type": final_state.get("document_type", "CONTRACT"),
            "classification_confidence": final_state.get("classification_confidence", "UNKNOWN"),
            "classification_reasoning": final_state.get("classification_reasoning", ""),
            "extraction_method": "langgraph_agent",
            "document_text": final_state.get("document_text", ""),  # Store for chatbot reuse
            "page_map": final_state.get("page_map", {}),
            "status": final_state.get("status", "unknown"),
            "error": final_state.get("error")
        }
        
        print("\n" + "=" * 60)
        print(f"[LANGGRAPH AGENT] Extraction completed: {final_state.get('status', 'unknown')}")
        print("=" * 60 + "\n")
        
        return extracted_data, metadata


# ============== Backwards Compatibility ==============

# Alias for backwards compatibility with existing code
ExtractionOrchestrator = ExtractionAgent


if __name__ == "__main__":
    # Test the agent
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python extraction_agent.py <file_path>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    
    agent = ExtractionAgent()
    extracted_data, metadata = agent.extract_from_file(file_path)
    
    print("\n" + "=" * 60)
    print("EXTRACTED DATA:")
    print("=" * 60)
    print(json.dumps(extracted_data, indent=2, ensure_ascii=False))

