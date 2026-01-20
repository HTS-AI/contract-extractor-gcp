# Invoice to Account Payable Application - API Documentation

## Overview

This document provides a comprehensive list of all APIs available in the Invoice to Account Payable Application along with testing examples.

**Base URL:** `http://localhost:8000`

---

## Table of Contents

1. [Health & Status](#health--status)
2. [Document Upload & Extraction](#document-upload--extraction)
3. [Dashboard & Data](#dashboard--data)
4. [Excel Data](#excel-data)
5. [Chatbot APIs](#chatbot-apis)
6. [File Management](#file-management)
7. [Direct Extraction APIs](#direct-extraction-apis)
8. [HTML Pages](#html-pages)

---

## Health & Status

### GET /health
Health check endpoint to verify server status.

**Response:**
```json
{
    "status": "healthy",
    "api_key_configured": true
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/health
```

---

## Document Upload & Extraction

### POST /api/upload
Upload a document file for extraction.

**Request:**
- Content-Type: `multipart/form-data`
- File types supported: `.pdf`, `.docx`, `.doc`, `.txt`

**Response:**
```json
{
    "extraction_id": "uuid-string",
    "file_name": "invoice.pdf",
    "status": "uploaded",
    "vector_store": {"created": false}
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@/path/to/invoice.pdf"
```

---

### POST /api/extract/{extraction_id}
Extract information from an uploaded document.

**Path Parameters:**
- `extraction_id`: UUID from the upload response

**Response:**
```json
{
    "success": true,
    "extraction_id": "uuid-string",
    "file_name": "invoice.pdf",
    "results": {
        "contract_type": "INVOICE",
        "invoice_id": "INV-001",
        "vendor": {...},
        "customer": {...},
        "line_items": [...],
        "totals": {...}
    },
    "from_cache": false
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/api/extract/{extraction_id}
```

---

### GET /api/extraction-status/{extraction_id}
Get current processing status for an extraction (for progress bar).

**Path Parameters:**
- `extraction_id`: UUID of the extraction

**Response:**
```json
{
    "extraction_id": "uuid-string",
    "status": "processing",
    "current_step": "extract_data",
    "step_description": "Extracting data using document extractor",
    "progress_percent": 55,
    "is_complete": false
}
```

**Progress Steps:**
| Step | Description | Progress |
|------|-------------|----------|
| `uploaded` | File uploaded | 0% |
| `extraction_started` | Extraction process started | 15% |
| `parse_document` | Parsing document text | 25% |
| `classify_document` | Classifying document type | 40% |
| `extract_data` | Extracting data | 55% |
| `enhance_data` | Enhancing extracted data | 70% |
| `calculate_risk` | Calculating risk score | 85% |
| `finalize` | Finalizing extraction | 95% |
| `completed` | Extraction complete | 100% |

**Test with cURL:**
```bash
curl http://localhost:8000/api/extraction-status/{extraction_id}
```

---

### GET /api/extraction/{extraction_id}
Get extraction data by extraction ID.

**Path Parameters:**
- `extraction_id`: UUID of the extraction

**Response:**
```json
{
    "success": true,
    "extraction_id": "uuid-string",
    "file_name": "invoice.pdf",
    "extracted_at": "2026-01-16T10:30:00",
    "results": {...}
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/extraction/{extraction_id}
```

---

### GET /api/extractions-list
Get list of all extracted documents.

**Response:**
```json
{
    "success": true,
    "extractions": [
        {
            "extraction_id": "uuid-1",
            "file_name": "invoice1.pdf",
            "extracted_at": "2026-01-16T10:30:00",
            "document_type": "INVOICE"
        },
        {
            "extraction_id": "uuid-2",
            "file_name": "invoice2.pdf",
            "extracted_at": "2026-01-15T09:00:00",
            "document_type": "INVOICE"
        }
    ]
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/extractions-list
```

---

## Dashboard & Data

### GET /api/dashboard
Get dashboard statistics.

**Response:**
```json
{
    "total_documents": 5,
    "average_risk_score": 42,
    "total_missing_clauses": 3,
    "contract_types": {
        "INVOICE": 3,
        "NDA": 2
    }
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/dashboard
```

---

### GET /api/json-data
Get all extracted JSON data for dashboard.

**Response:**
```json
{
    "extractions": [
        {
            "extraction_id": "uuid-string",
            "file_name": "invoice.pdf",
            "uploaded_at": "2026-01-16T10:00:00",
            "extracted_at": "2026-01-16T10:05:00",
            "data": {...}
        }
    ]
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/json-data
```

---

## Excel Data

### GET /api/excel-data
Get data from Excel file if it exists.

**Response:**
```json
{
    "success": true,
    "data": [
        {
            "Invoice ID": "INV-001",
            "Vendor Name": "ABC Corp",
            "Total Amount": 1500.00,
            ...
        }
    ]
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/excel-data
```

---

### GET /api/download-excel
Download the Excel file.

**Response:**
- Content-Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- File: `contract_extractions.xlsx`

**Test with cURL:**
```bash
curl -o contract_extractions.xlsx http://localhost:8000/api/download-excel
```

---

## Chatbot APIs

### POST /api/chat/upload
Upload a document for chatbot Q&A.

**Request:**
- Content-Type: `multipart/form-data`
- File types: `.pdf`, `.docx`, `.txt`

**Response:**
```json
{
    "success": true,
    "session_id": "uuid-string",
    "filename": "document.pdf",
    "document_length": 15000,
    "chunks_created": 25,
    "is_scanned": false,
    "used_ocr": false,
    "from_cache": "none",
    "cache_message": "New file processed"
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/api/chat/upload \
  -F "file=@/path/to/document.pdf"
```

---

### POST /api/chat/load-from-extraction/{extraction_id}
Create a chat session from an existing extraction (reuses parsed data).

**Path Parameters:**
- `extraction_id`: UUID of the extraction

**Response:**
```json
{
    "success": true,
    "session_id": "uuid-string",
    "filename": "invoice.pdf",
    "document_length": 12000,
    "chunks_created": 20,
    "message": "Session created from extraction data"
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/api/chat/load-from-extraction/{extraction_id}
```

---

### POST /api/chat/ask
Ask a question about the uploaded document.

**Request Body:**
```json
{
    "session_id": "uuid-string",
    "question": "What is the total amount on this invoice?"
}
```

**Response:**
```json
{
    "success": true,
    "answer": "The total amount on this invoice is $1,500.00",
    "sources": [
        {
            "page": 1,
            "text": "Total: $1,500.00",
            "relevance": 0.95
        }
    ]
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "uuid-string", "question": "What is the invoice total?"}'
```

---

### GET /api/chat/session/{session_id}
Get information about a chat session.

**Path Parameters:**
- `session_id`: UUID of the chat session

**Response:**
```json
{
    "success": true,
    "session": {
        "session_id": "uuid-string",
        "filename": "document.pdf",
        "created_at": "2026-01-16T10:30:00",
        "document_length": 15000
    }
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/chat/session/{session_id}
```

---

### DELETE /api/chat/session/{session_id}
Delete a chat session.

**Path Parameters:**
- `session_id`: UUID of the chat session

**Response:**
```json
{
    "success": true,
    "message": "Session deleted"
}
```

**Test with cURL:**
```bash
curl -X DELETE http://localhost:8000/api/chat/session/{session_id}
```

---

## File Management

> **Recommended:** Use `DELETE /api/files/extraction/{id}` for deleting extractions. It's simpler and more reliable.

### Quick Reference

| Use Case | Recommended API | Method |
|----------|----------------|--------|
| Delete single extraction | `/api/files/extraction/{id}` | DELETE ✅ |
| Delete cache files | `/api/files/delete` | POST |
| Clear all cache | `/api/files/clear-all` | POST |
| List all files | `/api/files/list` | GET |

---

### GET /api/files/list
List all cached files from local storage and GCS.

**Response:**
```json
{
    "success": true,
    "data": {
        "extraction_cache": [...],
        "chatbot_cache": [...],
        "extractions_data": [...],
        "exports": [...],
        "extraction_records": [...],
        "gcs_enabled": true,
        "gcs_bucket": "gs://bucket-name/cache/",
        "summary": {
            "total_extraction_cache": 5,
            "total_chatbot_cache": 3,
            "total_extractions_data": 1,
            "total_exports": 1
        }
    }
}
```

**Test with cURL:**
```bash
curl http://localhost:8000/api/files/list
```

---

### DELETE /api/files/extraction/{extraction_id} ⭐ Recommended
Delete an extraction completely (from memory, local, and GCS).

**This is the preferred method for deleting extractions** - simple URL path, no request body needed.

**Path Parameters:**
- `extraction_id`: UUID of the extraction

**Response:**
```json
{
    "success": true,
    "results": {
        "extraction_id": "uuid-string",
        "deleted": [
            "Removed from in-memory store",
            "Deleted extraction record: uuid-string"
        ],
        "failed": []
    }
}
```

**Test with cURL:**
```bash
curl -X DELETE http://localhost:8000/api/files/extraction/{extraction_id}
```

**Test with Python:**
```python
import requests
extraction_id = "your-extraction-id"
response = requests.delete(f"http://localhost:8000/api/files/extraction/{extraction_id}")
print(response.json())
```

---

### POST /api/files/delete
Delete specific files from local and/or GCS storage.

> **Note:** For deleting extractions, prefer using `DELETE /api/files/extraction/{id}` instead.

**Request Body (required):**
```json
{
    "files": [
        {"path": "path/to/file", "location": "local|gcs"}
    ],
    "file_hashes": ["hash1", "hash2"],
    "extraction_ids": ["id1", "id2"]
}
```

**Error Response (if body is empty):**
```json
{
    "success": false,
    "error": "Invalid or empty request body. Expected JSON with 'files', 'file_hashes', or 'extraction_ids' array."
}
```

**Success Response:**
```json
{
    "success": true,
    "results": {
        "deleted": ["Deleted: file1.json", "Deleted: file2.json"],
        "failed": [],
        "total_deleted": 2
    }
}
```

**Test with cURL:**
```bash
# Delete by file hashes (cache files)
curl -X POST http://localhost:8000/api/files/delete \
  -H "Content-Type: application/json" \
  -d '{"file_hashes": ["abc123def456"]}'

# Delete specific file paths
curl -X POST http://localhost:8000/api/files/delete \
  -H "Content-Type: application/json" \
  -d '{"files": [{"path": "gs://bucket/file.json", "location": "gcs"}]}'
```

---

### POST /api/files/clear-all
Clear all cache files from local and/or GCS storage.

**Request Body (optional - defaults shown):**
```json
{
    "clear_local": true,
    "clear_gcs": true,
    "clear_extractions_data": false,
    "clear_in_memory": true
}
```

**Response:**
```json
{
    "success": true,
    "results": {
        "local_extraction_deleted": 5,
        "local_chatbot_deleted": 3,
        "gcs_extraction_deleted": 5,
        "gcs_chatbot_deleted": 3,
        "extractions_data_cleared": false,
        "in_memory_cleared": false,
        "errors": []
    }
}
```

**Test with cURL:**
```bash
# Clear all cache (uses defaults)
curl -X POST http://localhost:8000/api/files/clear-all \
  -H "Content-Type: application/json" \
  -d '{}'

# Clear everything including extractions data
curl -X POST http://localhost:8000/api/files/clear-all \
  -H "Content-Type: application/json" \
  -d '{"clear_local": true, "clear_gcs": true, "clear_extractions_data": true, "clear_in_memory": true}'
```

---

## Direct Extraction APIs

### POST /extract/file
Direct file extraction API (without upload step).

**Request:**
- Content-Type: `multipart/form-data`
- `file`: Document file (required)
- `use_ocr`: Boolean (optional, default: false)
- `use_semantic_search`: Boolean (optional, default: true)

**Response:**
```json
{
    "success": true,
    "extracted_data": {...},
    "metadata": {
        "file_name": "invoice.pdf",
        "document_type": "INVOICE",
        "extraction_method": "langgraph_agent"
    },
    "message": "Successfully extracted data from invoice.pdf"
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/extract/file \
  -F "file=@/path/to/invoice.pdf" \
  -F "use_ocr=false" \
  -F "use_semantic_search=true"
```

---

### POST /extract/text
Extract data from raw text directly.

**Request Body:**
```json
{
    "text": "Invoice #12345\nDate: 2026-01-16\nTotal: $1,500.00\n...",
    "use_semantic_search": true
}
```

**Response:**
```json
{
    "success": true,
    "extracted_data": {...},
    "metadata": {...},
    "message": "Successfully extracted data from text"
}
```

**Test with cURL:**
```bash
curl -X POST http://localhost:8000/extract/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Invoice content here...", "use_semantic_search": true}'
```

---

## HTML Pages

### GET /
Main application page (requires login).

### GET /dashboard
JSON Dashboard page.

### GET /selected-factors
Selected factors page.

### GET /excel-table
Data Table page with Excel export.

---

## Testing with Python

```python
import requests

BASE_URL = "http://localhost:8000"

# 1. Health Check
response = requests.get(f"{BASE_URL}/health")
print(response.json())

# 2. Upload a file
with open("invoice.pdf", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/api/upload",
        files={"file": ("invoice.pdf", f, "application/pdf")}
    )
extraction_id = response.json()["extraction_id"]

# 3. Extract the document
response = requests.post(f"{BASE_URL}/api/extract/{extraction_id}")
print(response.json())

# 4. Get dashboard
response = requests.get(f"{BASE_URL}/api/dashboard")
print(response.json())

# 5. List files
response = requests.get(f"{BASE_URL}/api/files/list")
print(response.json())

# 6. Chat with document
response = requests.post(
    f"{BASE_URL}/api/chat/load-from-extraction/{extraction_id}"
)
session_id = response.json()["session_id"]

response = requests.post(
    f"{BASE_URL}/api/chat/ask",
    json={"session_id": session_id, "question": "What is the invoice total?"}
)
print(response.json()["answer"])
```

---

## Error Responses

All APIs return consistent error responses:

```json
{
    "success": false,
    "error": "Error message description"
}
```

**HTTP Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Success |
| 400 | Bad Request (invalid input) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for extraction | Yes |
| `GCP_CREDENTIALS_JSON` | GCP service account credentials (JSON) | For GCS |
| `GCS_CACHE_BUCKET` | GCS bucket for cache storage | For GCS |

---

## Running the Server

```bash
# Start the server
python app.py

# Server runs on http://localhost:8000
```

---

## Changelog

### January 16, 2026
- **File Management APIs Updated:**
  - Recommended `DELETE /api/files/extraction/{id}` as the preferred method for deleting extractions
  - Added error handling for empty request body in `POST /api/files/delete`
  - `POST /api/files/clear-all` now accepts empty body (uses defaults)
  - Added Quick Reference table for file management APIs
  - Added Python code examples

---

*Last Updated: January 16, 2026*
