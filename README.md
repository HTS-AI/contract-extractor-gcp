# Contract Extraction Engine

An AI-powered Contract Extraction Engine with Streamlit web interface for extracting structured contract data from Lease, NDA, and Service Contract documents. Uses OpenAI's `gpt-4o-mini` model to extract key information with high precision and zero hallucinations.

## Features

### Core Functionality
- **Multiple Document Types**: Automatically detects and extracts from:
  - **Lease Agreements** - Property, equipment, or asset leases
  - **NDA Documents** - Non-Disclosure Agreements
  - **Service Contracts** - Business service agreements
- **Multiple Input Formats**: Supports PDF, DOCX, TXT, and raw text input
- **OCR Support**: Handles scanned documents using Google Cloud Vision API
- **Streamlit Web Interface**: User-friendly dashboard for document upload and extraction
- **Automatic Excel Export**: Automatically saves all extractions to `contract_extractions.xlsx`

### Extracted Information
The system extracts the following key fields from all document types:
- **Document Type** - Automatically detected (LEASE, NDA, or CONTRACT)
- **Party Names** - All parties involved in the agreement
- **Start Date** - Contract/lease start date
- **Due Date** - Payment due date or deadline
- **Amount** - Total payment amount (integer only, no currency)
- **Currency** - Detected currency (INR, USD, EUR, GBP, JPY, CNY, etc.)
- **Frequency** - Payment frequency (Monthly, Quarterly, Annual, etc.)
- **Account Type (Head)** - Automatically assigned based on document type
- **Document IDs** - All identification numbers (Invoice ID, Contract ID, Reference ID, Agreement ID, Document Number)
- **Risk Score** - Calculated risk assessment (0-100)

### Additional Features
- **Currency Detection**: Automatically detects and extracts currency from documents (Rs., ₹, Rupees, USD, $, EUR, €, GBP, £, etc.)
- **Payment Calculations**: Automatically calculates per-period and per-month amounts
- **Percentage Filtering**: Automatically filters out percentage-only values (e.g., "10%", "10 percent") - only extracts actual monetary amounts
- **Risk Assessment**: Calculates risk scores based on missing information (missing due date and amount are high risk)
- **Source References**: Provides page numbers and text snippets for extracted data
- **Document Summary**: Generates comprehensive summaries of extracted information

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up Environment Variables

Create a `.env` file in the project root:

```bash
OPENAI_API_KEY=your-api-key-here
```

Or set it in your environment:

**Linux/Mac:**
```bash
export OPENAI_API_KEY="your-api-key-here"
```

**Windows PowerShell:**
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

### 3. (Optional) Google Cloud Vision API Setup

For scanned PDF support, set up Google Cloud Vision API:
1. Create a GCP service account
2. Download the service account JSON key file
3. Place it in the project root (default: `gcp-creds.json`)

## Usage

### Streamlit Web Interface (Recommended)

Launch the web interface:

```bash
streamlit run app.py
```

Then:
1. Navigate to **"📤 Extract Contract"** page
2. Upload a PDF, DOCX, or TXT file, or paste contract text
3. Click **"🔍 Extract Contract Data"**
4. View results in the **"📊 Dashboard"** or **"📋 View Details"** pages
5. Download the Excel file with all extracted data

### Command Line Interface

#### Extract from PDF file:
```bash
python main.py contract_documents/NDA-NSIL.pdf --output output.json
```

#### Extract from DOCX file:
```bash
python main.py contract_documents/contract.docx --output output.json
```

#### Extract from text file:
```bash
python main.py contract_documents/contract.txt --output output.json
```

#### Use OCR for scanned PDF:
```bash
python main.py contract_documents/scanned_contract.pdf --ocr --output output.json
```

### Python API

```python
from extraction_orchestrator import ExtractionOrchestrator

# Initialize orchestrator
orchestrator = ExtractionOrchestrator(
    api_key="your-api-key",
    use_gcs_vision=True,
    use_semantic_search=True
)

# Extract from file
extracted_data, metadata = orchestrator.extract_from_file("contract.pdf")

# Extract from text
extracted_data, metadata = orchestrator.extract_from_text("Contract text here...")

# Access extracted data
print(extracted_data["document_type"])
print(extracted_data["party_names"]["party_1"])
print(extracted_data["amount"])
print(extracted_data["risk_score"])
```

## Output Format

The extraction engine returns a structured JSON object with the following simplified fields:

```json
{
  "document_type": "CONTRACT",
  "party_names": {
    "party_1": "Company A",
    "party_2": "Company B",
    "additional_parties": []
  },
  "start_date": "2024-01-01",
  "due_date": "2024-12-31",
  "amount": "55000",
  "currency": "INR",
  "frequency": "Monthly",
  "account_type": "Service Contract Revenue",
  "document_ids": {
    "invoice_id": "INV-2024-001",
    "contract_id": "CNT-2024-001",
    "reference_id": "REF-2024-001"
  },
  "risk_score": {
    "score": 20,
    "level": "Low",
    "category": "🟢 Low Risk",
    "risk_factors": []
  },
  "per_period_amount": "4583",
  "per_month_amount": "4583",
  "period_name": "month"
}
```

## Excel Export

All extracted data is automatically saved to `contract_extractions.xlsx` with the following columns:

- **Document Name** - Name of the uploaded file
- **Document Type** - LEASE, NDA, or CONTRACT
- **Party Names** - All parties (formatted as comma-separated list)
- **Start Date** - Contract start date (YYYY-MM-DD)
- **Due Date** - Payment due date (YYYY-MM-DD)
- **Amount** - Payment amount (integer only, no currency)
- **Currency** - Detected currency code (INR, USD, EUR, GBP, JPY, CNY)
- **Frequency** - Payment frequency (Monthly, Quarterly, Annual, etc.)
- **Account Type (Head)** - Account classification
- **ID** - Combined document IDs (Invoice ID, Contract ID, Reference ID, Agreement ID, Document Number)
- **Risk Score** - Calculated risk score (0-100)

