# Extraction Architecture Documentation

## Overview

This system provides **type-specific extraction** for three document types:
- **Lease Documents** - Lease agreements for property, equipment, or assets
- **NDA Documents** - Non-Disclosure Agreements
- **Contract Documents** - Service/telecom contracts

The system automatically detects the document type and routes to the appropriate extractor.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Extraction Orchestrator                    │
│  (extraction_orchestrator.py)                               │
│  - Coordinates entire process                               │
│  - Routes to appropriate extractor                          │
└─────────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Document   │  │   Document   │  │   Document   │
│   Parser     │  │   Type       │  │   Type       │
│              │  │   Classifier │  │   Classifier │
│ (works with  │  │              │  │              │
│ vision_gcp)  │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   Lease      │  │   NDA        │  │   Contract   │
│   Extractor  │  │   Extractor  │  │   Extractor  │
│              │  │              │  │              │
│ lease_       │  │ nda_         │  │ contract_    │
│ extractor.py │  │ extractor.py │  │ extractor_   │
│              │  │              │  │ specific.py  │
└──────────────┘  └──────────────┘  └──────────────┘
```

## File Structure

### 1. **extraction_orchestrator.py** (Main Orchestrator)
   - **Purpose**: Coordinates the entire extraction process
   - **Responsibilities**:
     - Parses documents (integrates with `vision_gcp.py` for scanned PDFs)
     - Classifies document type (Lease, NDA, or Contract)
     - Routes to appropriate extractor
     - Returns unified results
   - **Key Methods**:
     - `extract_from_file()` - Extract from file path
     - `extract_from_text()` - Extract from raw text
     - `_route_to_extractor()` - Routes to correct extractor

### 2. **lease_extractor.py** (Lease-Specific Extractor)
   - **Purpose**: Extracts lease-specific fields
   - **Extracts**:
     - Site Location Details
     - Lessor & Lessee Information
     - Lease Term & Renewal Options
     - Rent Amount & Payment Schedule
     - Rent Escalation Clause
     - Permitted Use of Premises
     - Right of Access
     - Utility & Power Provisions
     - Termination Conditions
     - Maintenance & Responsibility Clauses
     - Compliance & Risk factors

### 3. **nda_extractor.py** (NDA-Specific Extractor)
   - **Purpose**: Extracts NDA-specific fields
   - **Extracts**:
     - Parties to the Agreement
     - Definition of Confidential Information
     - Purpose of Disclosure
     - Confidentiality Obligations
     - Exclusions from Confidentiality
     - Term & Duration of Confidentiality
     - Permitted Use & Restrictions
     - Return or Destruction of Information
     - Remedies & Liability for Breach
     - Governing Law & Jurisdiction
     - Compliance & Risk factors

### 4. **contract_extractor_specific.py** (Contract-Specific Extractor)
   - **Purpose**: Extracts contract-specific fields
   - **Extracts**:
     - Parties Involved
     - Contract Term & Validity
     - Scope of Services
     - SLA Parameters
     - Pricing & Commercials
     - Payment Terms
     - Penalties & Remedies
     - Termination Clause
     - Liability & Indemnification
     - Confidentiality & Data Protection
     - Compliance & Risk factors

## Integration with vision_gcp.py

The orchestrator seamlessly integrates with `vision_gcp.py`:

1. **Document Parser** (`document_parser.py`) is initialized with `use_gcs_vision=True`
2. When a **scanned PDF** is detected:
   - `document_parser.py` automatically calls `vision_gcp.py`
   - `vision_gcp.py` processes the PDF using Google Cloud Vision API
   - OCR text is returned to the parser
   - Parser returns text to orchestrator
3. The orchestrator then:
   - Classifies the document type
   - Routes to appropriate extractor
   - Returns extracted data

## Usage Example

```python
from extraction_orchestrator import ExtractionOrchestrator

# Initialize orchestrator
orchestrator = ExtractionOrchestrator(
    api_key="your-api-key",
    use_gcs_vision=True,  # Enables vision_gcp.py integration
    service_account_file="path/to/service-account.json"
)

# Extract from file (automatically uses vision_gcp.py if scanned PDF)
extracted_data, metadata = orchestrator.extract_from_file(
    "path/to/document.pdf",
    use_ocr=False  # Auto-detect or set True to force OCR
)

# Check document type
print(f"Document Type: {metadata['document_type']}")
print(f"Confidence: {metadata['classification_confidence']}")
```

## Workflow

1. **Document Upload** → File path or text provided
2. **Document Parsing** → `document_parser.py` parses (uses `vision_gcp.py` if scanned PDF)
3. **Type Classification** → `document_type_classifier.py` determines type
4. **Routing** → Orchestrator routes to appropriate extractor:
   - Lease → `lease_extractor.py`
   - NDA → `nda_extractor.py`
   - Contract → `contract_extractor_specific.py`
5. **Extraction** → Type-specific extractor extracts relevant fields
6. **Enhancement** → Semantic search and risk scoring (optional)
7. **Return** → Unified extraction results with metadata

## Troubleshooting

### Issue: Vision API not working
- **Check**: `use_gcs_vision=True` in orchestrator initialization
- **Check**: Service account file path is correct
- **Check**: `vision_gcp.py` is in the same directory
- **Check**: Google Cloud Vision API is enabled

### Issue: Wrong document type detected
- **Check**: Document text is clear and readable
- **Check**: Document contains type-specific keywords
- **Check**: Classification confidence level
- **Solution**: Can manually override by specifying extractor

### Issue: Extractor not found
- **Check**: All extractor files are in the same directory:
  - `lease_extractor.py`
  - `nda_extractor.py`
  - `contract_extractor_specific.py`
- **Check**: Import statements in `extraction_orchestrator.py`

### Issue: Missing fields in extraction
- **Check**: Document contains the information
- **Check**: Using correct extractor for document type
- **Check**: OpenAI API key is valid
- **Solution**: Enable semantic search for better field filling

## Benefits of This Architecture

1. **Modularity**: Each extractor is separate, easy to maintain
2. **Type-Specific**: Extracts only relevant fields for each document type
3. **Scalability**: Easy to add new document types
4. **Debugging**: Issues can be isolated to specific extractors
5. **Integration**: Works seamlessly with existing `vision_gcp.py` system

