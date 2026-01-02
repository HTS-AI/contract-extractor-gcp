"""
Extraction Orchestrator
Coordinates document type detection and routes to appropriate extractor.
Works seamlessly with vision_gcp.py for OCR processing.
"""

import os
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Import document parser (works with vision_gcp.py)
from document_parser import DocumentParser

# Import document type classifier
try:
    from document_type_classifier import classify_document_type
except ImportError:
    classify_document_type = None

# Import type-specific extractors
try:
    from lease_extractor import LeaseExtractor
except ImportError:
    LeaseExtractor = None

try:
    from nda_extractor import NDAExtractor
except ImportError:
    NDAExtractor = None

try:
    from contract_extractor_specific import ContractExtractorSpecific
except ImportError:
    ContractExtractorSpecific = None

# Import semantic search if available
try:
    from semantic_search import SemanticSearcher
except ImportError:
    SemanticSearcher = None


class ExtractionOrchestrator:
    """
    Orchestrates the entire extraction process:
    1. Parses document (works with vision_gcp.py for scanned PDFs)
    2. Classifies document type (Lease, NDA, or Contract)
    3. Routes to appropriate extractor
    4. Returns unified extraction results
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        use_gcs_vision: bool = True,
        service_account_file: Optional[str] = None,
        use_semantic_search: bool = True,
        document_id: Optional[str] = None
    ):
        """
        Initialize the extraction orchestrator.
        
        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY env var.
            use_gcs_vision: If True, use Google Cloud Vision API for scanned PDFs
            service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
            use_semantic_search: Whether to use semantic search for missing fields
            document_id: Unique identifier for the document (for vector DB)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.use_gcs_vision = use_gcs_vision
        # service_account_file is deprecated - credentials come from GCP_CREDENTIALS_JSON env var
        if service_account_file:
            import warnings
            warnings.warn(
                "service_account_file parameter is deprecated. "
                "Using GCP_CREDENTIALS_JSON from environment instead.",
                DeprecationWarning
            )
        self.service_account_file = None  # Not used anymore
        self.document_id = document_id
        
        # Initialize document parser (uses GCP_CREDENTIALS_JSON from environment)
        self.parser = DocumentParser(
            use_gcs_vision=use_gcs_vision,
            service_account_file=None  # Uses GCP_CREDENTIALS_JSON from environment
        )
        
        # Initialize type-specific extractors
        self.lease_extractor = LeaseExtractor(api_key=self.api_key) if LeaseExtractor else None
        self.nda_extractor = NDAExtractor(api_key=self.api_key) if NDAExtractor else None
        self.contract_extractor = ContractExtractorSpecific(api_key=self.api_key) if ContractExtractorSpecific else None
        
        # Initialize semantic searcher if available
        self.use_semantic_search = use_semantic_search and SemanticSearcher is not None
        self.semantic_searcher = SemanticSearcher(api_key=self.api_key, use_faiss=True) if self.use_semantic_search else None
        
        # Store page map for reference finding
        self.page_map = {}
    
    def extract_from_file(
        self,
        file_path: str,
        use_ocr: bool = False
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract data from a file (PDF, DOCX, TXT).
        Works seamlessly with vision_gcp.py for scanned PDFs.
        
        Args:
            file_path: Path to the document file
            use_ocr: If True, use OCR for PDF files
            
        Returns:
            Tuple of (extracted_data, metadata) where:
            - extracted_data: Extracted contract data
            - metadata: Metadata about the extraction (document_type, confidence, etc.)
        """
        # Step 1: Parse document (this will use vision_gcp.py if scanned PDF detected)
        print(f"Step 1: Parsing document: {file_path}")
        document_text, page_map = self.parser.parse_with_pages(file_path, use_ocr=use_ocr)
        
        # Step 2: Classify document type
        print("Step 2: Classifying document type...")
        document_type_info = self._classify_document(document_text)
        detected_type = document_type_info.get("document_type", "CONTRACT")
        
        print(f"Document classified as: {detected_type} (Confidence: {document_type_info.get('confidence', 'UNKNOWN')})")
        
        # Step 3: Route to appropriate extractor
        print(f"Step 3: Extracting data using {detected_type} extractor...")
        extracted_data = self._route_to_extractor(document_text, detected_type, page_map)
        
        # Step 4: Add metadata
        metadata = {
            "document_type": detected_type,
            "classification_confidence": document_type_info.get("confidence", "MEDIUM"),
            "classification_reasoning": document_type_info.get("reasoning", ""),
            "file_path": file_path,
            "file_name": Path(file_path).name,
            "extraction_method": "type_specific",
            "page_map": page_map,
            "document_text": document_text  # Include document text in metadata
        }
        
        # Step 4.5: Add quality metadata if available (from blur detection/enhancement)
        if hasattr(self.parser, 'get_quality_metadata'):
            quality_metadata = self.parser.get_quality_metadata()
            if quality_metadata:
                metadata["image_quality"] = quality_metadata
                # Add quality warning if needed
                if quality_metadata.get("needs_attention"):
                    blurry_pages = quality_metadata.get("blurry_pages", [])
                    total_pages = quality_metadata.get("total_pages", 1)
                    metadata["quality_warning"] = (
                        f"⚠️ Document quality warning: {len(blurry_pages)}/{total_pages} page(s) "
                        f"were blurry and have been enhanced. Some text may still be inaccurate. "
                        f"Consider re-scanning at higher resolution for better results."
                    )
        
        # Step 5: Enhance with semantic search if enabled
        if self.use_semantic_search and self.semantic_searcher:
            print("Step 4: Enhancing with semantic search...")
            try:
                doc_id = self.document_id or f"doc_{hash(document_text) % 100000}"
                self.semantic_searcher.initialize_vector_db(document_text, doc_id, page_map=page_map)
                extracted_data = self._enhance_with_semantic_search(extracted_data, document_text)
            except Exception as e:
                print(f"Warning: Semantic search enhancement failed: {e}")
        
        # Step 6: Add references
        extracted_data = self._add_references(extracted_data, document_text, page_map)
        
        # Step 6.5: Assign account type based on document type if not present
        extracted_data = self._assign_account_type_if_missing(extracted_data, detected_type)
        
        # Step 6.6: Extract and normalize currency
        extracted_data = self._extract_currency(extracted_data, document_text)
        
        # Step 6.7: Calculate per-period amount from total payment and frequency
        extracted_data = self._calculate_period_amount(extracted_data)
        
        # Step 7: Calculate risk score
        extracted_data = self._calculate_risk_score(extracted_data, document_text)
        
        return extracted_data, metadata
    
    def extract_from_text(
        self,
        document_text: str,
        page_map: Optional[Dict[int, str]] = None
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Extract data from raw text.
        
        Args:
            document_text: Raw text from document
            page_map: Optional dictionary mapping page numbers to text content
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        # Step 1: Store page map
        self.page_map = page_map or {}
        
        # Step 2: Classify document type
        print("Step 1: Classifying document type...")
        document_type_info = self._classify_document(document_text)
        detected_type = document_type_info.get("document_type", "CONTRACT")
        
        print(f"Document classified as: {detected_type} (Confidence: {document_type_info.get('confidence', 'UNKNOWN')})")
        
        # Step 3: Route to appropriate extractor
        print(f"Step 2: Extracting data using {detected_type} extractor...")
        extracted_data = self._route_to_extractor(document_text, detected_type, page_map or {})
        
        # Step 4: Add metadata
        metadata = {
            "document_type": detected_type,
            "classification_confidence": document_type_info.get("confidence", "MEDIUM"),
            "classification_reasoning": document_type_info.get("reasoning", ""),
            "extraction_method": "type_specific",
            "page_map": page_map or {},
            "document_text": document_text  # Include document text in metadata
        }
        
        # Step 5: Enhance with semantic search if enabled
        if self.use_semantic_search and self.semantic_searcher:
            print("Step 3: Enhancing with semantic search...")
            try:
                doc_id = self.document_id or f"doc_{hash(document_text) % 100000}"
                self.semantic_searcher.initialize_vector_db(document_text, doc_id, page_map=page_map or {})
                extracted_data = self._enhance_with_semantic_search(extracted_data, document_text)
            except Exception as e:
                print(f"Warning: Semantic search enhancement failed: {e}")
        
        # Step 6: Add references
        extracted_data = self._add_references(extracted_data, document_text, page_map or {})
        
        # Step 6.5: Assign account type based on document type if not present
        extracted_data = self._assign_account_type_if_missing(extracted_data, detected_type)
        
        # Step 6.6: Calculate per-period amount from total payment and frequency
        extracted_data = self._calculate_period_amount(extracted_data)
        
        # Step 7: Calculate risk score
        extracted_data = self._calculate_risk_score(extracted_data, document_text)
        
        return extracted_data, metadata
    
    def _classify_document(self, document_text: str) -> Dict[str, Any]:
        """Classify the document type."""
        if classify_document_type:
            try:
                return classify_document_type(document_text, api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Document classification failed: {e}")
                return {"document_type": "CONTRACT", "confidence": "LOW", "reasoning": "Classification failed, defaulting to CONTRACT"}
        else:
            return {"document_type": "CONTRACT", "confidence": "LOW", "reasoning": "Classifier not available, defaulting to CONTRACT"}
    
    def _route_to_extractor(
        self,
        document_text: str,
        document_type: str,
        page_map: Dict[int, str]
    ) -> Dict[str, Any]:
        """Route to the appropriate extractor based on document type."""
        document_type = document_type.upper()
        
        if document_type == "LEASE" and self.lease_extractor:
            print("Using Lease Extractor...")
            extracted_data = self.lease_extractor.extract(document_text)
        elif document_type == "NDA" and self.nda_extractor:
            print("Using NDA Extractor...")
            extracted_data = self.nda_extractor.extract(document_text)
        elif document_type == "CONTRACT" and self.contract_extractor:
            print("Using Contract Extractor...")
            extracted_data = self.contract_extractor.extract(document_text)
        else:
            # Fallback: use contract extractor if specific extractor not available
            print(f"Warning: {document_type} extractor not available, using Contract Extractor as fallback...")
            if self.contract_extractor:
                extracted_data = self.contract_extractor.extract(document_text)
            else:
                raise ValueError(f"No extractor available for document type: {document_type}")
        
        # Store document classification info
        extracted_data["document_classification"] = {
            "detected_type": document_type,
            "extraction_method": "type_specific"
        }
        
        return extracted_data
    
    def _enhance_with_semantic_search(
        self,
        extracted_data: Dict[str, Any],
        document_text: str
    ) -> Dict[str, Any]:
        """Enhance extracted data using semantic search for missing fields."""
        if not self.semantic_searcher:
            return extracted_data
        
        # Define semantic search queries for missing fields
        search_queries = self._get_semantic_search_queries(extracted_data)
        
        if not search_queries:
            return extracted_data
        
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
            extracted_data = self._extract_from_semantic_results(extracted_data, semantic_results, document_text)
        
        return extracted_data
    
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
        
        # Parties - check based on document type structure
        # For lease documents
        if "lessor_lessee_information" in data:
            lessor_lessee = data.get("lessor_lessee_information", {})
            if not lessor_lessee.get("lessor_name"):
                queries["lessor_name"] = {
                    "description": "lessor name, landlord name, property owner"
                }
            if not lessor_lessee.get("lessee_name"):
                queries["lessee_name"] = {
                    "description": "lessee name, tenant name, renter"
                }
        # For NDA documents
        elif "parties_to_agreement" in data:
            parties = data.get("parties_to_agreement", {})
            if not parties.get("disclosing_party_name"):
                queries["disclosing_party_name"] = {
                    "description": "disclosing party, party sharing information"
                }
            if not parties.get("receiving_party_name"):
                queries["receiving_party_name"] = {
                    "description": "receiving party, party receiving information"
                }
        # For contract documents
        elif "parties_involved" in data:
            parties = data.get("parties_involved", {})
            if not parties.get("customer_name"):
                queries["customer_name"] = {
                    "description": "customer name, client name, party A"
                }
            if not parties.get("telecom_provider_name"):
                queries["telecom_provider_name"] = {
                    "description": "telecom provider, service provider, party B"
                }
        # Generic parties structure (fallback)
        else:
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
        if not data.get("effective_date") and not data.get("start_date"):
            queries["effective_date"] = {
                "description": "effective date, commencement date, start date, date of effect"
            }
        if not data.get("end_date"):
            queries["end_date"] = {
                "description": "end date, expiration date, termination date, expiry date"
            }
        
        # Payment terms - check based on document type
        if "rent_payment_schedule" in data:
            payment = data.get("rent_payment_schedule", {})
            if not payment.get("monthly_rent") and not payment.get("annual_rent"):
                queries["rent_amount"] = {
                    "description": "rent amount, monthly rent, annual rent, rental payment"
                }
        elif "payment_terms" in data:
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
        if "governing_law_jurisdiction" in data:
            law = data.get("governing_law_jurisdiction", {})
            if not law.get("governing_law"):
                queries["governing_law"] = {
                    "description": "governing law, applicable law, jurisdiction law, legal system"
                }
        elif not data.get("governing_law"):
            queries["governing_law"] = {
                "description": "governing law, applicable law, jurisdiction law, legal system"
            }
        
        # Clauses
        if not data.get("confidentiality_clause") and not data.get("confidentiality_obligations"):
            queries["confidentiality_clause"] = {
                "description": "confidentiality, non-disclosure, NDA, secret, proprietary information"
            }
        if not data.get("termination_clause"):
            queries["termination_clause"] = {
                "description": "termination, cancellation, ending, expiry, contract end"
            }
        
        return queries
    
    def _extract_from_semantic_results(
        self,
        data: Dict[str, Any],
        semantic_results: Dict[str, list],
        document_text: str
    ) -> Dict[str, Any]:
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
        missing_fields = list(semantic_results.keys())
        
        if not missing_fields:
            return data
        
        # Create prompt to extract from semantic results
        extraction_prompt = f"""Based on the following semantic search results, extract the missing contract information.
Only extract information that is clearly present in the search results. If information is not found, return null.

{semantic_context}

Extract the following fields: {', '.join(missing_fields)}

Return a JSON object with only the extracted fields. Use null for fields that cannot be found."""
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            response = client.chat.completions.create(
                model="gpt-4o-mini",
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
            
            import json
            extracted = json.loads(response.choices[0].message.content)
            
            # Merge extracted data into main data structure
            for key, value in extracted.items():
                if value and value != "null":
                    # Handle nested structures based on document type
                    if key in ["lessor_name", "lessee_name"]:
                        if "lessor_lessee_information" not in data:
                            data["lessor_lessee_information"] = {}
                        data["lessor_lessee_information"][key] = value
                    elif key in ["disclosing_party_name", "receiving_party_name"]:
                        if "parties_to_agreement" not in data:
                            data["parties_to_agreement"] = {}
                        data["parties_to_agreement"][key] = value
                    elif key in ["customer_name", "telecom_provider_name"]:
                        if "parties_involved" not in data:
                            data["parties_involved"] = {}
                        data["parties_involved"][key] = value
                    elif key in ["party_1_name", "party_2_name"]:
                        if "parties" not in data:
                            data["parties"] = {}
                        data["parties"][key] = value
                    elif key in ["payment_amount", "payment_currency"]:
                        if "payment_terms" not in data:
                            data["payment_terms"] = {}
                        data["payment_terms"][key.replace("payment_", "")] = value
                    elif key == "rent_amount":
                        if "rent_payment_schedule" not in data:
                            data["rent_payment_schedule"] = {}
                        # Try to determine if monthly or annual
                        if "monthly" in str(value).lower():
                            data["rent_payment_schedule"]["monthly_rent"] = value
                        else:
                            data["rent_payment_schedule"]["annual_rent"] = value
                    else:
                        data[key] = value
                        
        except Exception as e:
            print(f"Warning: Failed to extract from semantic results: {str(e)}")
        
        return data
    
    def _add_references(
        self,
        extracted_data: Dict[str, Any],
        document_text: str,
        page_map: Dict[int, str]
    ) -> Dict[str, Any]:
        """Add references (source text snippets) to extracted data."""
        # Ensure references object exists
        if "references" not in extracted_data:
            extracted_data["references"] = {}
        
        # Store page_map for reference finding
        self.page_map = page_map
        
        # Find references for key fields - new simplified structure
        reference_mappings = {}
        
        # Document type
        if extracted_data.get("document_type"):
            reference_mappings["document_type"] = extracted_data["document_type"]
        
        # Party names
        if "party_names" in extracted_data:
            parties = extracted_data.get("party_names", {})
            if parties.get("party_1"):
                reference_mappings["party_1"] = parties["party_1"]
            if parties.get("party_2"):
                reference_mappings["party_2"] = parties["party_2"]
            # Store all party names together for reference
            all_parties = []
            if parties.get("party_1"):
                all_parties.append(parties["party_1"])
            if parties.get("party_2"):
                all_parties.append(parties["party_2"])
            if parties.get("additional_parties"):
                all_parties.extend([str(p) for p in parties["additional_parties"]])
            if all_parties:
                reference_mappings["party_names"] = ", ".join(all_parties)
        
        # Dates
        if extracted_data.get("start_date"):
            reference_mappings["start_date"] = extracted_data["start_date"]
        if extracted_data.get("due_date"):
            reference_mappings["due_date"] = extracted_data["due_date"]
        
        # Payment information
        if extracted_data.get("amount"):
            # For amount, extract only the numeric part for better matching
            # If amount is "INR 80,000", search for "80000" or "80,000"
            amount_str = str(extracted_data["amount"])
            # Extract numeric value (remove currency, keep number with or without comma)
            import re
            numeric_match = re.search(r'[\d,]+\.?\d*', amount_str)
            if numeric_match:
                reference_mappings["amount"] = numeric_match.group()  # e.g., "80,000" or "80000"
            else:
                reference_mappings["amount"] = extracted_data["amount"]
        if extracted_data.get("frequency"):
            reference_mappings["frequency"] = extracted_data["frequency"]
        
        # Account type
        if extracted_data.get("account_type"):
            reference_mappings["account_type"] = extracted_data["account_type"]
        
        # Compliance violations
        if extracted_data.get("rules_and_compliance_violation"):
            reference_mappings["rules_and_compliance_violation"] = extracted_data["rules_and_compliance_violation"]
        
        # Find text snippets for each field
        for ref_key, value in reference_mappings.items():
            if value and value not in [None, ""]:
                existing_ref = extracted_data["references"].get(ref_key)
                
                # Convert old string format to new dict format
                if existing_ref and isinstance(existing_ref, str):
                    existing_ref = {"text": existing_ref}
                    extracted_data["references"][ref_key] = existing_ref
                
                # If reference doesn't exist or is empty, find it
                if not existing_ref or not existing_ref.get("text"):
                    print(f"[REFERENCE] Searching for {ref_key}: '{str(value)[:50]}...'")
                    result = self._find_text_snippet(document_text, str(value))
                    if result:
                        snippet, page_num = result
                        ref_data = {"text": snippet}
                        if page_num:
                            ref_data["page"] = page_num
                        extracted_data["references"][ref_key] = ref_data
                        print(f"[REFERENCE] {ref_key}: Found on page {page_num if page_num else 'unknown'}")
                    else:
                        print(f"[REFERENCE] {ref_key}: NOT FOUND in document (value: {str(value)})")
                elif existing_ref and isinstance(existing_ref, dict) and not existing_ref.get("page"):
                    # Try to find page number for existing reference
                    print(f"[REFERENCE] Finding page number for {ref_key}...")
                    page_num = self._find_page_number_for_text(existing_ref.get("text", ""), document_text)
                    if page_num:
                        existing_ref["page"] = page_num
                        print(f"[REFERENCE] {ref_key}: Page number added: {page_num}")
                    else:
                        print(f"[REFERENCE] {ref_key}: Page number not found")
                else:
                    # Already has reference with page
                    if existing_ref and existing_ref.get("page"):
                        print(f"[REFERENCE] {ref_key}: Already has reference (Page {existing_ref.get('page')})")
        
        # Handle compliance violations (longer text)
        if extracted_data.get("rules_and_compliance_violation"):
            violation_text = extracted_data["rules_and_compliance_violation"]
            existing_ref = extracted_data["references"].get("rules_and_compliance_violation")
            
            if not existing_ref or not existing_ref.get("text"):
                # Use a portion of the violation text as reference
                snippet = str(violation_text)[:200] if len(str(violation_text)) > 200 else str(violation_text)
                result = self._find_text_snippet(document_text, snippet)
                if result:
                    snippet_text, page_num = result
                    ref_data = {"text": snippet_text}
                    if page_num:
                        ref_data["page"] = page_num
                    extracted_data["references"]["rules_and_compliance_violation"] = ref_data
                else:
                    # Fallback: use violation text without page number
                    extracted_data["references"]["rules_and_compliance_violation"] = {"text": snippet}
            elif existing_ref and isinstance(existing_ref, dict) and not existing_ref.get("page"):
                # Try to find page number for existing reference
                page_num = self._find_page_number_for_text(existing_ref.get("text", ""), document_text)
                if page_num:
                    existing_ref["page"] = page_num
        
        return extracted_data
    
    def _find_text_snippet(self, document_text: str, search_value: str, context_chars: int = 100) -> Optional[Tuple[str, Optional[int]]]:
        """
        Find a text snippet containing the search value and its page number.
        Uses advanced techniques: page-by-page search, regex, fuzzy matching, sliding window.
        
        Returns:
            Tuple of (snippet_text, page_number) or None if not found
        """
        if not search_value or not document_text:
            return None
        
        import re
        from fuzzywuzzy import fuzz
        
        # Normalize whitespace and punctuation for search
        search_normalized = re.sub(r'\s+', ' ', search_value.lower().strip())
        search_no_punct = re.sub(r'[^\w\s]', ' ', search_normalized)
        search_no_punct = re.sub(r'\s+', ' ', search_no_punct).strip()
        
        # STRATEGY 1: Page-by-page exact and fuzzy search
        if self.page_map:
            for page_num in sorted(self.page_map.keys()):
                page_text = self.page_map[page_num]
                page_normalized = re.sub(r'\s+', ' ', page_text.lower())
                page_no_punct = re.sub(r'[^\w\s]', ' ', page_normalized)
                page_no_punct = re.sub(r'\s+', ' ', page_no_punct).strip()
                
                # 1A. Try exact match with whitespace normalization
                if search_normalized in page_normalized:
                    idx = page_normalized.find(search_normalized)
                    if idx != -1:
                        start = max(0, idx - context_chars)
                        end = min(len(page_text), idx + len(search_value) + context_chars)
                        snippet = page_text[start:end].strip()
                        print(f"[MATCH] Found exact match on page {page_num}")
                        return (snippet[:200], page_num)
                
                # 1B. Try without punctuation
                if len(search_no_punct) > 5 and search_no_punct in page_no_punct:
                    idx = page_no_punct.find(search_no_punct)
                    if idx != -1:
                        start = max(0, idx - context_chars)
                        end = min(len(page_text), idx + len(search_no_punct) + context_chars)
                        snippet = page_text[start:end].strip()
                        print(f"[MATCH] Found no-punct match on page {page_num}")
                        return (snippet[:200], page_num)
                
                # 1C. Try regex with word boundaries (finds "X" in "blah X blah")
                if len(search_no_punct) > 5:
                    try:
                        # Escape special regex chars but allow partial matching
                        words = search_no_punct.split()
                        if len(words) >= 2:
                            # Create pattern that finds the phrase with flexible word boundaries
                            pattern = r'\b' + r'\s+'.join(re.escape(word) for word in words) + r'\b'
                            regex = re.compile(pattern, re.IGNORECASE)
                            match = regex.search(page_text)
                            if match:
                                idx = match.start()
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(match.group()) + context_chars)
                                snippet = page_text[start:end].strip()
                                print(f"[MATCH] Found regex match on page {page_num}: '{match.group()}'")
                                return (snippet[:200], page_num)
                    except:
                        pass
                
                # 1D. Fuzzy matching with sliding window (for embedded text)
                if len(search_no_punct) > 10:
                    words = page_no_punct.split()
                    search_word_count = len(search_no_punct.split())
                    
                    # Slide through text with window size = search length +/- 30%
                    for window_size in [search_word_count, search_word_count + 2, search_word_count + 4]:
                        if window_size > len(words):
                            continue
                            
                        for i in range(len(words) - window_size + 1):
                            window = ' '.join(words[i:i + window_size])
                            # Use fuzzy matching
                            ratio = fuzz.ratio(search_no_punct, window)
                            if ratio >= 85:  # 85% similarity threshold
                                # Find position in original text
                                window_pattern = r'\b' + r'\s+'.join(re.escape(w) for w in words[i:i + window_size]) + r'\b'
                                try:
                                    regex = re.compile(window_pattern, re.IGNORECASE)
                                    match = regex.search(page_text)
                                    if match:
                                        idx = match.start()
                                        start = max(0, idx - context_chars)
                                        end = min(len(page_text), idx + len(match.group()) + context_chars)
                                        snippet = page_text[start:end].strip()
                                        print(f"[MATCH] Found fuzzy match on page {page_num} (ratio: {ratio}%): '{match.group()}'")
                                        return (snippet[:200], page_num)
                                except:
                                    pass
        
        # Fallback: search entire document
        doc_normalized = re.sub(r'\s+', ' ', document_text.lower())
        if search_normalized in doc_normalized:
            idx = doc_normalized.find(search_normalized)
            start = max(0, idx - context_chars)
            end = min(len(document_text), idx + len(search_value) + context_chars)
            snippet = document_text[start:end].strip()
            
            page_num = None
            if self.page_map:
                page_num = self._find_page_number(idx, document_text)
            
            print(f"[MATCH] Found in full document fallback (page {page_num})")
            return (snippet[:200], page_num)
        
        # Try date format variations (for dates in ISO format like 2016-04-21)
        if self._is_iso_date(search_value):
            date_variations = self._generate_date_variations(search_value)
            
            # Search page by page to prioritize earlier pages
            if self.page_map:
                for page_num in sorted(self.page_map.keys()):
                    page_text = self.page_map[page_num]
                    page_normalized = re.sub(r'\s+', ' ', page_text.lower())
                    
                    for date_variant in date_variations:
                        variant_normalized = re.sub(r'\s+', ' ', date_variant.lower())
                        # Also try without punctuation
                        variant_no_punct = re.sub(r'[^\w\s]', ' ', variant_normalized)
                        variant_no_punct = re.sub(r'\s+', ' ', variant_no_punct).strip()
                        page_no_punct = re.sub(r'[^\w\s]', ' ', page_normalized)
                        page_no_punct = re.sub(r'\s+', ' ', page_no_punct).strip()
                        
                        if variant_normalized in page_normalized:
                            idx = page_normalized.find(variant_normalized)
                            if idx != -1:
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(date_variant) + context_chars)
                                snippet = page_text[start:end].strip()
                                return (snippet[:200], page_num)
                        
                        # Try without punctuation
                        if len(variant_no_punct) > 5 and variant_no_punct in page_no_punct:
                            idx = page_no_punct.find(variant_no_punct)
                            if idx != -1:
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(date_variant) + context_chars)
                                snippet = page_text[start:end].strip()
                                return (snippet[:200], page_num)
        
        # Try number/amount variations (for amounts like 55000 which might appear as 55,000)
        if self._is_number(search_value):
            number_variations = self._generate_number_variations(search_value)
            
            # Search page by page to prioritize earlier pages
            if self.page_map:
                for page_num in sorted(self.page_map.keys()):
                    page_text = self.page_map[page_num]
                    page_normalized = re.sub(r'\s+', ' ', page_text.lower())
                    
                    for number_variant in number_variations:
                        if number_variant.lower() in page_normalized:
                            idx = page_normalized.find(number_variant.lower())
                            if idx != -1:
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(number_variant) + context_chars)
                                snippet = page_text[start:end].strip()
                                return (snippet[:200], page_num)
            
            # Fallback: search entire document
            doc_normalized = re.sub(r'\s+', ' ', document_text.lower())
            for number_variant in number_variations:
                if number_variant.lower() in doc_normalized:
                    idx = doc_normalized.find(number_variant.lower())
                    start = max(0, idx - context_chars)
                    end = min(len(document_text), idx + len(number_variant) + context_chars)
                    snippet = document_text[start:end].strip()
                    
                    # Find page number
                    page_num = None
                    if self.page_map:
                        page_num = self._find_page_number(idx, document_text)
                    
                    return (snippet[:200], page_num)
            
            # Try regex-based search for more flexible matching (page by page)
            try:
                num_value = float(str(search_value).strip())
                if num_value == int(num_value):
                    num_int = int(num_value)
                    # Create regex pattern that matches the number with various separators and currency symbols
                    num_str = str(num_int)
                    pattern_parts = []
                    for i, digit in enumerate(num_str):
                        pattern_parts.append(digit)
                        remaining = len(num_str) - i - 1
                        if remaining > 0 and remaining % 3 == 0:
                            pattern_parts.append('[,\\s.]*')
                    
                    number_pattern = ''.join(pattern_parts)
                    full_pattern = r'(?:Rs\.?\s*|INR\s*|USD\s*|\$\s*)?' + number_pattern + r'(?:\s*(?:INR|USD|Rs))?'
                    regex = re.compile(full_pattern, re.IGNORECASE)
                    
                    # Search page by page
                    if self.page_map:
                        for page_num in sorted(self.page_map.keys()):
                            page_text = self.page_map[page_num]
                            match = regex.search(page_text)
                            if match:
                                idx = match.start()
                                matched_text = match.group()
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(matched_text) + context_chars)
                                snippet = page_text[start:end].strip()
                                return (snippet[:200], page_num)
                    
                    # Fallback: search entire document
                    match = regex.search(document_text)
                    if match:
                        idx = match.start()
                        matched_text = match.group()
                        start = max(0, idx - context_chars)
                        end = min(len(document_text), idx + len(matched_text) + context_chars)
                        snippet = document_text[start:end].strip()
                        
                        page_num = None
                        if self.page_map:
                            page_num = self._find_page_number(idx, document_text)
                        
                        return (snippet[:200], page_num)
            except:
                pass
        
        # Try partial match with regex and fuzzy (for party names and other text)
        if len(search_value) > 5:
            from fuzzywuzzy import fuzz
            words = search_value.split()
            
            for word_count in [len(words), min(5, len(words)), min(4, len(words)), min(3, len(words))]:
                if word_count < 2:
                    continue
                    
                partial_words = words[:word_count]
                partial_search = re.sub(r'\s+', ' ', " ".join(partial_words).lower())
                partial_no_punct = re.sub(r'[^\w\s]', ' ', partial_search)
                partial_no_punct = re.sub(r'\s+', ' ', partial_no_punct).strip()
                
                # Search page by page to prioritize earlier pages
                if self.page_map:
                    for page_num in sorted(self.page_map.keys()):
                        page_text = self.page_map[page_num]
                        page_normalized = re.sub(r'\s+', ' ', page_text.lower())
                        page_no_punct = re.sub(r'[^\w\s]', ' ', page_normalized)
                        page_no_punct = re.sub(r'\s+', ' ', page_no_punct).strip()
                        
                        # Try with whitespace normalization
                        if partial_search in page_normalized:
                            idx = page_normalized.find(partial_search)
                            if idx != -1:
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(partial_search) + context_chars)
                                snippet = page_text[start:end].strip()
                                print(f"[PARTIAL] Found partial match on page {page_num}")
                                return (snippet[:200], page_num)
                        
                        # Try without punctuation
                        if len(partial_no_punct) > 5 and partial_no_punct in page_no_punct:
                            idx = page_no_punct.find(partial_no_punct)
                            if idx != -1:
                                start = max(0, idx - context_chars)
                                end = min(len(page_text), idx + len(partial_no_punct) + context_chars)
                                snippet = page_text[start:end].strip()
                                print(f"[PARTIAL] Found partial no-punct match on page {page_num}")
                                return (snippet[:200], page_num)
                        
                        # Try regex with word boundaries
                        if len(partial_no_punct) > 5:
                            try:
                                pattern = r'\b' + r'\s+'.join(re.escape(w) for w in partial_words) + r'\b'
                                regex_obj = re.compile(pattern, re.IGNORECASE)
                                match = regex_obj.search(page_text)
                                if match:
                                    idx = match.start()
                                    start = max(0, idx - context_chars)
                                    end = min(len(page_text), idx + len(match.group()) + context_chars)
                                    snippet = page_text[start:end].strip()
                                    print(f"[PARTIAL] Found partial regex match on page {page_num}")
                                    return (snippet[:200], page_num)
                            except:
                                pass
        
        print(f"[NO MATCH] Could not find '{search_value[:50]}...' in any page")
        return None
    
    def _is_iso_date(self, value: str) -> bool:
        """Check if a value is in ISO date format (YYYY-MM-DD)."""
        import re
        return bool(re.match(r'^\d{4}-\d{2}-\d{2}$', value))
    
    def _is_number(self, value: str) -> bool:
        """Check if a value is a number (integer or decimal)."""
        value_str = str(value).strip()
        try:
            float(value_str)
            return True
        except:
            return False
    
    def _generate_number_variations(self, number: str) -> list:
        """
        Generate common number format variations.
        For example, 55000 -> ["55000", "55,000", "55 000", "55.000", etc.]
        """
        try:
            # Convert to number
            num_value = float(str(number).strip())
            
            # Generate variations
            variations = [
                str(number),  # Original
                str(int(num_value)) if num_value == int(num_value) else str(num_value),  # Integer or float
            ]
            
            # Add comma-separated formats for integers
            if num_value == int(num_value):
                num_int = int(num_value)
                # Add comma formatting (US/UK style)
                variations.append(f"{num_int:,}")  # 55,000
                # Add space formatting (EU style)
                variations.append(f"{num_int:,}".replace(',', ' '))  # 55 000
                # Add dot formatting (some EU countries)
                variations.append(f"{num_int:,}".replace(',', '.'))  # 55.000
                
                # Add variations with common prefixes
                for prefix in ['Rs.', 'Rs', 'INR', 'USD', '$']:
                    variations.append(f"{prefix} {num_int:,}")
                    variations.append(f"{prefix} {num_int}")
                    variations.append(f"{prefix}{num_int:,}")
                    variations.append(f"{prefix}{num_int}")
            
            return variations
        except:
            return [str(number)]
    
    def _generate_date_variations(self, iso_date: str) -> list:
        """
        Generate common date format variations from ISO date.
        Includes both zero-padded and non-padded day formats.
        For example, 2025-11-06 -> ["November 6, 2025", "November 06, 2025", "11/6/2025", "11/06/2025", etc.]
        """
        try:
            from datetime import datetime
            import platform
            date_obj = datetime.strptime(iso_date, '%Y-%m-%d')
            
            # Get day with and without zero-padding
            day_padded = date_obj.strftime('%d')  # "06"
            day_no_pad = str(date_obj.day)  # "6"
            month_padded = date_obj.strftime('%m')  # "11"
            month_no_pad = str(date_obj.month)  # "11"
            year = date_obj.strftime('%Y')  # "2025"
            
            variations = [
                iso_date,  # 2025-11-06
                date_obj.strftime('%d-%m-%Y'),  # 06-11-2025
                date_obj.strftime('%m-%d-%Y'),  # 11-06-2025
                date_obj.strftime('%d/%m/%Y'),  # 06/11/2025
                date_obj.strftime('%m/%d/%Y'),  # 11/06/2025
                f"{month_no_pad}/{day_no_pad}/{year}",  # 11/6/2025 (no padding)
                f"{day_no_pad}/{month_no_pad}/{year}",  # 6/11/2025 (no padding)
                date_obj.strftime('%B %d, %Y'),  # November 06, 2025 (with zero padding)
                f"{date_obj.strftime('%B')} {day_no_pad}, {year}",  # November 6, 2025 (without padding)
                date_obj.strftime('%d %B %Y'),  # 06 November 2025
                f"{day_no_pad} {date_obj.strftime('%B')} {year}",  # 6 November 2025
                date_obj.strftime('%b %d, %Y'),  # Nov 06, 2025
                f"{date_obj.strftime('%b')} {day_no_pad}, {year}",  # Nov 6, 2025
                date_obj.strftime('%d %b %Y'),  # 06 Nov 2025
                f"{day_no_pad} {date_obj.strftime('%b')} {year}",  # 6 Nov 2025
                date_obj.strftime('%Y/%m/%d'),  # 2025/11/06
                f"{year}/{month_no_pad}/{day_no_pad}",  # 2025/11/6
                date_obj.strftime('%d.%m.%Y'),  # 06.11.2025
                f"{day_no_pad}.{month_no_pad}.{year}",  # 6.11.2025
                date_obj.strftime('%Y.%m.%d'),  # 2025.11.06
                date_obj.strftime('%d-%b-%Y'),  # 06-Nov-2025
                f"{day_no_pad}-{date_obj.strftime('%b')}-{year}",  # 6-Nov-2025
                date_obj.strftime('%d-%B-%Y'),  # 06-November-2025
                f"{day_no_pad}-{date_obj.strftime('%B')}-{year}",  # 6-November-2025
                date_obj.strftime('%d %B, %Y'),  # 06 November, 2025
                f"{day_no_pad} {date_obj.strftime('%B')}, {year}",  # 6 November, 2025
                date_obj.strftime('%B %d %Y'),  # November 06 2025
                f"{date_obj.strftime('%B')} {day_no_pad} {year}",  # November 6 2025
                # Add ordinal suffixes (both padded and non-padded)
                f"{date_obj.day}{'th' if 10 <= date_obj.day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')} {date_obj.strftime('%B %Y')}",  # 6th November 2025
                f"{date_obj.day}{'th' if 10 <= date_obj.day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')} {date_obj.strftime('%b %Y')}",  # 6th Nov 2025
                f"{date_obj.day}{'th' if 10 <= date_obj.day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')} {date_obj.strftime('%B, %Y')}",  # 6th November, 2025
                f"{date_obj.day}{'th' if 10 <= date_obj.day % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(date_obj.day % 10, 'th')} of {date_obj.strftime('%B %Y')}",  # 6th of November 2025
            ]
            
            # Remove duplicates while preserving order
            seen = set()
            unique_variations = []
            for v in variations:
                if v not in seen:
                    seen.add(v)
                    unique_variations.append(v)
            
            return unique_variations
        except:
            return [iso_date]
    
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
    
    def _assign_account_type_if_missing(
        self,
        extracted_data: Dict[str, Any],
        document_type: str
    ) -> Dict[str, Any]:
        """
        Assign account type (account head) based on document type if not already present.
        
        Account head represents the account type where the Amount can be stored in accounting.
        
        Args:
            extracted_data: Extracted data dictionary
            document_type: Document type (LEASE, NDA, or CONTRACT)
            
        Returns:
            Updated extracted_data with account_type assigned if it was missing
        """
        # Check if account_type is missing or empty
        account_type = extracted_data.get("account_type")
        
        # If account_type is not present, null, or empty string, assign based on document type
        if not account_type or account_type.strip() == "" or account_type.lower() == "null":
            document_type_upper = document_type.upper()
            
            # Map document types to account head types
            account_head_mapping = {
                "LEASE": "Lease/Rental Expense",
                "NDA": "Legal/Compliance Expense",
                "CONTRACT": "Service Contract Revenue"
            }
            
            # Assign account type based on document type
            assigned_account_type = account_head_mapping.get(document_type_upper, "General Expense")
            extracted_data["account_type"] = assigned_account_type
            print(f"Assigned account type '{assigned_account_type}' based on document type '{document_type}'")
        
        return extracted_data
    
    def _extract_currency(
        self,
        extracted_data: Dict[str, Any],
        document_text: str = ""
    ) -> Dict[str, Any]:
        """
        Extract currency from amount field and document text, then add it as a separate currency field.
        Also converts amount to integer format.
        Filters out percentage-only values (e.g., "10%", "10 percent").
        
        Args:
            extracted_data: Extracted data dictionary
            document_text: Original document text to search for currency indicators
            
        Returns:
            Updated extracted_data with currency field and integer amount
        """
        import re
        
        amount_str = extracted_data.get("amount", "")
        currency = ""
        
        # Validate that amount is not a percentage only
        # Only filter if the amount string is EXACTLY a percentage (e.g., "10%", "10 percent")
        # Don't filter if it contains both percentage and actual amount/currency
        if amount_str:
            try:
                amount_lower = str(amount_str).lower().strip()
                # Check if amount string is ONLY a percentage (e.g., "10%", "10 percent", "5.5%")
                # Pattern: starts with number, followed by % or "percent", and nothing else (or just whitespace)
                is_percentage_only = bool(re.match(r'^\s*\d+\.?\d*\s*%\s*$|^\s*\d+\.?\d*\s*percent\s*$', amount_lower))
                
                # Only filter if it's EXACTLY a percentage (very strict check)
                # Don't filter if there's any currency or additional text
                if is_percentage_only:
                    # This is a percentage only, not an actual amount - clear it
                    print(f"Warning: Amount '{amount_str}' appears to be a percentage only, not an actual monetary value. Clearing amount field.")
                    extracted_data["amount"] = ""
                    extracted_data["currency"] = ""
                    return extracted_data
            except Exception as e:
                # If validation fails, don't block extraction - just log and continue
                print(f"Warning: Error in percentage validation: {e}. Continuing with extraction.")
        
        if amount_str:
            # Extract numeric value and currency
            amount_match = re.search(r'[\d,]+\.?\d*', str(amount_str).replace(',', ''))
            # Updated regex to include Rs., Rs , RS., RS (case insensitive)
            currency_match = re.search(r'[A-Z]{3}|INR|USD|EUR|GBP|JPY|CNY|Rupees|Rupee|RS\.|RS |Rs\.|Rs |₹|\$|€|£|¥', str(amount_str), re.IGNORECASE)
            
            if amount_match:
                try:
                    numeric_amount = float(amount_match.group().replace(',', ''))
                    
                    # Extract currency
                    currency = ""
                    amount_upper = str(amount_str).upper()
                    
                    # Check for Rs. or Rs patterns first (before regex match)
                    if re.search(r'Rs\.|Rs |RS\.|RS ', amount_str, re.IGNORECASE):
                        currency = "INR"
                    elif currency_match:
                        currency_code = currency_match.group().upper()
                        # Map currency symbols and names to codes
                        currency_map = {
                            "₹": "INR",
                            "$": "USD",
                            "€": "EUR",
                            "£": "GBP",
                            "¥": "JPY",
                            "RUPEES": "INR",
                            "RUPEE": "INR",
                            "RS.": "INR",
                            "RS ": "INR",
                        }
                        currency = currency_map.get(currency_code, currency_code)
                    else:
                        # Try to detect from common patterns
                        if "INR" in amount_upper or "RUPEES" in amount_upper or "RUPEE" in amount_upper or "₹" in amount_str or "RS." in amount_upper or "RS " in amount_upper:
                            currency = "INR"
                        elif "USD" in amount_upper or "$" in amount_str:
                            currency = "USD"
                        elif "EUR" in amount_upper or "€" in amount_str:
                            currency = "EUR"
                        elif "GBP" in amount_upper or "£" in amount_str:
                            currency = "GBP"
                        elif "JPY" in amount_upper or "¥" in amount_str:
                            currency = "JPY"
                        elif "CNY" in amount_upper:
                            currency = "CNY"
                        else:
                            currency = ""  # Don't default to any currency if not detected
                    
                    # Convert to integer
                    amount_int = int(round(numeric_amount))
                    
                    # Update amount field (integer only, no currency)
                    # Currency stored separately in currency field
                    if not currency:
                        # Currency not found in amount field, search document text
                        currency = self._search_currency_in_document(document_text, numeric_amount)
                    
                    # Amount is always integer only, currency stored separately
                    extracted_data["amount"] = str(amount_int)
                    extracted_data["currency"] = currency if currency else ""
                    
                except (ValueError, AttributeError):
                    # If extraction fails, try to at least detect currency
                    amount_upper = str(amount_str).upper()
                    if re.search(r'Rs\.|Rs |RS\.|RS ', amount_str, re.IGNORECASE) or "INR" in amount_upper or "RUPEES" in amount_upper or "RUPEE" in amount_upper or "₹" in amount_str:
                        currency = "INR"
                    elif "USD" in amount_upper or "$" in amount_str:
                        currency = "USD"
                    elif "EUR" in amount_upper or "€" in amount_str:
                        currency = "EUR"
                    elif "GBP" in amount_upper or "£" in amount_str:
                        currency = "GBP"
                    elif "JPY" in amount_upper or "¥" in amount_str:
                        currency = "JPY"
                    elif "CNY" in amount_upper:
                        currency = "CNY"
                    else:
                        # Search document text for currency
                        try:
                            numeric_amount = float(re.search(r'[\d,]+\.?\d*', str(amount_str).replace(',', '')).group().replace(',', ''))
                            currency = self._search_currency_in_document(document_text, numeric_amount)
                        except:
                            currency = ""
                    
                    if currency:
                        extracted_data["currency"] = currency
                        # Try to update amount if we have numeric value (integer only, no currency)
                        try:
                            amount_int = int(round(float(re.search(r'[\d,]+\.?\d*', str(amount_str).replace(',', '')).group().replace(',', ''))))
                            extracted_data["amount"] = str(amount_int)
                        except:
                            pass
                    else:
                        extracted_data["currency"] = ""
        else:
            # No amount, don't set default currency
            extracted_data["currency"] = ""
        
        return extracted_data
    
    def _search_currency_in_document(self, document_text: str, amount_value: float) -> str:
        """
        Search document text for currency indicators near the amount value.
        
        Args:
            document_text: Original document text
            amount_value: Numeric amount value to search near
            
        Returns:
            Currency code if found, empty string otherwise
        """
        import re
        
        if not document_text:
            return ""
        
        # Format amount with and without commas for searching
        amount_str = str(int(amount_value))
        amount_with_commas = f"{int(amount_value):,}"
        
        # Search for amount patterns in document
        # Look for patterns like "Rs. 55000", "55000 Rupees", "INR 55000", etc.
        patterns = [
            rf'Rs\.?\s*{re.escape(amount_str)}|Rs\.?\s*{re.escape(amount_with_commas)}',
            rf'{re.escape(amount_str)}\s*Rupees?|{re.escape(amount_with_commas)}\s*Rupees?',
            rf'INR\s*{re.escape(amount_str)}|INR\s*{re.escape(amount_with_commas)}',
            rf'₹\s*{re.escape(amount_str)}|₹\s*{re.escape(amount_with_commas)}',
        ]
        
        # Check for INR indicators near the amount
        for pattern in patterns:
            if re.search(pattern, document_text, re.IGNORECASE):
                return "INR"
        
        # Check for other currencies near the amount
        if re.search(rf'USD\s*{re.escape(amount_str)}|\$\s*{re.escape(amount_str)}', document_text, re.IGNORECASE):
            return "USD"
        if re.search(rf'EUR\s*{re.escape(amount_str)}|€\s*{re.escape(amount_str)}', document_text, re.IGNORECASE):
            return "EUR"
        if re.search(rf'GBP\s*{re.escape(amount_str)}|£\s*{re.escape(amount_str)}', document_text, re.IGNORECASE):
            return "GBP"
        if re.search(rf'JPY\s*{re.escape(amount_str)}|¥\s*{re.escape(amount_str)}', document_text, re.IGNORECASE):
            return "JPY"
        if re.search(rf'CNY\s*{re.escape(amount_str)}', document_text, re.IGNORECASE):
            return "CNY"
        
        # General search for currency indicators in the document (if amount-specific search failed)
        if re.search(r'Rs\.|Rs |RS\.|RS |RUPEES|RUPEE|₹', document_text, re.IGNORECASE):
            return "INR"
        if re.search(r'USD|\$', document_text, re.IGNORECASE):
            return "USD"
        if re.search(r'EUR|€', document_text, re.IGNORECASE):
            return "EUR"
        if re.search(r'GBP|£', document_text, re.IGNORECASE):
            return "GBP"
        if re.search(r'JPY|¥', document_text, re.IGNORECASE):
            return "JPY"
        if re.search(r'CNY', document_text, re.IGNORECASE):
            return "CNY"
        
        return ""
    
    def _calculate_period_amount(
        self,
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate per-period amount based on total payment and frequency.
        
        For example:
        - Total: 12000 INR, Frequency: Monthly → Per Month: 12000 INR
        - Total: 12000 INR, Frequency: Quarterly → Per Month: 4000 INR (12000/3)
        - Total: 12000 INR, Frequency: Annual → Per Month: 1000 INR (12000/12)
        
        Args:
            extracted_data: Extracted data dictionary
            
        Returns:
            Updated extracted_data with per_period_amount and per_month_amount if calculable
        """
        amount_str = extracted_data.get("amount", "")
        frequency = extracted_data.get("frequency", "")
        
        if not amount_str or not frequency:
            return extracted_data
        
        # Extract numeric value from amount string
        import re
        # Try to extract number from amount string (handles "12000 INR", "INR 12000", "$5000", etc.)
        amount_match = re.search(r'[\d,]+\.?\d*', str(amount_str).replace(',', ''))
        if not amount_match:
            return extracted_data
        
        try:
            total_amount = float(amount_match.group().replace(',', ''))
        except (ValueError, AttributeError):
            return extracted_data
        
        # Extract currency if present
        currency_match = re.search(r'[A-Z]{3}|INR|USD|EUR|GBP|JPY|CNY', str(amount_str).upper())
        currency = currency_match.group() if currency_match else ""
        
        # Normalize frequency to lowercase for matching
        frequency_lower = str(frequency).lower().strip()
        
        # Calculate periods per year based on frequency
        periods_per_year = None
        
        if any(term in frequency_lower for term in ['monthly', 'month', 'per month', 'each month']):
            periods_per_year = 12
            period_name = "month"
        elif any(term in frequency_lower for term in ['quarterly', 'quarter', 'per quarter', 'each quarter', 'qtr']):
            periods_per_year = 4
            period_name = "quarter"
        elif any(term in frequency_lower for term in ['annual', 'annually', 'yearly', 'year', 'per year', 'each year']):
            periods_per_year = 1
            period_name = "year"
        elif any(term in frequency_lower for term in ['semi-annual', 'semi annual', 'half-yearly', 'half yearly', 'biannual']):
            periods_per_year = 2
            period_name = "half-year"
        elif any(term in frequency_lower for term in ['weekly', 'week', 'per week', 'each week']):
            periods_per_year = 52
            period_name = "week"
        elif any(term in frequency_lower for term in ['daily', 'day', 'per day', 'each day']):
            periods_per_year = 365
            period_name = "day"
        elif any(term in frequency_lower for term in ['one-time', 'one time', 'single', 'lump sum', 'once']):
            periods_per_year = 1
            period_name = "one-time"
        else:
            # Unknown frequency, cannot calculate
            return extracted_data
        
        # Calculate per-period amount
        per_period_amount = total_amount / periods_per_year
        
        # Calculate per-month amount (for comparison)
        if periods_per_year == 12:
            per_month_amount = per_period_amount
        elif periods_per_year == 4:  # Quarterly
            per_month_amount = total_amount / 12
        elif periods_per_year == 1:  # Annual
            per_month_amount = total_amount / 12
        elif periods_per_year == 2:  # Semi-annual
            per_month_amount = total_amount / 12
        elif periods_per_year == 52:  # Weekly
            per_month_amount = total_amount / 12
        elif periods_per_year == 365:  # Daily
            per_month_amount = total_amount / 12
        else:
            per_month_amount = total_amount / 12  # Default to monthly equivalent
        
        # Format amounts as integers only (no currency, currency stored separately)
        # Add calculated fields to extracted data
        extracted_data["per_period_amount"] = str(int(round(per_period_amount)))
        extracted_data["per_month_amount"] = str(int(round(per_month_amount)))
        extracted_data["period_name"] = period_name
        extracted_data["total_amount_numeric"] = total_amount
        
        # Get currency from extracted_data if available
        currency_display = extracted_data.get("currency", currency if currency else "")
        currency_str = f" {currency_display}" if currency_display else ""
        print(f"Calculated payment: {int(round(per_period_amount))}{currency_str} per {period_name} (equivalent to {int(round(per_month_amount))}{currency_str} per month)")
        
        return extracted_data
    
    def _calculate_risk_score(
        self,
        extracted_data: Dict[str, Any],
        document_text: str
    ) -> Dict[str, Any]:
        """
        Calculate risk score based on extracted contract data.
        
        Risk factors considered:
        - Missing critical clauses
        - Missing important information
        - Unfavorable terms
        - Date-related risks
        - Payment risks
        - Legal risks
        """
        risk_factors = []
        risk_score = 0  # Start with 0 (low risk), increase for each risk factor
        max_risk = 100
        
        # 1. Missing Document Type (Low Risk: +5)
        if not extracted_data.get("document_type"):
            risk_score += 5
            risk_factors.append({
                "factor": "Missing document type",
                "severity": "Low",
                "impact": 5
            })
        
        # 2. Missing Party Information (High Risk: +15)
        parties_missing = False
        if "party_names" in extracted_data:
            parties = extracted_data.get("party_names", {})
            if not parties.get("party_1") and not parties.get("party_2"):
                parties_missing = True
        else:
            parties_missing = True
        
        if parties_missing:
            risk_score += 15
            risk_factors.append({
                "factor": "Missing party information",
                "severity": "High",
                "impact": 15
            })
        
        # 3. Missing Dates (Medium to High Risk)
        if not extracted_data.get("start_date"):
            risk_score += 10
            risk_factors.append({
                "factor": "Missing start date",
                "severity": "High",
                "impact": 10
            })
        
        due_date_missing = not extracted_data.get("due_date")
        if due_date_missing:
            risk_score += 20
            risk_factors.append({
                "factor": "Missing due date",
                "severity": "High",
                "impact": 20
            })
        
        # 4. Missing Payment Information (High Risk: +20)
        amount_missing = not extracted_data.get("amount")
        if amount_missing:
            risk_score += 20
            risk_factors.append({
                "factor": "Missing payment amount",
                "severity": "High",
                "impact": 20
            })
        
        # 5. Combined High Risk: If both amount AND due date are missing, add additional high risk
        if amount_missing and due_date_missing:
            risk_score += 15
            risk_factors.append({
                "factor": "Missing both payment amount and due date (Critical)",
                "severity": "High",
                "impact": 15
            })
        
        if not extracted_data.get("frequency"):
            risk_score += 5
            risk_factors.append({
                "factor": "Missing payment frequency",
                "severity": "Low",
                "impact": 5
            })
        
        # 5. Missing Account Type (Low Risk: +5)
        if not extracted_data.get("account_type"):
            risk_score += 5
            risk_factors.append({
                "factor": "Missing account type",
                "severity": "Low",
                "impact": 5
            })
        
        # 6. Compliance Violations (High Risk: +20 if violations exist)
        compliance_violation = extracted_data.get("rules_and_compliance_violation", "")
        # Only add risk if there are actual violations (not the "No violation" message)
        if compliance_violation and compliance_violation.strip().lower() != "no violation of rules and compliance":
            risk_score += 20
            risk_factors.append({
                "factor": "Compliance violations detected",
                "severity": "High",
                "impact": 20
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
        extracted_data["risk_score"] = {
            "score": risk_score,
            "level": risk_level,
            "category": risk_category,
            "risk_factors": risk_factors
        }
        
        return extracted_data


# Singleton instance for the application
_orchestrator_instance: Optional[ExtractionOrchestrator] = None


def get_orchestrator(
    api_key: Optional[str] = None,
    use_gcs_vision: bool = True,
    service_account_file: Optional[str] = None,
    use_semantic_search: bool = True
) -> ExtractionOrchestrator:
    """
    Get or create the ExtractionOrchestrator singleton instance.
    This reuses the same instance to avoid creating multiple OpenAI clients.
    
    Args:
        api_key: OpenAI API key (optional, will use env var if not provided)
        use_gcs_vision: Enable Google Cloud Vision API for scanned PDFs
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        use_semantic_search: Whether to use semantic search for missing fields
        
    Returns:
        ExtractionOrchestrator instance
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = ExtractionOrchestrator(
            api_key=api_key,
            use_gcs_vision=use_gcs_vision,
            service_account_file=service_account_file,
            use_semantic_search=use_semantic_search
        )
    return _orchestrator_instance