The Excel file is automatically updated whenever a new document is extracted. You can download it from the Streamlit dashboard.

## Account Type Assignment

The system automatically assigns account types based on document type:

- **LEASE** → "Lease/Rental Expense"
- **NDA** → "Legal/Compliance Expense"
- **CONTRACT** → "Service Contract Revenue"

If an account type is found in the document, it uses that; otherwise, it assigns based on document type.


## Currency Detection

The system automatically detects currency from documents:

- **Supported Formats**: 
  - Indian Rupees: "Rs.", "Rs ", "₹", "Rupees", "Rupee", "INR"
  - US Dollars: "$", "USD"
  - Euros: "€", "EUR"
  - British Pounds: "£", "GBP"
  - Japanese Yen: "¥", "JPY"
  - Chinese Yuan: "CNY"
- **Detection Method**: Searches both the extracted amount field and the original document text
- **Storage**: Currency is stored separately from amount (amount is integer only)

### Examples:

- Document: "Rs. 55,000 monthly" → Amount: `55000`, Currency: `INR`
- Document: "$5,000 per quarter" → Amount: `5000`, Currency: `USD`
- Document: "₹80,000 annually" → Amount: `80000`, Currency: `INR`

## Payment Calculations

The system automatically calculates payment amounts based on frequency:

- **Per Period Amount**: Calculated from total amount and frequency (e.g., monthly rent, quarterly payment)
- **Per Month Amount**: Monthly equivalent of the payment

### Examples:

**Monthly Payment:**
- Amount: 80,000, Currency: INR, Frequency: Monthly
- Per Period: 80,000 INR (per month)
- Per Month: 80,000 INR

**Annual Payment:**
- Amount: 120,000, Currency: INR, Frequency: Annual
- Per Period: 120,000 INR (per year)
- Per Month: 10,000 INR (120,000 / 12)

## Risk Score Calculation

Risk scores are calculated based on:
- Missing critical information (parties, dates, amounts)
- **Missing Due Date**: +20 points (High Risk)
- **Missing Amount**: +20 points (High Risk)
- **Missing Both Due Date and Amount**: +15 additional points (Critical)
- Missing start date: +10 points
- Missing party information: +15 points
- Missing account type: +5 points
- Overall document completeness

Risk levels:
- **0-29**: 🟢 Low Risk
- **30-59**: 🟡 Medium Risk
- **60-79**: 🟠 High Risk
- **80-100**: 🔴 Critical Risk

## Extraction Rules

1. **Missing Data**: Returns `null` or empty string for any missing or not present data
2. **No Hallucination**: Never invents or assumes contract clauses
3. **Exact Wording**: Preserves original clause wording exactly
4. **Date Format**: Converts all dates to ISO format (YYYY-MM-DD)
5. **Amount Format**: Amounts are stored as integers only (no currency code in amount field)
6. **Currency Detection**: Currency is automatically detected and stored separately
7. **Percentage Filtering**: Percentages (e.g., "10%", "10 percent") are NOT extracted as amounts - only actual monetary values are extracted
8. **Account Type**: Assigns based on document type if not found in document
9. **Document IDs**: All IDs (Invoice ID, Contract ID, Reference ID, Agreement ID, Document Number) are combined into a single "ID" field in Excel

## Project Structure

```
contract_analysis/
├── app.py                          # Streamlit web interface
├── extraction_orchestrator.py      # Main orchestrator (coordinates extraction)
├── document_parser.py              # Document parsing (PDF, DOCX, TXT)
├── document_type_classifier.py     # Document type detection
├── lease_extractor.py              # Lease-specific extraction
├── nda_extractor.py                # NDA-specific extraction
├── contract_extractor_specific.py  # Contract-specific extraction
├── document_summary.py             # Summary generation
├── excel_export.py                 # Excel export functionality
├── vision_gcp.py                  # Google Cloud Vision API integration
├── semantic_search.py              # Semantic search for missing fields
├── main.py                         # Command-line interface
├── requirements.txt                # Python dependencies
└── contract_extractions.xlsx       # Auto-generated Excel file
```

## Requirements

- Python 3.8+
- OpenAI API key
- (Optional) Google Cloud Vision API for scanned PDF support
- (Optional) Tesseract OCR for local OCR (alternative to GCP Vision)

## Dependencies

- `openai>=1.12.0` - OpenAI API client
- `streamlit>=1.28.0` - Web interface framework
- `pandas>=2.0.0` - Data manipulation and Excel export
- `openpyxl>=3.1.0` - Excel file handling
- `PyPDF2>=3.0.0` - PDF text extraction
- `python-docx>=1.1.0` - DOCX file parsing
- `python-dotenv>=1.0.0` - Environment variable management
- `numpy>=1.24.0` - Numerical operations
- `faiss-cpu>=1.7.4` - Vector similarity search (optional)

## Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set up environment:**
```bash
# Create .env file
echo "OPENAI_API_KEY=your-api-key-here" > .env
```

3. **Launch Streamlit app:**
```bash
streamlit run app.py
```

4. **Upload a document** and extract data!

## Features Overview

### Streamlit Dashboard
- **📊 Dashboard**: Overview of extracted contract with key metrics
- **📤 Extract Contract**: Upload documents and extract data
- **📋 View Details**: Detailed view with summary, references, and full JSON

### Automatic Features
- Document type detection
- Account type assignment
- Compliance violation checking
- Risk score calculation
- Payment amount calculations
- Excel file updates

## License

This project is provided as-is for contract automation purposes.
