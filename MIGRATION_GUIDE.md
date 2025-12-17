# Migration Guide: From General Extraction to Type-Specific Extraction

## Overview

The system has been migrated from a **general extraction approach** to a **type-specific extraction approach** using an orchestrator pattern.

## What Changed

### Old System (Deprecated)
- **Single File**: `contract_extractor.py` with generic extraction logic
- **Generic Prompts**: One prompt tried to extract all fields for all document types
- **Manual Flow**: Separate steps for parsing and extraction
- **Less Accurate**: Extracted irrelevant fields for each document type

### New System (Current)
- **Orchestrator**: `extraction_orchestrator.py` coordinates the entire process
- **Type-Specific Extractors**: 
  - `lease_extractor.py` - For lease documents
  - `nda_extractor.py` - For NDA documents
  - `contract_extractor_specific.py` - For service contracts
- **Automatic Routing**: Detects document type and routes to appropriate extractor
- **Better Accuracy**: Extracts only relevant fields for each document type

## Migration Steps

### 1. Update Imports

**Old:**
```python
from contract_extractor import ContractExtractor
from document_parser import DocumentParser
```

**New:**
```python
from extraction_orchestrator import ExtractionOrchestrator
```

### 2. Update Initialization

**Old:**
```python
parser = DocumentParser(use_gcs_vision=True, service_account_file="...")
extractor = ContractExtractor(api_key=api_key)
```

**New:**
```python
orchestrator = ExtractionOrchestrator(
    api_key=api_key,
    use_gcs_vision=True,  # Automatically integrates with vision_gcp.py
    service_account_file="gcp-creds.json",
    use_semantic_search=True
)
```

### 3. Update Extraction Calls

**Old:**
```python
# Step 1: Parse document
document_text, page_map = parser.parse_with_pages(file_path, use_ocr=use_ocr)

# Step 2: Extract data
extracted_data = extractor.extract(document_text, page_map=page_map)
```

**New:**
```python
# Single step: Orchestrator handles everything
extracted_data, metadata = orchestrator.extract_from_file(file_path, use_ocr=use_ocr)

# Metadata contains:
# - document_type: "LEASE", "NDA", or "CONTRACT"
# - classification_confidence: "HIGH", "MEDIUM", or "LOW"
# - classification_reasoning: Explanation of classification
# - page_map: Page mapping (also in extracted_data)
```

### 4. Update Text Extraction

**Old:**
```python
extracted_data = extractor.extract(document_text, page_map=page_map)
```

**New:**
```python
extracted_data, metadata = orchestrator.extract_from_text(document_text, page_map=page_map)
```

## Key Differences

### Return Values

**Old:**
- Returns: `Dict[str, Any]` (extracted data only)

**New:**
- Returns: `Tuple[Dict[str, Any], Dict[str, Any]]` (extracted data + metadata)

### Document Type Detection

**Old:**
- Classification happened but wasn't used for routing
- Generic extraction for all types

**New:**
- Classification determines which extractor to use
- Type-specific extraction with relevant fields only

### Integration with vision_gcp.py

**Old:**
- Manual integration required
- User had to handle DocumentParser separately

**New:**
- Automatic integration
- Orchestrator handles DocumentParser internally
- Seamlessly uses vision_gcp.py for scanned PDFs

## Files Updated

1. ✅ **app.py** - Updated to use ExtractionOrchestrator
2. ✅ **main.py** - Updated to use ExtractionOrchestrator
3. ✅ **example_usage.py** - Updated to use ExtractionOrchestrator
4. ⚠️ **contract_extractor.py** - Marked as deprecated (kept for backward compatibility)

## New Files Created

1. ✅ **extraction_orchestrator.py** - Main orchestrator
2. ✅ **lease_extractor.py** - Lease-specific extractor
3. ✅ **nda_extractor.py** - NDA-specific extractor
4. ✅ **contract_extractor_specific.py** - Contract-specific extractor
5. ✅ **document_type_classifier.py** - Document type detection
6. ✅ **EXTRACTION_ARCHITECTURE.md** - Architecture documentation

## Benefits

1. **Better Accuracy**: Type-specific extraction means only relevant fields are extracted
2. **Easier Debugging**: Issues can be isolated to specific extractor files
3. **Better Maintainability**: Each extractor is separate and focused
4. **Automatic Integration**: Works seamlessly with vision_gcp.py
5. **Scalability**: Easy to add new document types

## Backward Compatibility

The old `ContractExtractor` class is still available but marked as deprecated. Existing code will continue to work, but new code should use `ExtractionOrchestrator`.

## Testing

After migration, test with:
- Lease documents → Should extract lease-specific fields
- NDA documents → Should extract NDA-specific fields
- Contract documents → Should extract contract-specific fields
- Scanned PDFs → Should automatically use vision_gcp.py

## Support

If you encounter issues:
1. Check that all new extractor files are present
2. Verify document type classification is working
3. Ensure vision_gcp.py integration is enabled
4. Check that OpenAI API key is configured

