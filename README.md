# Invoice to AP — Automated Invoice Processing & 3-Way Matching

An end-to-end Accounts Payable automation system that extracts invoice data using AI, matches invoices against Purchase Orders (POs) and Goods Received Notes (GRNs), manages billing approvals, and tracks payment status.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Application Flow](#application-flow)
- [Matching Logic](#matching-logic)
- [Exception Handling](#exception-handling)
- [Data Table](#data-table)
- [Billing Table](#billing-table)
- [Payment Table](#payment-table)
- [Chatbot](#chatbot)
- [Notification System](#notification-system)
- [Multi-Currency Support](#multi-currency-support)
- [Test Documents](#test-documents)
- [Project Structure](#project-structure)
- [API Reference](#api-reference)

---

## Overview

This application automates the Accounts Payable workflow:

1. **Upload** invoices (PDF, DOCX, HTML, TXT) for AI-powered data extraction.
2. **Upload** POs and GRNs via the Buyer Portal.
3. **Match** invoices against POs and GRNs (2-way or 3-way matching).
4. **Bill** — enter amounts received with auto-calculated tax, then approve.
5. **Track** payment status across all matched invoices.
6. **Chat** — ask the AI chatbot questions about any uploaded document.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python, FastAPI, Uvicorn |
| Frontend | React 18, React Router v6, Vite, Tailwind CSS |
| AI Extraction | OpenAI GPT-4o-mini, LangChain, LangGraph |
| OCR | Google Cloud Vision (for scanned PDFs) |
| Chatbot | FAISS vector store, OpenAI embeddings, RAG pipeline |
| Storage | Local filesystem + Google Cloud Storage (GCS) |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key (set `OPENAI_API_KEY` environment variable)
- Google Cloud credentials (optional, for GCS and OCR)

### Run the Application

```bash
python run.py
```

This starts both the backend and frontend:

- **Backend API**: http://127.0.0.1:8000
- **Frontend UI**: http://localhost:5173

The frontend proxies all `/api` requests to the backend automatically.

### Stop the Application

Press `Ctrl+C` in the terminal (or `Ctrl+Break` on Windows if `Ctrl+C` doesn't respond).

---

## Application Flow

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Upload      │────>│ AI Extract   │────>│ PO/GRN Match  │
│ Invoice     │     │ (GPT-4o)     │     │ (2/3-way)     │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                  │
                                    ┌─────────────┴─────────────┐
                                    │                           │
                              ┌─────▼─────┐             ┌──────▼──────┐
                              │ MATCHED   │             │ REJECTED    │
                              │           │             │ (Exception) │
                              └─────┬─────┘             └─────────────┘
                                    │
                              ┌─────▼─────┐
                              │ Data Table │
                              │ (Excel)    │
                              └─────┬─────┘
                                    │
                              ┌─────▼──────┐
                              │ Billing    │──── Enter amt received,
                              │ Table      │     auto-calc tax, approve
                              └─────┬──────┘
                                    │ (on Approved)
                              ┌─────▼──────┐
                              │ Payment    │──── Billed = invoice amt,
                              │ Table      │     Amt Rec = billing total
                              └────────────┘
```

### Step by Step

1. **Upload Invoice** — drag-and-drop or browse on the Home page.
2. **AI Extraction** — the system uses GPT-4o-mini to extract structured data (vendor, amounts, line items, dates, tax details, etc.).
3. **PO Matching** — the system looks up a matching PO by PO number from the invoice. If found, it checks vendor details and line items.
4. **GRN Matching** — if a GRN exists for the PO, it performs 3-way matching (Invoice vs PO vs GRN). Otherwise, 2-way matching (Invoice vs PO).
5. **Data Table** — matched invoices appear in the Data Table and can be exported to Excel.
6. **Billing Table** — enter the amount received (full or partial). Tax is auto-calculated from the invoice's original tax percentage. Change status to "Approved" to push to Payment Table.
7. **Payment Table** — shows billed amount (always the original invoice amount), amount received (from approved billing), balance due, and auto-calculated payment status.

---

## Matching Logic

### Priority Order

1. **PO exists?** — If no PO matches the invoice's PO number, the invoice is **rejected** ("PO Not Found").
2. **Vendor match?** — The invoice vendor must match the PO vendor. If not, **rejected** ("Vendor Mismatch").
3. **GRN exists?** — If a GRN exists for the PO, perform **3-way match**. If not, perform **2-way match**.

### 2-Way Match (Invoice vs PO)

Used when a matching PO exists but no GRN has been uploaded.

- Compares invoice line items (descriptions, quantities) against the PO.
- If items and quantities match, the invoice is accepted with a warning: "GRN not uploaded — matched against PO only."
- If items or quantities don't match, the invoice is rejected.

### 3-Way Match (Invoice vs PO vs GRN)

Used when both a matching PO and GRN exist.

- Compares invoice line items against the **GRN** (received quantities), not the PO.
- This is important because the GRN reflects what was actually received — which may be less than what the PO ordered.
- If all items and quantities match, the invoice is accepted: "3-way match successful — ready for payment."
- If items or quantities don't match, the invoice is rejected with specific item-level issues.

### Why GRN Takes Priority Over PO

If the GRN shows fewer items received than the PO ordered, the invoice should only be paid for what was actually received. The matching logic enforces this by comparing against GRN quantities when available.

---

## Exception Handling

The system handles five specific exception cases. Each generates a notification explaining the issue.

| Exception | Cause | Result |
|-----------|-------|--------|
| **No PO** | Invoice references a PO number that doesn't exist in the system | Rejected — cannot enter AP without a valid PO |
| **Vendor Mismatch** | Invoice vendor name doesn't match the PO vendor | Rejected — possible fraud or wrong PO reference |
| **Qty Exceeds GRN** | Invoice claims more quantity than the GRN shows was received | Rejected — can only bill for what was received |
| **Extra Items** | Invoice has line items not present in the PO/GRN, or PO/GRN has items missing from the invoice | Rejected — line item discrepancy |
| **No GRN** | PO exists but no GRN has been uploaded yet | Falls back to 2-way match (Invoice vs PO) with a warning |

### Exception Notifications

Each exception generates a specific notification with:
- **Type**: `error` (for rejections) or `warning` (for fallbacks like No GRN)
- **Title**: describes the exception (e.g., "Vendor / Supplier Mismatch")
- **Message**: detailed explanation with specific values (e.g., "Invoice vendor 'ABC Corp' does not match PO vendor 'XYZ Ltd'")

---

## Data Table

The Data Table is the central view where all successfully extracted and matched invoices are displayed in a structured, Excel-like format. It serves as the consolidated output of the extraction and matching pipeline.

### Columns

| Column | Description |
|--------|-------------|
| Extracted At | Timestamp when the document was extracted |
| Document Name | Original uploaded file name |
| Unique ID | System-generated extraction ID |
| IDs | Invoice number or document identifier extracted from the content |
| Type | Document type (e.g., Invoice, Contract) |
| Account Type | Accounting head / category extracted from the invoice |
| Party Names | Vendor / supplier / buyer names extracted from the document |
| Start Date | Invoice issue date or contract start date |
| Due Date | Payment due date |
| Amount | Invoice total amount (formatted with currency) |
| Currency | Currency code (INR, USD, GBP, SAR, QAR, OMR, etc.) |
| Risk Score | AI-assessed risk level (Low / Medium / High / Critical) |
| Matched PO | PO number that the invoice was matched against (blank if no match) |

### Features

- **Resizable columns** — drag column borders to resize widths, similar to Excel.
- **Text wrapping** — the "Matched PO" column wraps long PO numbers instead of truncating.
- **Risk color coding** — risk scores are color-coded: green (Low), amber (Medium), orange (High), red (Critical).
- **Excel export** — click "Download Excel" to export all rows as an `.xlsx` file for offline analysis or reporting.
- **Refresh** — reload data from the backend without navigating away.
- **Full-width layout** — the table stretches to fill the entire page for a desktop-application feel.

### Data Flow

```
Uploaded Document
      │
      ▼
AI Extraction (GPT-4o-mini)
      │
      ▼
PO/GRN Matching
      │
      ├── Matched ──────► Data Table row (all columns populated)
      │
      └── Rejected ─────► Notification only (not shown in Data Table)
```

Only invoices with `status = "completed"` (i.e., successfully extracted and matched) appear in the Data Table. Rejected or failed extractions are excluded and visible only through the notification system and dashboard counts.

### Excel Download

The exported Excel file (`contract_extractions.xlsx`) contains all the same columns as the Data Table. This is useful for:

- Sharing extraction results with stakeholders who don't have access to the application.
- Feeding data into external ERP, accounting, or auditing systems.
- Archival and compliance record-keeping.

---

## Billing Table

The Billing Table manages how much has been received/paid against each matched invoice.

### Columns

| Column | Editable | Source |
|--------|----------|--------|
| Billing Date | Yes | User sets the billing date |
| Invoice # | No | From extracted invoice |
| Vendor | No | From extracted invoice |
| PO Number | No | From PO match |
| Description | No | From invoice line items |
| Invoice Amt | No | Original invoice total (incl. tax) |
| **Amt Received** | **Yes** | User enters how much was received/paid |
| Tax % | No | Auto-extracted from the invoice's original tax rate |
| Tax Amt | No | Auto-calculated: `Amt Received x Tax %` |
| Total Payable | No | Auto-calculated: `Amt Received + Tax Amt` |
| Currency | No | From invoice |
| Due Date | No | From invoice |
| Payment Terms | No | From invoice |
| **Status** | **Yes** | Dropdown: Draft / Approved / Submitted / Rejected |
| **Remarks** | **Yes** | Free text notes |

### Tax Auto-Calculation

Tax is never manually editable. The system extracts the tax percentage from the original invoice (e.g., 18% IGST, 15% VAT, 8.875% sales tax) and applies it to the Amount Received. This prevents tax miscalculations.

### Approval Flow

- **Draft** — billing entered but not finalized. Does NOT affect Payment Table.
- **Approved** — billing confirmed. Amount Received + Tax flows to Payment Table.
- **Submitted / Rejected** — additional status options. Do NOT affect Payment Table.

Only **Approved** billings are reflected in the Payment Table.

---

## Payment Table

The Payment Table is a **read-only** view showing the payment status of all matched invoices.

### Columns

| Column | Value |
|--------|-------|
| Invoice Uploaded | Upload timestamp |
| Account Type | From invoice extraction |
| PO Number | From PO match |
| Invoice # | From invoice |
| Inv Date | Invoice date |
| Due Date | Payment due date |
| **Billed Amount** | Always the original invoice amount (never changes) |
| **Amt Rec** | From Billing Table (amt_received + tax) — only when billing is Approved |
| **Bal Due** | Billed Amount - Amt Rec |
| **Payment Status** | Auto-calculated |

### Payment Status Rules

| Condition | Status |
|-----------|--------|
| Amount Received = 0 | **Not paid** |
| 0 < Amount Received < Billed Amount | **Partially paid** |
| Amount Received >= Billed Amount | **Full paid** |

---

## Chatbot

An AI-powered chatbot that can answer questions about uploaded documents.

### Features

- **RAG pipeline**: documents are chunked and indexed using FAISS + OpenAI embeddings.
- **Per-document chat**: ask questions about a specific invoice, PO, or GRN.
- **All-documents chat**: ask questions across all loaded invoices, POs, and GRNs (e.g., "How many invoices are there?", "Which invoices have matching GRNs?").
- **Context-aware**: includes PO/GRN match status, failure reasons, and item issues in the searchable text.

### Usage

1. The chatbot auto-loads all completed invoices, POs, and GRNs at startup.
2. Use "Change Document" to switch between individual documents or the "All" view.
3. Ask natural language questions in the chat input.

---

## Notification System

In-app notifications for all extraction, matching, and billing events.

- **Bell icon** in the header with unread count badge.
- **Notification types**: success (green), error (red), warning (amber), info (blue).
- **Persistent**: notifications are stored and survive page refreshes.
- **Actions**: mark as read, mark all as read, clear all.

### Example Notifications

- "Invoice matched successfully with PO-MNTH-2026-001 and GRN" (success)
- "PO Not Found — invoice references PO-XXX which does not exist" (error)
- "Vendor Mismatch — invoice vendor does not match PO vendor" (error)
- "GRN not uploaded — falling back to 2-way match" (warning)
- "Billing approved — amount received will reflect in Payment Table" (success)

---

## Multi-Currency Support

The system handles invoices from multiple countries with different currencies and tax regimes:

| Country | Currency | Tax System | Rate |
|---------|----------|------------|------|
| India | INR | GST (IGST / CGST+SGST) | 18% |
| Qatar | QAR | No VAT | 0% |
| USA | USD | Sales Tax (state-specific) | 8.875% (NY) |
| UK | GBP | VAT | 20% |
| Saudi Arabia (KSA) | SAR | VAT (ZATCA) | 15% |
| Oman | OMR | VAT | 5% |

Tax percentages are extracted from the invoice's `amounts.taxes` array and applied automatically in the Billing Table. No manual tax entry is needed.

---

## Test Documents

Pre-built HTML test documents are available in `New data for AP/`:

```
New data for AP/
├── Invoice/
│   ├── INV-MNTH-2026-001.html        # India, monthly, INR, 18% IGST
│   ├── INV-MNTH-2026-002.html        # India, monthly
│   ├── INV-QRTR-2026-001.html        # India, quarterly
│   ├── INV-QRTR-2026-002.html        # India, quarterly
│   ├── INV-QTR-2026-001.html         # Qatar, QAR, 0% tax
│   ├── INV-USA-2026-001.html         # USA, USD, 8.875% sales tax
│   ├── INV-UK-2026-001.html          # UK, GBP, 20% VAT
│   ├── INV-KSA-2026-001.html         # KSA, SAR, 15% VAT
│   ├── INV-OMN-2026-001.html         # Oman, OMR, 5% VAT
│   └── Exception Cases/
│       ├── INV-EXC-NO-PO.html        # References non-existent PO
│       ├── INV-EXC-VENDOR-MISMATCH.html  # Wrong vendor name
│       ├── INV-EXC-QTY-EXCEEDS-GRN.html  # Qty > GRN received
│       ├── INV-EXC-EXTRA-ITEMS.html      # Items not in PO/GRN
│       └── INV-EXC-NO-GRN.html          # PO exists but no GRN
├── POs/
│   ├── PO-MNTH-2026-001.html         # India monthly PO
│   ├── PO-QRTR-2026-001.html         # India quarterly PO
│   ├── PO-QTR-2026-001.html          # Qatar PO
│   ├── PO-USA-2026-001.html          # USA PO
│   ├── PO-UK-2026-001.html           # UK PO
│   ├── PO-KSA-2026-001.html          # KSA PO
│   └── PO-OMN-2026-001.html          # Oman PO
└── GRNs/
    ├── GRN-MNTH-2026-001.html        # India monthly GRN
    ├── GRN-MNTH-2026-002.html        # India monthly GRN
    ├── GRN-QRTR-2026-001.html        # India quarterly GRN
    ├── GRN-QRTR-2026-002.html        # India quarterly GRN
    ├── GRN-QTR-2026-001.html         # Qatar GRN
    ├── GRN-USA-2026-001.html         # USA GRN
    ├── GRN-UK-2026-001.html          # UK GRN
    ├── GRN-KSA-2026-001.html         # KSA GRN
    └── GRN-OMN-2026-001.html         # Oman GRN
```

### Testing Workflow

1. Start the app with `python run.py`.
2. Go to "Buyer Portal" and upload POs first, then GRNs.
3. Go to Home and upload invoices (start with the normal ones, then try exception cases).
4. Check the Dashboard for match counts.
5. Go to Billing Table to enter amounts and approve.
6. Go to Payment Table to verify amounts flow correctly.

---

## Project Structure

```
InvoicetoAP_GRN/
├── app.py                    # FastAPI backend (routes, extraction, billing, payment)
├── run.py                    # Starts backend + frontend together
├── po_matcher.py             # PO/GRN/Invoice matching logic
├── document_chat.py          # AI chatbot (RAG with FAISS)
├── cache_manager.py          # GCS and local file caching
├── extraction_agent.py       # LangGraph extraction agent
├── extraction_orchestrator.py# Alternative extraction orchestrator
├── po_extractor.py           # PO data extraction
├── grn_extractor.py          # GRN data extraction
├── document_parser.py        # Document parsing and OCR
├── test_billing_payment.py   # Unit tests for billing/payment logic
├── data/                     # Extracted data (all_invoices.json, etc.)
├── New data for AP/          # Test HTML documents
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # Routes
│   │   ├── api/client.js     # API client functions
│   │   ├── pages/
│   │   │   ├── Home.jsx      # Upload, extract, dashboard
│   │   │   ├── ExcelTable.jsx    # Data table
│   │   │   ├── BillingTable.jsx  # Billing management
│   │   │   ├── PaymentTable.jsx  # Payment tracking
│   │   │   ├── BuyerPortal.jsx   # PO/GRN upload
│   │   │   └── ...
│   │   └── components/
│   │       ├── Layout.jsx    # Navigation layout
│   │       └── ResizableTable.jsx # Resizable table columns
│   └── vite.config.js        # Vite config with API proxy
└── requirements.txt          # Python dependencies
```

---

## API Reference

### Document Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload` | Upload document for extraction |
| POST | `/api/extract/{id}` | Start AI extraction |
| GET | `/api/extraction-status/{id}` | Check extraction status |
| GET | `/api/extraction/{id}` | Get extracted data |
| GET | `/api/extractions-list` | List all extractions |
| DELETE | `/api/extraction/{id}` | Delete extraction |

### PO & GRN

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/upload-po` | Upload Purchase Order |
| POST | `/api/upload-grn` | Upload Goods Received Note |

### Billing

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/billing` | Get all billing rows |
| PATCH | `/api/billing/{id}` | Update billing (amt_received, remarks, billing_status, billing_date) |

### Payment

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/payment-status` | Get all payment rows |
| PATCH | `/api/payment-status/{id}` | Update payment status |

### Dashboard

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/dashboard` | Dashboard stats (totals, matched, unmatched) |

### Chatbot

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/load-all-documents` | Load all docs for chat |
| POST | `/api/chat/ask` | Ask a question |
| DELETE | `/api/chat/session/{id}` | Delete chat session |

### Notifications

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications` | Get all notifications |
| PATCH | `/api/notifications/read-all` | Mark all as read |
| PATCH | `/api/notifications/{id}/read` | Mark one as read |
| DELETE | `/api/notifications` | Clear all notifications |

### File Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/files/list` | List cached files (extractions, POs, GRNs) |
| POST | `/api/files/delete` | Delete specific cached files |
| POST | `/api/files/clear-all` | Clear all cached data |
