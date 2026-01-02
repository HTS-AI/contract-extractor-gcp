"""
Contract Extraction Engine using OpenAI gpt-4o-mini
Extracts structured contract data from various document formats.
Uses semantic search to find information even when not explicitly stated.

DEPRECATED: This file contains the old general extraction logic.
For new implementations, please use ExtractionOrchestrator from extraction_orchestrator.py
which provides type-specific extraction (Lease, NDA, Contract).

The orchestrator automatically:
- Detects document type
- Routes to appropriate extractor (lease_extractor.py, nda_extractor.py, contract_extractor_specific.py)
- Integrates with vision_gcp.py for scanned PDFs
- Provides better accuracy with type-specific extraction

This file is kept for backward compatibility but is not recommended for new code.
"""

import json
import re
from typing import Dict, Any, Optional
from openai import OpenAI

try:
    from semantic_search import SemanticSearcher
except ImportError:
    SemanticSearcher = None

try:
    from document_type_classifier import classify_document_type
except ImportError:
    classify_document_type = None


class ContractExtractor:
    """Extracts contract details using OpenAI gpt-4o-mini model."""
    
    def __init__(self, api_key: Optional[str] = None, use_semantic_search: bool = True, document_id: Optional[str] = None):
        """
        Initialize the contract extractor.
        
        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY env var.
            use_semantic_search: Whether to use semantic search for missing fields
            document_id: Unique identifier for the document (for vector DB)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.page_map = {}
        self.document_id = document_id
        self.use_semantic_search = use_semantic_search and SemanticSearcher is not None
        self.semantic_searcher = SemanticSearcher(api_key=api_key, use_faiss=True) if self.use_semantic_search else None
        
    def extract(self, document_text: str, page_map: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
        """
        Extract contract details from document text.
        
        Args:
            document_text: Raw text from contract document (OCR, PDF, DOCX, or plain text)
            page_map: Optional dictionary mapping page numbers to text content for page tracking
            
        Returns:
            Dictionary containing extracted contract data in the required JSON format
        """
        # Store page map for reference finding
        self.page_map = page_map if page_map else {}
        
        # Initialize vector database with document chunks and embeddings
        if self.use_semantic_search and self.semantic_searcher and self.semantic_searcher.use_faiss:
            doc_id = self.document_id or f"doc_{hash(document_text) % 100000}"
            try:
                self.semantic_searcher.initialize_vector_db(document_text, doc_id, page_map=page_map)
                print(f"Vector database initialized with {len(document_text)} characters")
            except Exception as e:
                print(f"Warning: Could not initialize vector database: {str(e)}")
        
        # Classify document type first
        document_type_info = None
        if classify_document_type:
            try:
                # Get API key from environment or use None (classifier will use env var)
                import os
                api_key = os.getenv('OPENAI_API_KEY')
                document_type_info = classify_document_type(document_text, api_key=api_key)
                print(f"Document classified as: {document_type_info.get('document_type', 'UNKNOWN')} (Confidence: {document_type_info.get('confidence', 'UNKNOWN')})")
            except Exception as e:
                print(f"Warning: Document type classification failed: {e}")
        
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
                temperature=0.1,  # Low temperature for precision
                response_format={"type": "json_object"}
            )
        except Exception as e:
            raise ValueError(f"OpenAI API error: {str(e)}")
        
        # Parse the JSON response
        try:
            response_content = response.choices[0].message.content
            extracted_data = json.loads(response_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON response from OpenAI: {str(e)}\nResponse: {response_content[:500]}")
        
        # Validate and clean the output
        validated_data = self._validate_output(extracted_data)
        
        # Override contract_type with classified type if available and more specific
        if document_type_info and document_type_info.get("document_type"):
            classified_type = document_type_info["document_type"]
            # Only override if extracted type is empty or generic
            if not validated_data.get("contract_type") or validated_data.get("contract_type", "").upper() in ["CONTRACT", "AGREEMENT", ""]:
                validated_data["contract_type"] = classified_type
            # Store classification info
            validated_data["document_classification"] = {
                "detected_type": classified_type,
                "confidence": document_type_info.get("confidence", "MEDIUM"),
                "reasoning": document_type_info.get("reasoning", "")
            }
        
        # Use semantic search to fill missing fields
        if self.use_semantic_search and self.semantic_searcher:
            validated_data = self._enhance_with_semantic_search(validated_data, document_text)
        
        # Enhance references by finding source text snippets with page numbers
        validated_data = self._enhance_references(validated_data, document_text)
        
        # Calculate risk score based on extracted data
        validated_data = self._calculate_risk_score(validated_data, document_text)
        
        return validated_data
    
    def _get_system_prompt(self) -> str:
        """Get the system prompt for the extraction task."""
        return """You are an AI Contract Extraction Engine built specifically for a Contract Automation System.
