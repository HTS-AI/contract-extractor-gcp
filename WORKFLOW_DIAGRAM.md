# Invoice to Account Payable Application - Workflow Diagram

## Complete System Workflow

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              INVOICE TO ACCOUNT PAYABLE SYSTEM                          │
│                                  (with PO Matching)                                     │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────────────────┐
                    │              USER INTERFACE                  │
                    │         (Web Browser / Frontend)             │
                    │                                             │
                    │  ┌───────────────────────────────────────┐  │
                    │  │  📋 PURCHASE ORDER UPLOAD (TOP)       │  │
                    │  │  - Upload PO first for matching       │  │
                    │  │  - View list of uploaded POs          │  │
                    │  │  - Auto-extract & cache PO data       │  │
                    │  └───────────────────────────────────────┘  │
                    │                                             │
                    │  ┌───────────────────────────────────────┐  │
                    │  │  📤 INVOICE UPLOAD (BELOW PO)         │  │
                    │  │  - Upload invoice for extraction      │  │
                    │  │  - Auto-match with cached POs         │  │
                    │  │  - Warning if no PO match found       │  │
                    │  └───────────────────────────────────────┘  │
                    └───────────────────┬─────────────────────────┘
                                        │
                    ┌───────────────────┴───────────────────┐
                    │                                       │
                    ▼                                       ▼
    ┌───────────────────────────┐           ┌───────────────────────────┐
    │   PURCHASE ORDER UPLOAD   │           │      INVOICE UPLOAD       │
    │    POST /api/upload-po    │           │     POST /api/upload      │
    └───────────────┬───────────┘           └───────────────┬───────────┘
                    │                                       │
                    ▼                                       ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │                         STEP 1: FILE UPLOAD                        │
    │  ┌─────────────────────────────────────────────────────────────┐  │
    │  │  • Validate file type (PDF, DOCX, TXT)                      │  │
    │  │  • Compute SHA256 file hash                                 │  │
    │  │  • Generate unique extraction ID                            │  │
    │  │  • Save to temporary storage                                │  │
    │  └─────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────┬───────────────────────────────────┘
                                    │
                                    ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │                       STEP 2: CACHE CHECK                          │
    │  ┌─────────────────────────────────────────────────────────────┐  │
    │  │  Check cache using file hash:                               │  │
    │  │  • For PO: Check po_cache/                                  │  │
    │  │  • For Invoice: Check extraction_cache/                     │  │
    │  └─────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────┬───────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            ┌───────▼───────┐               ┌───────▼───────┐
            │  CACHE HIT    │               │  CACHE MISS   │
            │ (Use cached   │               │ (Process new) │
            │   results)    │               │               │
            └───────┬───────┘               └───────┬───────┘
                    │                               │
                    │                               ▼
                    │       ┌───────────────────────────────────────────┐
                    │       │          STEP 3: DOCUMENT PARSING          │
                    │       │  ┌─────────────────────────────────────┐  │
                    │       │  │  DocumentParser determines method:  │  │
                    │       │  │  • Complete Text (native PDF)       │  │
                    │       │  │  • Semi OCR (hybrid PDF)            │  │
                    │       │  │  • Complete OCR (scanned PDF)       │  │
                    │       │  └─────────────────────────────────────┘  │
                    │       └───────────────────┬───────────────────────┘
                    │                           │
                    │               ┌───────────┴───────────┐
                    │               │                       │
                    │       ┌───────▼───────┐       ┌───────▼───────┐
                    │       │  Native Text  │       │   OCR Mode    │
                    │       │  Extraction   │       │               │
                    │       │  (PyPDF/DOCX) │       │               │
                    │       └───────┬───────┘       └───────┬───────┘
                    │               │                       │
                    │               │               ┌───────▼───────────────┐
                    │               │               │  Google Cloud Vision  │
                    │               │               │      API (OCR)        │
                    │               │               │  ┌─────────────────┐  │
                    │               │               │  │ Upload to GCS   │  │
                    │               │               │  │ Process OCR     │  │
                    │               │               │  │ Extract text    │  │
                    │               │               │  └─────────────────┘  │
                    │               │               └───────┬───────────────┘
                    │               │                       │
                    │               └───────────┬───────────┘
                    │                           │
                    │                           ▼
                    │       ┌───────────────────────────────────────────┐
                    │       │        STEP 4: DOCUMENT CLASSIFICATION     │
                    │       │  ┌─────────────────────────────────────┐  │
                    │       │  │  LLM classifies document type:      │  │
                    │       │  │  • PURCHASE_ORDER                   │  │
                    │       │  │  • INVOICE                          │  │
                    │       │  │  • LEASE                            │  │
                    │       │  │  • NDA                              │  │
                    │       │  │  • CONTRACT                         │  │
                    │       │  └─────────────────────────────────────┘  │
                    │       └───────────────────┬───────────────────────┘
                    │                           │
                    │                           ▼
                    │       ┌───────────────────────────────────────────┐
                    │       │          STEP 5: DATA EXTRACTION           │
                    │       │  ┌─────────────────────────────────────┐  │
                    │       │  │  Based on document type:            │  │
                    │       │  │  • PO → po_extractor.py             │  │
                    │       │  │  • Invoice → extract_invoice_data   │  │
                    │       │  │  • Lease → extract_lease_data       │  │
                    │       │  │  • NDA → extract_nda_data           │  │
                    │       │  │  • Contract → extract_contract_data │  │
                    │       │  │                                     │  │
                    │       │  │  Extracted fields:                  │  │
                    │       │  │  • Party names (vendor/customer)    │  │
                    │       │  │  • Document IDs (PO#, Invoice#)     │  │
                    │       │  │  • Dates (issue, due, delivery)     │  │
                    │       │  │  • Amounts & Currency               │  │
                    │       │  │  • Line items                       │  │
                    │       │  │  • Tax details                      │  │
                    │       │  │  • Payment details                  │  │
                    │       │  └─────────────────────────────────────┘  │
                    │       └───────────────────┬───────────────────────┘
                    │                           │
                    └───────────────────────────┤
                                                │
                                                ▼
    ┌───────────────────────────────────────────────────────────────────┐
    │                    STEP 6: SAVE TO CACHE                           │
    │  ┌─────────────────────────────────────────────────────────────┐  │
    │  │  For PO:                                                    │  │
    │  │  • Save to po_cache/ (local + GCS)                         │  │
    │  │  • Update PO Index (for fast lookup)                       │  │
    │  │  • Upload PDF to GCS: purchase_orders/{filename}           │  │
    │  │                                                             │  │
    │  │  For Invoice:                                               │  │
    │  │  • Save to extraction_cache/ (local + GCS)                 │  │
    │  └─────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────┬───────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │                               │
            ┌───────▼───────┐               ┌───────▼───────┐
            │  PURCHASE     │               │   INVOICE     │
            │   ORDER       │               │   (Continue   │
            │  (Complete)   │               │    to Step 7) │
            └───────┬───────┘               └───────┬───────┘
                    │                               │
                    ▼                               ▼
    ┌───────────────────────────┐   ┌───────────────────────────────────────┐
    │  Return PO Extraction     │   │     STEP 7: DUPLICATE INVOICE CHECK    │
    │  Results to User          │   │  ┌─────────────────────────────────┐  │
    │  • PO Number              │   │  │  Check if Invoice ID exists     │  │
    │  • Vendor/Customer        │   │  │  in extractions_store           │  │
    │  • Line Items             │   │  └─────────────────────────────────┘  │
    │  • Amounts                │   └───────────────────┬───────────────────┘
    └───────────────────────────┘                       │
                                        ┌───────────────┴───────────────┐
                                        │                               │
                                ┌───────▼───────┐               ┌───────▼───────┐
                                │  DUPLICATE    │               │   UNIQUE      │
                                │   FOUND       │               │   (Continue)  │
                                └───────┬───────┘               └───────┬───────┘
                                        │                               │
                                        ▼                               ▼
                        ┌───────────────────────────┐   ┌───────────────────────────────────────┐
                        │  ⚠️ Return Warning         │   │     STEP 8: PO MATCHING CHECK          │
                        │  • Don't save to Excel    │   │  ┌─────────────────────────────────┐  │
                        │  • Show duplicate info    │   │  │  Match invoice with PO:         │  │
                        └───────────────────────────┘   │  │                                 │  │
                                                        │  │  Primary: Match by PO Number    │  │
                                                        │  │  • Search PO Index by po_number │  │
                                                        │  │                                 │  │
                                                        │  │  Fallback: Match by Details     │  │
                                                        │  │  • Vendor/Customer names        │  │
                                                        │  │  • Item descriptions            │  │
                                                        │  │  • Amount matching              │  │
                                                        │  └─────────────────────────────────┘  │
                                                        └───────────────────┬───────────────────┘
                                                                            │
                                                            ┌───────────────┴───────────────┐
                                                            │                               │
                                                    ┌───────▼───────┐               ┌───────▼───────┐
                                                    │  PO NOT       │               │  PO MATCHED   │
                                                    │   FOUND       │               │               │
                                                    └───────┬───────┘               └───────┬───────┘
                                                            │                               │
                                                            ▼                               ▼
                                        ┌───────────────────────────────┐   ┌───────────────────────────────┐
                                        │  ⚠️ Return Warning             │   │  STEP 9: SAVE TO EXCEL         │
                                        │  ┌─────────────────────────┐  │   │  ┌─────────────────────────┐  │
                                        │  │ • Don't save to Excel  │  │   │  │ • Add row with:         │  │
                                        │  │ • Show PO not found    │  │   │  │   - Document details    │  │
                                        │  │ • Suggest: Upload PO   │  │   │  │   - Party names         │  │
                                        │  │   first                │  │   │  │   - Amounts/Currency    │  │
                                        │  │ • Return extracted     │  │   │  │   - Dates               │  │
                                        │  │   data for reference   │  │   │  │   - Matched PO info     │  │
                                        │  └─────────────────────────┘  │   │  │ • Save to GCS (if      │  │
                                        └───────────────────────────────┘   │  │   enabled)              │  │
                                                                            │  └─────────────────────────┘  │
                                                                            └───────────────────┬───────────┘
                                                                                                │
                                                                                                ▼
                                                                            ┌───────────────────────────────┐
                                                                            │  STEP 10: RETURN RESULTS       │
                                                                            │  ┌─────────────────────────┐  │
                                                                            │  │ • Extraction results    │  │
                                                                            │  │ • Matched PO details    │  │
                                                                            │  │ • Dashboard update      │  │
                                                                            │  │ • UI display            │  │
                                                                            │  └─────────────────────────┘  │
                                                                            └───────────────────────────────┘
```

---

## Storage Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   STORAGE LAYERS                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    ┌───────────────────────────────────────────────────────────────────────────────────┐
    │                              GOOGLE CLOUD STORAGE (GCS)                            │
    │                           gs://bucket-name/cache/                                  │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
    │  │                                                                             │  │
    │  │  purchase_orders/          ← PO PDF files                                   │  │
    │  │    ├── PO-2025-001.pdf                                                      │  │
    │  │    ├── PO-2025-002.pdf                                                      │  │
    │  │    └── ...                                                                  │  │
    │  │                                                                             │  │
    │  │  po_cache/                 ← PO extraction cache                            │  │
    │  │    ├── {hash}_po.json      (extracted data + metadata)                      │  │
    │  │    └── po_index.json       (PO number → file hash mapping)                  │  │
    │  │                                                                             │  │
    │  │  extraction_cache/         ← Invoice/Document extraction cache              │  │
    │  │    └── {hash}_extraction.json                                               │  │
    │  │                                                                             │  │
    │  │  chatbot_cache/            ← Chatbot session cache                          │  │
    │  │    └── {hash}_chatbot.json                                                  │  │
    │  │                                                                             │  │
    │  │  extractions/              ← Individual extraction records                  │  │
    │  │    └── {extraction_id}.json                                                 │  │
    │  │                                                                             │  │
    │  │  exports/                  ← Excel exports                                  │  │
    │  │    └── contract_extractions.xlsx                                            │  │
    │  │                                                                             │  │
    │  └─────────────────────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            │ Sync
                                            ▼
    ┌───────────────────────────────────────────────────────────────────────────────────┐
    │                              LOCAL FILE STORAGE                                    │
    │                           C:\Users\Admin\INVAP\                                   │
    │  ┌─────────────────────────────────────────────────────────────────────────────┐  │
    │  │                                                                             │  │
    │  │  po_cache/                 ← Local PO cache (fallback)                      │  │
    │  │    ├── {hash}_po.json                                                       │  │
    │  │    └── po_index.json                                                        │  │
    │  │                                                                             │  │
    │  │  extraction_cache/         ← Local extraction cache                         │  │
    │  │    └── {hash}_extraction.json                                               │  │
    │  │                                                                             │  │
    │  │  chatbot_cache/            ← Local chatbot cache                            │  │
    │  │    └── {hash}_chatbot.json                                                  │  │
    │  │                                                                             │  │
    │  │  extractions/              ← Local extraction records                       │  │
    │  │    └── {extraction_id}.json                                                 │  │
    │  │                                                                             │  │
    │  │  contract_extractions.xlsx ← Excel file                                     │  │
    │  │                                                                             │  │
    │  │  PurchaseOrders/           ← Source PO PDFs                                 │  │
    │  │    └── *.pdf                                                                │  │
    │  │                                                                             │  │
    │  │  invoices/                 ← Source invoice PDFs                            │  │
    │  │    └── *.pdf                                                                │  │
    │  │                                                                             │  │
    │  └─────────────────────────────────────────────────────────────────────────────┘  │
    └───────────────────────────────────────────────────────────────────────────────────┘
```

---

## PO Matching Logic

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              PO MATCHING DECISION TREE                                   │
└─────────────────────────────────────────────────────────────────────────────────────────┘

                        ┌───────────────────────────────┐
                        │      Invoice Extracted        │
                        │                               │
                        │  • Invoice ID: INV-2025-001  │
                        │  • PO Number: PO-2025-050    │
                        │  • Vendor: ABC Corp          │
                        │  • Amount: $5,000            │
                        └───────────────┬───────────────┘
                                        │
                                        ▼
                        ┌───────────────────────────────┐
                        │  Does Invoice have PO Number? │
                        └───────────────┬───────────────┘
                                        │
                        ┌───────────────┴───────────────┐
                        │                               │
                ┌───────▼───────┐               ┌───────▼───────┐
                │     YES       │               │      NO       │
                │ (Primary      │               │ (Fallback     │
                │  Matching)    │               │  Matching)    │
                └───────┬───────┘               └───────┬───────┘
                        │                               │
                        ▼                               ▼
        ┌───────────────────────────┐   ┌───────────────────────────┐
        │  Search PO Index by       │   │  Search by Details:       │
        │  PO Number                │   │                           │
        │                           │   │  Score Calculation:       │
        │  po_index.json:           │   │  • Vendor match: +40 pts  │
        │  {                        │   │  • Customer match: +30 pts│
        │    "hash1": {             │   │  • Item match: +15 pts    │
        │      "po_number": "PO-    │   │  • Amount match: +15 pts  │
        │       2025-050",          │   │                           │
        │      "vendor": "...",     │   │  Min score for match: 30  │
        │      ...                  │   │  (vendor OR customer)     │
        │    }                      │   │                           │
        │  }                        │   │                           │
        └───────────────┬───────────┘   └───────────────┬───────────┘
                        │                               │
                        ▼                               ▼
        ┌───────────────────────────┐   ┌───────────────────────────┐
        │  PO Number == "PO-2025-   │   │  Best Match Score >= 30?  │
        │   050" found in index?    │   │                           │
        └───────────────┬───────────┘   └───────────────┬───────────┘
                        │                               │
            ┌───────────┴───────────┐       ┌───────────┴───────────┐
            │                       │       │                       │
    ┌───────▼───────┐       ┌───────▼───────┐       ┌───────▼───────┐
    │   MATCHED     │       │  NOT FOUND    │       │   MATCHED     │
    │   ✅          │       │   ⚠️          │       │   ✅          │
    └───────┬───────┘       └───────┬───────┘       └───────┬───────┘
            │                       │                       │
            ▼                       ▼                       ▼
    ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
    │ Save to Excel │       │ Return Warning│       │ Save to Excel │
    │ with PO info  │       │ Don't save    │       │ with PO info  │
    └───────────────┘       └───────────────┘       └───────────────┘
```

---

## API Endpoints Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   API ENDPOINTS                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  PURCHASE ORDER APIs                                                                     │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  POST /api/upload-po          Upload & extract PO (auto-cached)                         │
│  GET  /api/po/list            List all available POs                                    │
│  GET  /api/po/{file_hash}     Get full PO details                                       │
│  POST /api/po/match           Match invoice with PO                                     │
│  GET  /api/po/count           Get PO count                                              │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  INVOICE/DOCUMENT APIs                                                                   │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  POST /api/upload             Upload document for extraction                            │
│  POST /api/extract/{id}       Extract document (checks PO match for invoices)          │
│  GET  /api/extraction/{id}    Get extraction by ID                                      │
│  GET  /api/extractions-list   List all extractions                                      │
│  GET  /api/extraction-status/{id}  Get extraction status                               │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  DATA EXPORT APIs                                                                        │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  GET  /api/excel-data         Get Excel data                                            │
│  GET  /api/download-excel     Download Excel file                                       │
│  GET  /api/json-data          Get all JSON data                                         │
│  GET  /api/dashboard          Get dashboard stats                                       │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Document Processing Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                            DOCUMENT PROCESSING PIPELINE                                  │
└─────────────────────────────────────────────────────────────────────────────────────────┘

    PDF/DOCX/TXT
         │
         ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Native Text    │     │   Hybrid PDF    │     │  Scanned PDF    │
│  Extraction     │     │  (Text + OCR)   │     │  (Full OCR)     │
│                 │     │                 │     │                 │
│  PyPDF2/python- │     │  PyPDF2 +       │     │  Google Cloud   │
│  docx           │     │  Vision API     │     │  Vision API     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │    Combined Text        │
                    │    (with page mapping)  │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Document Classifier    │
                    │  (GPT-4o-mini)          │
                    │                         │
                    │  → PURCHASE_ORDER       │
                    │  → INVOICE              │
                    │  → LEASE                │
                    │  → NDA                  │
                    │  → CONTRACT             │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Type-Specific          │
                    │  Extraction             │
                    │  (GPT-4o-mini)          │
                    │                         │
                    │  Structured JSON Output │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Validation & Matching  │
                    │                         │
                    │  • Duplicate check      │
                    │  • PO matching          │
                    │  • Risk scoring         │
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │  Storage                │
                    │                         │
                    │  • Cache (GCS + Local)  │
                    │  • Excel (if matched)   │
                    │  • Dashboard update     │
                    └─────────────────────────┘
```
