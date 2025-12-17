"""
Contract Document Extractor (Service Contracts)
Extracts contract-specific fields from service contracts across all business sectors.
"""

import json
from typing import Dict, Any, Optional
from openai import OpenAI


class ContractExtractorSpecific:
    """Extracts contract-specific details from service contract documents."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the contract extractor.
        
        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY env var.
        """
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
    
    def extract(self, document_text: str) -> Dict[str, Any]:
        """
        Extract contract-specific details from document text.
        
        Args:
            document_text: Raw text from contract document
            
        Returns:
            Dictionary containing extracted contract data
        """
        # Clean the input text
        cleaned_text = self._clean_text(document_text)
        
        # Create the extraction prompt
        prompt = self._create_extraction_prompt(cleaned_text)
        
        # Call OpenAI API
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
        except Exception as e:
            raise ValueError(f"OpenAI API error: {str(e)}")
        
        # Parse the JSON response
        try:
            response_content = response.choices[0].message.content
            extracted_data = json.loads(response_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response: {str(e)}")
        
        return extracted_data
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for contract extraction."""
        return """You are an AI Contract Document Extraction Engine.
You MUST extract ALL relevant contract details with high precision and zero hallucinations.

EXTRACTION RULES:
1. If any data is missing or not present → return null.
2. NEVER hallucinate or invent contract clauses.
3. Preserve original clause wording exactly.
4. Convert all dates to ISO format: YYYY-MM-DD.
5. Return EXACT JSON — no explanation, no markdown, no notes.
6. CRITICAL: Extract party names (Customer/Client and Service Provider) from the document header, "PARTIES" section, or signature block. Look for full legal names, company names, or individual names."""
    
    def _create_extraction_prompt(self, document_text: str) -> str:
        """Create the extraction prompt for contract documents."""
        return f"""Analyze the following SERVICE CONTRACT document and extract ONLY the following specific information:

DOCUMENT TEXT:
{document_text}

REQUIRED OUTPUT FORMAT (STRICT JSON):
{{
  "document_type": "CONTRACT",
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
    "reference_id": "",
    "agreement_id": "",
    "service_id": "",
    "document_number": "",
    "po_number": "",
    "quotation_number": "",
    "work_order_number": "",
    "project_id": "",
    "file_number": "",
    "gst_number": "",
    "pan_number": "",
    "cin_number": "",
    "tan_number": "",
    "payment_reference": "",
    "transaction_id": "",
    "receipt_number": "",
    "bank_reference": "",
    "certificate_number": "",
    "license_number": "",
    "authorization_number": "",
    "approval_number": "",
    "other_ids": []
  }},
  "rules_and_compliance_violation": "",
  "risk_score": null
}}

EXTRACTION INSTRUCTIONS:
1. Document Type: Set to "CONTRACT"
2. Party Names: Extract all party names (Customer/Client and Service Provider/Vendor). Include full legal names, company names, or individual names. Put primary parties in party_1 and party_2, additional parties in the array.
3. Start Date: Extract the contract effective date, start date, or commencement date. Format as YYYY-MM-DD.
4. Due Date: Extract payment due date, invoice due date, or any payment deadline. Format as YYYY-MM-DD.
5. Amount: Extract the payment amount, contract value, total payment, or any monetary value mentioned. IMPORTANT: Do NOT extract percentages (like "10%", "10 percent", "5%") as amounts - only extract actual monetary values with currency. If only percentages are mentioned without actual amounts, leave amount as empty/null.
6. Frequency: Extract payment frequency (e.g., "Monthly", "Quarterly", "Annual", "One-time", "Per invoice").
7. Account Type: Extract account type, account head, or account classification if mentioned in the document.
8. Document IDs: Extract all identification numbers/IDs mentioned in the document:
   - Invoice ID/Invoice Number
   - Contract ID/Contract Number
   - Reference ID/Reference Number
   - Agreement ID/Agreement Number
   - Service ID/Service Number
   - Document Number
   - PO Number/Purchase Order Number
   - Quotation Number/Quote ID
   - Work Order Number
   - Project ID/Project Number
   - File Number/Filing Number
   - GST Number/GSTIN (Indian Tax ID)
   - PAN Number (Indian Permanent Account Number)
   - CIN Number (Company Identification Number)
   - TAN Number (Tax Deduction Account Number)
   - Payment Reference Number
   - Transaction ID/Transaction Reference
   - Receipt Number
   - Bank Reference Number
   - Certificate Number (ISO, Quality, Compliance certificates)
   - License Number
   - Authorization Number
   - Approval Number
   - Any other ID numbers in other_ids array
   Look for patterns like "Invoice ID:", "Contract #", "Ref:", "PO:", "GST:", "PAN:", "CIN:", "Certificate No:", etc.
9. Rules and Compliance Violation: 
   - CAREFULLY analyze the document for any rules violations, compliance issues, regulatory violations, breach of regulations, non-compliance, or any mention of violations.
   - Look for keywords like: "violation", "non-compliance", "breach", "regulatory violation", "compliance issue", "rule violation", "illegal", "prohibited", "forbidden", "against regulations", "violates", "non-conforming"
   - If ANY violation is found: Provide detailed description of the violation(s) with specific references to the document sections/clauses where mentioned. Include the exact text or clause that indicates the violation.
   - If NO violations are found: Return exactly "No violation of rules and compliance"
   - Be thorough - check all clauses, terms, conditions, and any regulatory references in the document
10. Risk Score: Leave as null (will be calculated separately).

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Use null for missing values (except for rules_and_compliance_violation which should always return either violation details or "No violation of rules and compliance")
- Extract party names from document header, "PARTIES" section, or signature block
- Look for phrases like "Customer:", "Client:", "Buyer:", "Provider:", "Vendor:", "Supplier:", "Contractor:"
- Convert all dates to ISO format: YYYY-MM-DD
- For rules_and_compliance_violation: Always provide a value - either violation details with references or "No violation of rules and compliance" """
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize the input text."""
        if not text:
            return ""
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return text.strip()