You MUST extract ALL relevant contract details with high precision and zero hallucinations.

EXTRACTION RULES:
1. If any data is missing or not present → return null.
2. NEVER hallucinate or invent contract clauses.
3. Preserve original clause wording exactly.
4. Convert all dates to ISO format: YYYY-MM-DD.
5. Extract ALL occurrences of parties, clauses, payments, or dates.
6. Return EXACT JSON — no explanation, no markdown, no notes.
7. Keep text clean and without escape characters.
8. Look for information in various forms - it may be stated directly or implied in related clauses.
9. For each extracted field, provide a "reference" field containing the exact text snippet from the document that supports the extraction (max 200 characters)."""
    
    def _create_extraction_prompt(self, document_text: str) -> str:
        """Create the extraction prompt with document text."""
        return f"""Analyze the following contract document and extract ALL relevant details in the exact JSON format specified below.

DOCUMENT TEXT:
{document_text}

REQUIRED OUTPUT FORMAT (STRICT JSON):
{{
  "contract_title": "",
  "contract_type": "",
  "parties": {{
    "party_1_name": "",
    "party_1_address": "",
    "party_2_name": "",
    "party_2_address": "",
    "additional_parties": []
  }},
  "effective_date": "",
  "execution_date": "",
  "start_date": "",
  "end_date": "",
  "auto_renewal": "",
  "termination_clause": "",
  "termination_notice_period": "",
  "governing_law": "",
  "jurisdiction": "",
  "payment_terms": {{
    "amount": "",
    "currency": "",
    "frequency": "",
    "due_dates": []
  }},
  "contract_value": "",
  "obligations": {{
    "party_1_obligations": [],
    "party_2_obligations": []
  }},
  "confidentiality_clause": "",
  "liability_clause": "",
  "indemnity_clause": "",
  "insurance_requirements": "",
  "deliverables": [],
  "milestones": [],
  "renewal_terms": "",
  "penalty_terms": "",
  "governing_clauses_raw": [],
  "signatories": {{
    "party_1_signatory": "",
    "party_2_signatory": ""
  }},
  "risk_score": null,
  "missing_clauses": [],
  "summary": "",
  "references": {{
    "contract_title": "",
    "contract_type": "",
    "party_1_name": "",
    "party_1_address": "",
    "party_2_name": "",
    "party_2_address": "",
    "effective_date": "",
    "execution_date": "",
    "start_date": "",
    "end_date": "",
    "auto_renewal": "",
    "termination_clause": "",
    "termination_notice_period": "",
    "governing_law": "",
    "jurisdiction": "",
    "payment_amount": "",
    "payment_currency": "",
    "payment_frequency": "",
    "contract_value": "",
    "confidentiality_clause": "",
    "liability_clause": "",
    "indemnity_clause": "",
    "insurance_requirements": "",
    "renewal_terms": "",
    "penalty_terms": "",
    "party_1_signatory": "",
    "party_2_signatory": ""
  }}
}}

IMPORTANT:
- Return ONLY valid JSON, no markdown, no explanations
- Use null for missing values
- Preserve exact wording from the document
- Convert dates to YYYY-MM-DD format
- Extract all relevant information, do not omit anything
- For the "references" object, provide objects with "text" (exact text snippet up to 200 characters) and "page" (page number if available) for each extracted value. Format: {{"text": "snippet", "page": 1}}. If a value is null, the corresponding reference should also be null.
- Do NOT calculate risk_score - leave it as null. Risk score will be calculated separately."""
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize the input text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special escape characters but preserve content
        text = text.replace('\n', ' ').replace('\r', ' ')
        text = text.replace('\t', ' ')
        
        # Trim
        text = text.strip()
        
        return text
    
    def _validate_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and ensure the output matches the required format."""
        # Define the required structure
        required_structure = {
            "contract_title": "",
            "contract_type": "",
            "parties": {
                "party_1_name": "",
                "party_1_address": "",
                "party_2_name": "",
                "party_2_address": "",
                "additional_parties": []
            },
            "effective_date": "",
            "execution_date": "",
            "start_date": "",
            "end_date": "",
            "auto_renewal": "",
            "termination_clause": "",
            "termination_notice_period": "",
            "governing_law": "",
            "jurisdiction": "",
            "payment_terms": {
                "amount": "",
                "currency": "",
                "frequency": "",
                "due_dates": []
            },
            "contract_value": "",
            "obligations": {
                "party_1_obligations": [],
                "party_2_obligations": []
            },
            "confidentiality_clause": "",
            "liability_clause": "",
            "indemnity_clause": "",
            "insurance_requirements": "",
            "deliverables": [],
            "milestones": [],
            "renewal_terms": "",
            "penalty_terms": "",
            "governing_clauses_raw": [],
            "signatories": {
                "party_1_signatory": "",
                "party_2_signatory": ""
            },
            "risk_score": None,
            "missing_clauses": [],
            "summary": "",
            "references": {}
        }
        
        # Merge with defaults to ensure all fields exist
        validated = self._merge_dicts(required_structure, data)
        
        # Normalize empty strings to null for missing data
        validated = self._normalize_empty_to_null(validated)
        
        return validated
    
    def _merge_dicts(self, base: Dict, override: Dict) -> Dict:
        """Recursively merge two dictionaries."""
        result = base.copy()
        
        for key, value in override.items():
            if key in result:
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = self._merge_dicts(result[key], value)
                else:
                    result[key] = value
            else:
                result[key] = value
        
        return result
    
    def _normalize_empty_to_null(self, data: Any) -> Any:
        """Recursively convert empty strings to null."""
        if isinstance(data, dict):
            return {k: self._normalize_empty_to_null(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._normalize_empty_to_null(item) for item in data]
        elif isinstance(data, str) and data.strip() == "":
            return None
        else:
            return data
    
    def _enhance_references(self, data: Dict[str, Any], document_text: str) -> Dict[str, Any]:
        """Enhance references by finding source text snippets in the document with page numbers."""
        # Ensure references object exists
        if "references" not in data:
            data["references"] = {}
        
        # Find references for key fields
        reference_mappings = {
            "contract_title": data.get("contract_title"),
            "contract_type": data.get("contract_type"),
            "party_1_name": data.get("parties", {}).get("party_1_name"),
            "party_1_address": data.get("parties", {}).get("party_1_address"),
            "party_2_name": data.get("parties", {}).get("party_2_name"),
            "party_2_address": data.get("parties", {}).get("party_2_address"),
            "effective_date": data.get("effective_date"),
            "execution_date": data.get("execution_date"),
            "start_date": data.get("start_date"),
            "end_date": data.get("end_date"),
            "governing_law": data.get("governing_law"),
            "jurisdiction": data.get("jurisdiction"),
            "contract_value": data.get("contract_value"),
            "payment_amount": data.get("payment_terms", {}).get("amount"),
            "payment_currency": data.get("payment_terms", {}).get("currency"),
            "payment_frequency": data.get("payment_terms", {}).get("frequency"),
        }
        
        # Find text snippets for each field
        for ref_key, value in reference_mappings.items():
            if value and value not in [None, ""]:
                existing_ref = data["references"].get(ref_key)
                
                # Convert old string format to new dict format
                if existing_ref and isinstance(existing_ref, str):
                    existing_ref = {"text": existing_ref}
                    data["references"][ref_key] = existing_ref
                
                # If reference doesn't exist or is empty, find it
                if not existing_ref or not existing_ref.get("text"):
                    result = self._find_text_snippet(document_text, str(value))
                    if result:
                        snippet, page_num = result
                        ref_data = {"text": snippet}
                        if page_num:
                            ref_data["page"] = page_num
                        data["references"][ref_key] = ref_data
                elif existing_ref and isinstance(existing_ref, dict) and not existing_ref.get("page"):
                    # Try to find page number for existing reference
                    page_num = self._find_page_number_for_text(existing_ref.get("text", ""), document_text)
                    if page_num:
                        existing_ref["page"] = page_num
        
        # Handle clauses (longer text)
        clause_fields = {
            "confidentiality_clause": data.get("confidentiality_clause"),
            "liability_clause": data.get("liability_clause"),
            "indemnity_clause": data.get("indemnity_clause"),
            "termination_clause": data.get("termination_clause"),
        }
        
        for ref_key, clause_text in clause_fields.items():
            if clause_text and clause_text not in [None, ""]:
                existing_ref = data["references"].get(ref_key)
                
                # Convert old string format to new dict format
                if existing_ref and isinstance(existing_ref, str):
                    existing_ref = {"text": existing_ref}
                    data["references"][ref_key] = existing_ref
                
                if not existing_ref or not existing_ref.get("text"):
                    # For clauses, use a portion of the clause itself as reference
                    snippet = str(clause_text)[:200] if len(str(clause_text)) > 200 else str(clause_text)
                    result = self._find_text_snippet(document_text, snippet)
                    if result:
                        snippet_text, page_num = result
                        ref_data = {"text": snippet_text}
                        if page_num:
                            ref_data["page"] = page_num
                        data["references"][ref_key] = ref_data
                    else:
                        # Fallback: use clause text without page number
                        data["references"][ref_key] = {"text": snippet}
                elif existing_ref and isinstance(existing_ref, dict) and not existing_ref.get("page"):
                    # Try to find page number for existing reference
                    page_num = self._find_page_number_for_text(existing_ref.get("text", ""), document_text)
                    if page_num:
                        existing_ref["page"] = page_num
        
        return data
    
    def _find_text_snippet(self, document_text: str, search_value: str, context_chars: int = 100) -> Optional[tuple]:
        """
        Find a text snippet containing the search value and its page number.
        
        Returns:
            Tuple of (snippet_text, page_number) or None if not found
        """
        if not search_value or not document_text:
            return None
        
        # Normalize for search (case-insensitive, handle dates)
        search_normalized = search_value.lower().strip()
        doc_normalized = document_text.lower()
        
        page_num = None
        
        # Try exact match first
        if search_normalized in doc_normalized:
            idx = doc_normalized.find(search_normalized)
            start = max(0, idx - context_chars)
            end = min(len(document_text), idx + len(search_value) + context_chars)
            snippet = document_text[start:end].strip()
            
            # Find page number
            if self.page_map:
                page_num = self._find_page_number(idx, document_text)
            
            return (snippet[:200], page_num)  # Limit to 200 chars
        
        # Try partial match (for dates in different formats)
        # Extract key parts of the value
        if len(search_value) > 5:
            # Try first few words
            words = search_value.split()[:3]
            partial_search = " ".join(words).lower()
            if partial_search in doc_normalized:
                idx = doc_normalized.find(partial_search)
                start = max(0, idx - context_chars)
                end = min(len(document_text), idx + len(partial_search) + context_chars)
                snippet = document_text[start:end].strip()
                
                # Find page number
                if self.page_map:
                    page_num = self._find_page_number(idx, document_text)
                
                return (snippet[:200], page_num)
        
        return None
    
    def _find_page_number(self, char_index: int, document_text: str) -> Optional[int]:
        """Find the page number for a given character index in the document."""
        if not self.page_map:
            return None
        
        # Calculate cumulative character positions for each page
        cumulative_pos = 0
        for page_num in sorted(self.page_map.keys()):
            page_text = self.page_map[page_num]
            page_length = len(page_text)
            
            if cumulative_pos <= char_index < cumulative_pos + page_length:
                return page_num
            
            cumulative_pos += page_length + 1  # +1 for newline separator
        
        # If not found, return the last page
        if self.page_map:
            return max(self.page_map.keys())
        
        return None
    
    def _find_page_number_for_text(self, search_text: str, document_text: str) -> Optional[int]:
        """Find the page number for a given text snippet."""
        if not search_text or not self.page_map:
            return None
        
        # Find the text in the document
        search_normalized = search_text.lower().strip()[:50]  # Use first 50 chars for matching
        doc_normalized = document_text.lower()
        
        if search_normalized in doc_normalized:
            idx = doc_normalized.find(search_normalized)
            return self._find_page_number(idx, document_text)
        
        return None
    
    def _enhance_with_semantic_search(self, data: Dict[str, Any], document_text: str) -> Dict[str, Any]:
        """Use semantic search to find missing information."""
        if not self.semantic_searcher:
            return data
        
        # Define semantic search queries for missing fields
        search_queries = self._get_semantic_search_queries(data)
        
        if not search_queries:
            return data
        
        # Perform semantic searches
        semantic_results = {}
        for field_key, query_info in search_queries.items():
            try:
                snippets = self.semantic_searcher.find_related_info(
                    document_text,
                    field_key,
                    query_info['description'],
                    top_k=3
                )
                if snippets:
                    semantic_results[field_key] = snippets
            except Exception as e:
                print(f"Warning: Semantic search failed for {field_key}: {str(e)}")
                continue
        
        # If we found semantic results, create an enhanced prompt
        if semantic_results:
            data = self._extract_from_semantic_results(data, semantic_results, document_text)
        
        return data
    
    def _get_semantic_search_queries(self, data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Get semantic search queries for missing fields."""
        queries = {}
        
        # Contract title
        if not data.get("contract_title"):
            queries["contract_title"] = {
                "description": "contract title, agreement name, document title, heading"
            }
        
        # Contract type
        if not data.get("contract_type"):
            queries["contract_type"] = {
                "description": "contract type, agreement type, NDA, MSA, service agreement, license agreement"
            }
        
        # Parties
        parties = data.get("parties", {})
        if not parties.get("party_1_name"):
            queries["party_1_name"] = {
                "description": "first party name, company name, party A, contractor, client, vendor"
            }
        if not parties.get("party_2_name"):
            queries["party_2_name"] = {
                "description": "second party name, company name, party B, contractor, client, vendor"
            }
        
        # Dates
        if not data.get("effective_date"):
            queries["effective_date"] = {
                "description": "effective date, commencement date, start date, date of effect"
            }
        if not data.get("end_date"):
            queries["end_date"] = {
                "description": "end date, expiration date, termination date, expiry date"
            }
        
        # Payment terms
        payment = data.get("payment_terms", {})
        if not payment.get("amount"):
            queries["payment_amount"] = {
                "description": "payment amount, price, cost, fee, payment, compensation, remuneration"
            }
        if not payment.get("currency"):
            queries["payment_currency"] = {
                "description": "currency, USD, EUR, INR, payment currency, monetary unit"
            }
        
        # Governing law
        if not data.get("governing_law"):
            queries["governing_law"] = {
                "description": "governing law, applicable law, jurisdiction law, legal system"
            }
        
        # Clauses
        if not data.get("confidentiality_clause"):
            queries["confidentiality_clause"] = {
                "description": "confidentiality, non-disclosure, NDA, secret, proprietary information"
            }
        if not data.get("termination_clause"):
            queries["termination_clause"] = {
                "description": "termination, cancellation, ending, expiry, contract end"
            }
        
        return queries
    
    def _extract_from_semantic_results(self, data: Dict[str, Any], semantic_results: Dict[str, list[str]], document_text: str) -> Dict[str, Any]:
        """Extract information from semantic search results using LLM."""
        if not semantic_results:
            return data
        
        # Create a prompt with semantic search results
        semantic_context = "SEMANTIC SEARCH RESULTS (relevant sections that may contain the information):\n\n"
        for field_key, snippets in semantic_results.items():
            semantic_context += f"Field: {field_key}\n"
            for i, snippet in enumerate(snippets, 1):
                semantic_context += f"  Result {i}: {snippet[:300]}...\n"
            semantic_context += "\n"
        
        # Create extraction prompt for missing fields
        missing_fields = []
        for field_key in semantic_results.keys():
            if field_key == "contract_title" and not data.get("contract_title"):
                missing_fields.append("contract_title")
            elif field_key == "contract_type" and not data.get("contract_type"):
                missing_fields.append("contract_type")
            elif field_key == "party_1_name" and not data.get("parties", {}).get("party_1_name"):
                missing_fields.append("party_1_name")
            elif field_key == "party_2_name" and not data.get("parties", {}).get("party_2_name"):
                missing_fields.append("party_2_name")
            elif field_key == "effective_date" and not data.get("effective_date"):
                missing_fields.append("effective_date")
            elif field_key == "end_date" and not data.get("end_date"):
                missing_fields.append("end_date")
            elif field_key == "payment_amount" and not data.get("payment_terms", {}).get("amount"):
                missing_fields.append("payment_amount")
            elif field_key == "payment_currency" and not data.get("payment_terms", {}).get("currency"):
                missing_fields.append("payment_currency")
            elif field_key == "governing_law" and not data.get("governing_law"):
                missing_fields.append("governing_law")
            elif field_key == "confidentiality_clause" and not data.get("confidentiality_clause"):
                missing_fields.append("confidentiality_clause")
            elif field_key == "termination_clause" and not data.get("termination_clause"):
                missing_fields.append("termination_clause")
        
        if not missing_fields:
            return data
        
        # Create prompt to extract from semantic results
        extraction_prompt = f"""Based on the following semantic search results, extract the missing contract information.
Only extract information that is clearly present in the search results. If information is not found, return null.

{semantic_context}

Extract the following fields: {', '.join(missing_fields)}

Return a JSON object with only the extracted fields. Use null for fields that cannot be found.

Example format:
{{
  "contract_title": "extracted title or null",
  "party_1_name": "extracted name or null"
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a contract extraction assistant. Extract only information that is clearly present in the provided text. Return null for missing information."
                    },
                    {
                        "role": "user",
                        "content": extraction_prompt
                    }
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            extracted = json.loads(response.choices[0].message.content)
            
            # Merge extracted data into main data structure
            for key, value in extracted.items():
                if value and value != "null":
                    if key == "party_1_name":
                        if "parties" not in data:
                            data["parties"] = {}
                        data["parties"]["party_1_name"] = value
                    elif key == "party_2_name":
                        if "parties" not in data:
                            data["parties"] = {}
                        data["parties"]["party_2_name"] = value
                    elif key == "payment_amount":
                        if "payment_terms" not in data:
                            data["payment_terms"] = {}
                        data["payment_terms"]["amount"] = value
                    elif key == "payment_currency":
                        if "payment_terms" not in data:
                            data["payment_terms"] = {}
                        data["payment_terms"]["currency"] = value
                    else:
                        data[key] = value
                        
        except Exception as e:
            print(f"Warning: Failed to extract from semantic results: {str(e)}")
        
        return data
    
    def _calculate_risk_score(self, data: Dict[str, Any], document_text: str) -> Dict[str, Any]:
        """
        Calculate risk score based on extracted contract data.
        
        Risk factors considered:
        - Missing critical clauses (confidentiality, termination, liability, indemnity)
        - Missing important information (parties, dates, payment terms)
        - Unfavorable terms (unlimited liability, no termination notice)
        - Date-related risks (no end date, auto-renewal without notice)
        - Payment risks (unclear payment terms)
        - Legal risks (no governing law, no jurisdiction)
        
        Returns:
            Dictionary with updated risk_score and risk_details
        """
        risk_factors = []
        risk_score = 0  # Start with 0 (low risk), increase for each risk factor
        max_risk = 100
        
        # 1. Missing Critical Clauses (High Risk: +15 each)
        critical_clauses = {
            "confidentiality_clause": "Confidentiality/NDA clause",
            "termination_clause": "Termination clause",
            "liability_clause": "Liability clause",
            "indemnity_clause": "Indemnity clause"
        }
        
        missing_clauses = []
        for clause_key, clause_name in critical_clauses.items():
            if not data.get(clause_key):
                missing_clauses.append(clause_name)
                risk_score += 15
                risk_factors.append({
                    "factor": f"Missing {clause_name}",
                    "severity": "High",
                    "impact": 15
                })
        
        # 2. Missing Important Information (Medium Risk: +10 each)
        if not data.get("contract_title"):
            risk_score += 5
            risk_factors.append({
                "factor": "Missing contract title",
                "severity": "Medium",
                "impact": 5
            })
        
        parties = data.get("parties", {})
        if not parties.get("party_1_name") or not parties.get("party_2_name"):
            risk_score += 10
            risk_factors.append({
                "factor": "Missing party information",
                "severity": "High",
                "impact": 10
            })
        
        if not data.get("effective_date") and not data.get("start_date"):
            risk_score += 8
            risk_factors.append({
                "factor": "Missing effective/start date",
                "severity": "Medium",
                "impact": 8
            })
        
        if not data.get("end_date"):
            risk_score += 10
            risk_factors.append({
                "factor": "Missing end/expiration date",
                "severity": "High",
                "impact": 10
            })
        
        # 3. Payment Terms Risks (Medium-High Risk: +8 to +12)
        payment = data.get("payment_terms", {})
        if not payment.get("amount") and not data.get("contract_value"):
            risk_score += 8
            risk_factors.append({
                "factor": "Missing payment amount/contract value",
                "severity": "Medium",
                "impact": 8
            })
        
        if not payment.get("currency"):
            risk_score += 5
            risk_factors.append({
                "factor": "Missing payment currency",
                "severity": "Low",
                "impact": 5
            })
        
        # 4. Legal & Jurisdiction Risks (High Risk: +10 each)
        if not data.get("governing_law"):
            risk_score += 10
            risk_factors.append({
                "factor": "Missing governing law",
                "severity": "High",
                "impact": 10
            })
        
        if not data.get("jurisdiction"):
            risk_score += 8
            risk_factors.append({
                "factor": "Missing jurisdiction",
                "severity": "Medium",
                "impact": 8
            })
        
        # 5. Termination & Renewal Risks (Medium-High Risk: +8 to +12)
        if not data.get("termination_notice_period"):
            risk_score += 8
            risk_factors.append({
                "factor": "Missing termination notice period",
                "severity": "Medium",
                "impact": 8
            })
        
        auto_renewal = data.get("auto_renewal", "").lower() if data.get("auto_renewal") else ""
        if "yes" in auto_renewal or "true" in auto_renewal or "automatic" in auto_renewal:
            if not data.get("renewal_terms"):
                risk_score += 10
                risk_factors.append({
                    "factor": "Auto-renewal enabled but renewal terms not specified",
                    "severity": "High",
                    "impact": 10
                })
        
        # 6. Analyze clause content for unfavorable terms (using LLM)
        risk_score, additional_factors = self._analyze_clause_risks(data, document_text, risk_score)
        risk_factors.extend(additional_factors)
        
        # PRIORITY CHECK: Due Date and Amount are critical attributes
        # Check if due_date and amount are missing (contracts use payment_terms structure)
        due_date_missing = False
        amount_missing = False
        
        # Check for due_date (top level or in payment_terms.due_dates)
        if not data.get("due_date"):
            payment = data.get("payment_terms", {})
            due_dates = payment.get("due_dates", [])
            if not due_dates or (isinstance(due_dates, list) and len(due_dates) == 0):
                due_date_missing = True
        else:
            due_date_missing = False
        
        # Check for amount (payment_terms.amount or contract_value)
        payment = data.get("payment_terms", {})
        payment_amount = payment.get("amount") if payment else None
        contract_value = data.get("contract_value")
        if not payment_amount and not contract_value:
            amount_missing = True
        
        # Apply priority rules: Both missing = High risk (>=60), One missing = Medium risk (>=30)
        if due_date_missing and amount_missing:
            # Both critical attributes missing - ensure High risk minimum
            if risk_score < 60:
                risk_score = 60
                risk_factors.append({
                    "factor": "Priority: Both due date and amount missing - High risk enforced",
                    "severity": "High",
                    "impact": 0
                })
        elif due_date_missing or amount_missing:
            # One critical attribute missing - ensure Medium risk minimum
            if risk_score < 30:
                risk_score = 30
                risk_factors.append({
                    "factor": "Priority: One critical attribute (due date or amount) missing - Medium risk enforced",
                    "severity": "Medium",
                    "impact": 0
                })
        
        # Cap risk score at max_risk
        risk_score = min(risk_score, max_risk)
        
        # Determine risk level
        if risk_score < 30:
            risk_level = "Low"
            risk_category = "🟢 Low Risk"
        elif risk_score < 60:
            risk_level = "Medium"
            risk_category = "🟡 Medium Risk"
        elif risk_score < 80:
            risk_level = "High"
            risk_category = "🟠 High Risk"
        else:
            risk_level = "Critical"
            risk_category = "🔴 Critical Risk"
        
        # Update data with risk score and details
        data["risk_score"] = {
            "score": risk_score,
            "level": risk_level,
            "category": risk_category,
            "max_score": max_risk,
            "risk_factors": risk_factors,
            "missing_clauses": missing_clauses
        }
        
        # Also update missing_clauses field if not already set
        if not data.get("missing_clauses") or len(data.get("missing_clauses", [])) == 0:
            data["missing_clauses"] = missing_clauses
        
        return data
    
    def _analyze_clause_risks(self, data: Dict[str, Any], document_text: str, current_risk: int) -> tuple:
        """
        Analyze clause content for unfavorable terms using LLM.
        
        Returns:
            Tuple of (updated_risk_score, additional_risk_factors)
        """
        additional_factors = []
        risk_increase = 0
        
        # Check for high-risk terms in key clauses
        high_risk_keywords = {
            "liability_clause": {
                "unlimited": 15,
                "no limit": 15,
                "without limitation": 12,
                "all liability": 10
            },
            "indemnity_clause": {
                "unlimited": 12,
                "all losses": 10,
                "any and all": 8
            },
            "termination_clause": {
                "no termination": 15,
                "cannot terminate": 15,
                "perpetual": 12
            }
        }
        
        for clause_key, keywords in high_risk_keywords.items():
            clause_text = data.get(clause_key, "").lower() if data.get(clause_key) else ""
            if clause_text:
                for keyword, impact in keywords.items():
                    if keyword in clause_text:
                        risk_increase += impact
                        additional_factors.append({
                            "factor": f"Unfavorable term in {clause_key.replace('_', ' ')}: '{keyword}'",
                            "severity": "High" if impact >= 12 else "Medium",
                            "impact": impact
                        })
                        break  # Only count once per clause
        
        # Use LLM for deeper analysis if we have significant clauses
        if data.get("liability_clause") or data.get("indemnity_clause") or data.get("termination_clause"):
            try:
                analysis_prompt = f"""Analyze the following contract clauses for potential risks. 
Focus on unfavorable terms that could expose parties to excessive liability, lack of protection, or unfair conditions.

Liability Clause: {data.get('liability_clause', 'Not specified')}
Indemnity Clause: {data.get('indemnity_clause', 'Not specified')}
Termination Clause: {data.get('termination_clause', 'Not specified')}
Penalty Terms: {data.get('penalty_terms', 'Not specified')}

Identify any high-risk terms such as:
- Unlimited liability
- Excessive penalties
- One-sided indemnification
- Unfair termination conditions
- Lack of protection for one party

Return a JSON object with:
{{
  "risk_factors": [
    {{
      "factor": "description of the risk",
      "severity": "High/Medium/Low",
      "impact": <number 0-20>
    }}
  ],
  "total_risk_increase": <total additional risk points>
}}

If no significant risks are found, return {{"risk_factors": [], "total_risk_increase": 0}}"""

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a contract risk analyst. Analyze clauses for potential risks and return structured JSON."
                        },
                        {
                            "role": "user",
                            "content": analysis_prompt
                        }
                    ],
                    temperature=0.2,
                    response_format={"type": "json_object"}
                )
                
                analysis_result = json.loads(response.choices[0].message.content)
                
                if analysis_result.get("risk_factors"):
                    additional_factors.extend(analysis_result["risk_factors"])
                    risk_increase += analysis_result.get("total_risk_increase", 0)
                    
            except Exception as e:
                print(f"Warning: Could not perform deep clause analysis: {str(e)}")
        
        return (current_risk + risk_increase, additional_factors)

