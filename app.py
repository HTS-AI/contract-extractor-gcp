"""
FastAPI Application for Invoice to Account Payable Application
Extract structured information from invoices and documents
Updated with JSON and Excel data endpoints
"""

import os
import json
import uuid
import re
import tempfile
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Use LangGraph-based agent instead of traditional orchestrator
try:
    from extraction_agent import ExtractionAgent as ExtractionOrchestrator
    print("[STARTUP] Using LangGraph-based ExtractionAgent")
    # For LangGraph agent, we'll still create instances as needed
    get_orchestrator = None
except ImportError:
    # Fallback to traditional orchestrator if LangGraph not available
    from extraction_orchestrator import ExtractionOrchestrator, get_orchestrator
    print("[STARTUP] Using traditional ExtractionOrchestrator (LangGraph not available)")
from docx_to_pdf_converter import convert_docx_to_pdf, should_convert_to_pdf
from excel_export import update_contract_excel
from document_chat import get_chatbot
from cache_manager import get_cache_manager
from po_extractor import POExtractor, get_po_extractor
from po_matcher import get_po_matcher, match_invoice
import extraction_status_manager

# Cache chatbot instance to avoid repeated get_chatbot() calls
_cached_chatbot = None

def get_cached_chatbot():
    """Get cached chatbot instance (singleton pattern)."""
    global _cached_chatbot
    if _cached_chatbot is None:
        _cached_chatbot = get_chatbot()
    return _cached_chatbot

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Invoice to Account Payable API",
    description="API for extracting structured data from invoices and documents (PDF, DOCX, TXT)",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# JSON file for persistent storage
EXTRACTIONS_JSON_FILE = Path(__file__).parent / "extractions_data.json"

# Validation folder for chatbot PDFs
VALIDATION_FOLDER = Path(__file__).parent / "chatbot_validation"
VALIDATION_FOLDER.mkdir(exist_ok=True)  # Create folder if it doesn't exist
print(f"[STARTUP] Chatbot validation folder: {VALIDATION_FOLDER.absolute()}")

# In-memory storage for extractions and dashboard data
extractions_store: Dict[str, Dict[str, Any]] = {}

# Status tracking for progress updates - use shared module
extraction_status = extraction_status_manager.extraction_status
dashboard_data = {
    "total_documents": 0,
    "total_invoices": 0,
    "total_pos": 0,
    "matched_invoices": 0,
    "unmatched_invoices": 0,
    "average_risk_score": 0,
    "total_missing_clauses": 0,
    "contract_types": {}
}


def recalculate_dashboard_from_extractions():
    """Recalculate dashboard data from all stored extractions."""
    global dashboard_data
    
    # Reset dashboard data
    dashboard_data["total_documents"] = 0
    dashboard_data["total_invoices"] = 0
    dashboard_data["matched_invoices"] = 0
    dashboard_data["unmatched_invoices"] = 0
    dashboard_data["average_risk_score"] = 0
    dashboard_data["total_missing_clauses"] = 0
    dashboard_data["contract_types"] = {}
    
    # Get PO count from cache
    try:
        po_matcher = get_po_matcher()
        dashboard_data["total_pos"] = po_matcher.get_po_count()
    except Exception as e:
        print(f"[DASHBOARD] Error getting PO count: {e}")
        dashboard_data["total_pos"] = 0
    
    if not extractions_store:
        print(f"[DASHBOARD] No extractions in store. Dashboard reset.")
        return
    
    total_risk = 0
    
    print(f"[DASHBOARD] Recalculating from {len(extractions_store)} extractions...")
    
    for extraction_id, extraction in extractions_store.items():
        dashboard_data["total_documents"] += 1
        
        # Get extracted_data which contains the actual document data
        extracted_data = extraction.get("extracted_data", {})
        
        # Also check results for document type (some extractions store it there)
        results_data = extraction.get("results", {})
        
        # Check if it's an invoice - look in multiple places
        doc_type = (
            extracted_data.get("document_type") or 
            results_data.get("contract_type") or
            extraction.get("document_type") or 
            extracted_data.get("contract_type") or 
            extraction.get("contract_type") or 
            "Unknown"
        )
        
        # Get status (could be "completed", "po_not_found", etc.)
        status = extraction.get("status", "")
        
        if doc_type and doc_type.upper() == "INVOICE":
            dashboard_data["total_invoices"] += 1
            
            # Check PO matching status - look in extracted_data first, then extraction, then results
            po_match = (
                extracted_data.get("_po_match") or 
                extraction.get("_po_match") or 
                results_data.get("_po_match") or 
                {}
            )
            
            # Determine if matched based on _po_match or status
            if po_match.get("matched") == True:
                dashboard_data["matched_invoices"] += 1
                print(f"   - {extraction.get('file_name', extraction_id)}: MATCHED")
            elif po_match.get("matched") == False or status == "po_not_found":
                # Explicitly marked as unmatched OR has po_not_found status
                dashboard_data["unmatched_invoices"] += 1
                print(f"   - {extraction.get('file_name', extraction_id)}: NOT MATCHED (status={status})")
            elif "_po_match" in extracted_data or "_po_match" in extraction:
                # Has _po_match but matched is not explicitly True, count as unmatched
                dashboard_data["unmatched_invoices"] += 1
                print(f"   - {extraction.get('file_name', extraction_id)}: NOT MATCHED (has _po_match)")
            else:
                # Legacy invoice (before PO matching feature) - count as matched
                dashboard_data["matched_invoices"] += 1
                print(f"   - {extraction.get('file_name', extraction_id)}: MATCHED (legacy)")
        
        # Sum up risk scores - check all places
        risk_score = (
            extracted_data.get("risk_score") or 
            results_data.get("risk_score") or
            extraction.get("risk_score", 0)
        )
        if isinstance(risk_score, dict):
            risk_score = risk_score.get("score", 0)
        if risk_score:
            total_risk += risk_score
        
        # Count missing clauses - check all places
        missing = (
            extracted_data.get("missing_clauses") or 
            results_data.get("missing_clauses") or
            extraction.get("missing_clauses", [])
        )
        if missing:
            dashboard_data["total_missing_clauses"] += len(missing)
        
        # Count contract types
        if doc_type:
            if doc_type in dashboard_data["contract_types"]:
                dashboard_data["contract_types"][doc_type] += 1
            else:
                dashboard_data["contract_types"][doc_type] = 1
    
    # Calculate average risk score
    if dashboard_data["total_documents"] > 0:
        dashboard_data["average_risk_score"] = int(total_risk / dashboard_data["total_documents"])
    
    print(f"[DASHBOARD] Updated: {dashboard_data['total_invoices']} invoices, {dashboard_data['total_pos']} POs, {dashboard_data['matched_invoices']} matched, {dashboard_data['unmatched_invoices']} unmatched")


def load_extractions_from_file():
    """Load extractions from GCS (if available) or JSON file on server startup."""
    global extractions_store
    try:
        # Try loading from cache manager (supports GCS)
        cache_manager = get_cache_manager()
        gcs_data = cache_manager.load_extractions_data()
        
        if gcs_data:
            # GCS data is a list of extractions, convert to dict
            if isinstance(gcs_data, list):
                extractions_store = {}
                for i, item in enumerate(gcs_data):
                    ext_id = item.get("extraction_id", str(i))
                    extractions_store[ext_id] = item
                    print(f"   - Loaded: {item.get('file_name', 'Unknown')} (ID: {ext_id}, Status: {item.get('status', 'unknown')})")
            elif isinstance(gcs_data, dict) and "extractions" in gcs_data:
                extractions_store = gcs_data.get("extractions", {})
                for ext_id, item in extractions_store.items():
                    print(f"   - Loaded: {item.get('file_name', 'Unknown')} (ID: {ext_id}, Status: {item.get('status', 'unknown')})")
            else:
                extractions_store = gcs_data if isinstance(gcs_data, dict) else {}
            print(f"[STARTUP] Loaded {len(extractions_store)} extractions from cache (GCS/local)")
            # Recalculate dashboard from loaded extractions
            recalculate_dashboard_from_extractions()
            return
        
        # Fallback to local file
        if EXTRACTIONS_JSON_FILE.exists():
            with open(EXTRACTIONS_JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                extractions_store = data.get("extractions", {})
                print(f"[STARTUP] Loaded {len(extractions_store)} extractions from {EXTRACTIONS_JSON_FILE.name}")
                # Recalculate dashboard from loaded extractions
                recalculate_dashboard_from_extractions()
        else:
            print(f"[STARTUP] No existing extractions file found. Starting fresh.")
            extractions_store = {}
    except Exception as e:
        print(f"[STARTUP] Error loading extractions: {e}")
        extractions_store = {}


def save_extractions_to_file():
    """Save extractions to GCS (if available) and JSON file for persistence."""
    try:
        data = {
            "last_updated": datetime.now().isoformat(),
            "total_extractions": len(extractions_store),
            "extractions": extractions_store
        }
        
        # Save to local file (legacy format for backward compatibility)
        with open(EXTRACTIONS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"[SAVE] Extractions saved to {EXTRACTIONS_JSON_FILE.name}")
        
        # Save each extraction as individual file (new approach)
        try:
            cache_manager = get_cache_manager()
            for extraction_id, extraction_data in extractions_store.items():
                cache_manager.save_extraction_record(extraction_id, extraction_data)
        except Exception as gcs_error:
            print(f"[SAVE] Note: Individual file save skipped or failed: {gcs_error}")
            
    except Exception as e:
        print(f"[ERROR] Failed to save extractions: {e}")


# Alias for compatibility
def save_extractions_to_json():
    """Alias for save_extractions_to_file()."""
    save_extractions_to_file()


# Load extractions on module import (server startup)
load_extractions_from_file()


class TextExtractionRequest(BaseModel):
    """Request model for text extraction."""
    text: str
    use_semantic_search: bool = True


class ExtractionResponse(BaseModel):
    """Response model for extraction results."""
    success: bool
    extracted_data: dict
    metadata: dict
    message: str = ""


# ============== HTML Page Routes ==============

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main index page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Index page not found")


@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve the dashboard page."""
    dashboard_path = STATIC_DIR / "dashboard.html"
    if dashboard_path.exists():
        return HTMLResponse(content=dashboard_path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Dashboard page not found")


@app.get("/selected-factors", response_class=HTMLResponse)
async def serve_selected_factors():
    """Serve the selected factors page."""
    factors_path = STATIC_DIR / "selected_factors.html"
    if factors_path.exists():
        return HTMLResponse(content=factors_path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Selected factors page not found")


@app.get("/excel-table", response_class=HTMLResponse)
async def serve_excel_table():
    """Serve the Excel data table page."""
    excel_table_path = STATIC_DIR / "excel_table.html"
    if excel_table_path.exists():
        return HTMLResponse(content=excel_table_path.read_text(encoding="utf-8"))
    raise HTTPException(status_code=404, detail="Excel table page not found")


# ============== API Routes ==============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    api_key = os.getenv('OPENAI_API_KEY')
    return {
        "status": "healthy",
        "api_key_configured": bool(api_key)
    }


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file for extraction.
    Returns an extraction_id for tracking.
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: .pdf, .docx, .doc, .txt"
        )
    
    try:
        # Generate extraction ID
        extraction_id = str(uuid.uuid4())
        
        print("\n" + "="*80)
        print(f"[UPLOAD] FILE UPLOAD INITIATED")
        print("="*80)
        print(f"  File Name: {file.filename}")
        print(f"  File Type: {file_ext}")
        print(f"  Extraction ID: {extraction_id}")
        
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            file_size = len(content)
            temp_file.write(content)
            temp_path = temp_file.name
        
        print(f"  File Size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
        print(f"  Temp Path: {temp_path}")
        
        # Compute file hash for caching
        cache_manager = get_cache_manager()
        file_hash = cache_manager.compute_content_hash(content)
        print(f"  File Hash: {file_hash[:16]}...")
        
        # Store file info with hash
        extractions_store[extraction_id] = {
            "file_path": temp_path,
            "file_name": file.filename,
            "file_hash": file_hash,  # Store hash for cache lookup
            "status": "uploaded",
            "results": None,
            "uploaded_at": datetime.now().isoformat(),
            "extracted_at": None
        }
        
        # Initialize status tracking
        extraction_status[extraction_id] = {
            "current_step": "uploaded",
            "step_description": "File uploaded successfully",
            "progress_percent": 0
        }
        
        print(f"[SUCCESS] Upload completed successfully!")
        print("="*80 + "\n")
        
        return {
            "extraction_id": extraction_id,
            "file_name": file.filename,
            "status": "uploaded",
            "vector_store": {"created": False}
        }
        
    except Exception as e:
        print(f"\n" + "="*80)
        print(f"[ERROR] UPLOAD FAILED!")
        print("="*80)
        print(f"  File: {file.filename if file else 'Unknown'}")
        print(f"  Error: {str(e)}")
        print("="*80 + "\n")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/extract/{extraction_id}")
async def extract_document(extraction_id: str):
    """
    Extract information from an uploaded document.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    if extraction_id not in extractions_store:
        raise HTTPException(status_code=404, detail="Extraction ID not found")
    
    extraction = extractions_store[extraction_id]
    
    if extraction["status"] == "completed" and extraction["results"]:
        return {"results": extraction["results"]}
    
    try:
        # Initialize status tracking (but don't set extraction_started yet - wait for cache check)
        extraction["status"] = "processing"
        
        print("\n" + "="*80)
        print(f"[EXTRACT] STARTING EXTRACTION PROCESS")
        print("="*80)
        print(f"  Extraction ID: {extraction_id}")
        print(f"  Document: {extraction['file_name']}")
        
        file_path = extraction["file_path"]
        file_hash = extraction.get("file_hash")
        file_ext = Path(file_path).suffix.lower()
        
        # Check cache before processing
        cache_manager = get_cache_manager()
        cached_result = None
        
        if file_hash:
            # Check cache silently (no progress bar needed - it's instant)
            print(f"\n[STEP 0] Checking extraction cache...")
            cached_result = cache_manager.load_extraction_cache(file_hash)
            if cached_result:
                print(f"   [CACHE HIT] Found cached extraction results!")
                print(f"   - Cached at: {cached_result.get('cached_at', 'Unknown')}")
                
                # Use cached data
                extracted_data = cached_result.get("extracted_data", {})
                metadata = cached_result.get("metadata", {})
                document_text = cached_result.get("document_text", "")
                
                # ============== DUPLICATE INVOICE ID CHECK (FOR INVOICES ONLY) ==============
                doc_type = extracted_data.get("document_type", "UNKNOWN")
                
                if doc_type == "INVOICE":
                    # Extract invoice ID from document_ids (including quotation_number)
                    doc_ids = extracted_data.get("document_ids", {})
                    invoice_id = doc_ids.get("invoice_id") or doc_ids.get("invoice_number") or doc_ids.get("quotation_number") or ""
                    
                    if invoice_id and invoice_id.strip():
                        print(f"\n[DUPLICATE CHECK] Checking for duplicate invoice ID: {invoice_id}")
                        
                        # Check if this invoice ID already exists
                        duplicate = check_duplicate_invoice_id(invoice_id, extraction_id)
                        
                        if duplicate:
                            # Duplicate found! Don't save, return warning
                            print(f"   [DUPLICATE FOUND] Invoice ID '{invoice_id}' already exists!")
                            print(f"   - Existing file: {duplicate['file_name']}")
                            print(f"   - Processed on: {duplicate['extracted_at']}")
                            print(f"   [ACTION] Blocking save - returning warning to user")
                            
                            # Update extraction status to show duplicate - skip progress bar
                            extraction["status"] = "duplicate"
                            extraction_status[extraction_id] = {
                                "current_step": "duplicate",
                                "step_description": "Duplicate invoice detected",
                                "progress_percent": 100,
                                "skip_progress": True,
                                "is_duplicate": True,
                                "is_complete": True,
                                "duplicate_info": {
                                    "invoice_id": invoice_id,
                                    "existing_file": duplicate['file_name'],
                                    "processed_date": duplicate['extracted_at']
                                }
                            }
                            
                            # Clean up temp file if exists
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            
                            # Return warning response (DON'T SAVE TO DATABASE)
                            return {
                                "status": "duplicate_invoice",
                                "success": False,
                                "warning": True,
                                "message": f"⚠️ Invoice ID '{invoice_id}' already exists in the system.",
                                "details": {
                                    "invoice_id": invoice_id,
                                    "existing_document": duplicate["file_name"],
                                    "processed_date": duplicate["extracted_at"],
                                    "extraction_id": duplicate["extraction_id"],
                                    "vendor": duplicate.get("vendor", ""),
                                    "amount": duplicate.get("amount", ""),
                                    "currency": duplicate.get("currency", "")
                                },
                                "suggestion": "This invoice was previously processed. Please verify if you uploaded the correct document."
                            }
                        else:
                            print(f"   [OK] Invoice ID is unique, proceeding with save")
                    else:
                        print(f"   [WARNING] No invoice ID found in extracted data, skipping duplicate check")
                # ============== END DUPLICATE CHECK ==============
                
                # ============== PO MATCHING CHECK (FOR INVOICES FROM CACHE) ==============
                if doc_type == "INVOICE":
                    print(f"\n[PO CHECK] Checking PO matching for cached invoice...")
                    
                    # Match invoice with PO
                    po_matched, po_data, po_message = match_invoice(extracted_data)
                    
                    if not po_matched:
                        # No matching PO found! Don't save to Excel, but store for dashboard tracking
                        print(f"   [PO NOT FOUND] {po_message}")
                        print(f"   [ACTION] Storing extraction for dashboard (NOT saving to Excel)")
                        
                        # Mark as unmatched
                        extracted_data["_po_match"] = {
                            "matched": False,
                            "po_number": "",
                            "po_filename": "",
                            "match_message": po_message
                        }
                        
                        # Store in extraction store for dashboard tracking
                        extraction["extracted_data"] = extracted_data
                        extraction["metadata"] = metadata
                        extraction["status"] = "po_not_found"
                        
                        # Transform to frontend format
                        results = transform_to_frontend_format(extracted_data, metadata)
                        extraction["results"] = results
                        extraction["extracted_at"] = datetime.now().isoformat()
                        
                        # Update extraction status
                        extraction_status[extraction_id] = {
                            "current_step": "po_not_found",
                            "step_description": "No matching Purchase Order found",
                            "progress_percent": 100,
                            "skip_progress": True,
                            "is_po_missing": True,
                            "is_complete": True,
                            "po_message": po_message
                        }
                        
                        # Update dashboard for unmatched invoice
                        update_dashboard(results, po_matched=False)
                        
                        # Save to extraction cache (so re-upload loads from cache)
                        file_hash = extraction.get("file_hash")
                        if file_hash:
                            document_text = metadata.get("document_text", "")
                            cache_manager.save_extraction_cache(file_hash, extracted_data, metadata, document_text)
                            print(f"   [OK] Saved unmatched invoice to extraction cache for future use")
                        
                        # Save to file for persistence (so dashboard survives restart)
                        save_extractions_to_file()
                        
                        # Clean up temp file if exists
                        if os.path.exists(file_path):
                            os.remove(file_path)
                        
                        # Return warning response (DON'T SAVE TO EXCEL, but show in dashboard)
                        return {
                            "status": "po_not_found",
                            "success": False,
                            "warning": True,
                            "message": f"⚠️ {po_message}",
                            "details": {
                                "invoice_file": extraction["file_name"],
                                "po_number_in_invoice": extracted_data.get("document_ids", {}).get("po_number", ""),
                                "vendor": extracted_data.get("party_names", {}).get("vendor", ""),
                                "customer": extracted_data.get("party_names", {}).get("customer", ""),
                                "amount": extracted_data.get("amount", "")
                            },
                            "suggestion": "Please upload the corresponding Purchase Order first, then re-upload this invoice.",
                            "extracted_data": extracted_data,
                            "results": results  # Include results for dashboard display
                        }
                    else:
                        print(f"   [OK] PO matched: {po_message}")
                        # Store PO matching info in extracted data for Excel export
                        extracted_data["_po_match"] = {
                            "matched": True,
                            "po_number": po_data.get("po_number", "") if po_data else "",
                            "po_filename": po_data.get("filename", "") if po_data else "",
                            "match_message": po_message
                        }
                # ============== END PO MATCHING CHECK ==============
                
                # Store in extraction store
                extraction["extracted_data"] = extracted_data
                extraction["metadata"] = metadata
                
                # Transform to frontend format
                results = transform_to_frontend_format(extracted_data, metadata)
                
                # Update store
                extraction["status"] = "completed"
                extraction["results"] = results
                extraction["extracted_at"] = datetime.now().isoformat()
                
                # Update status for cache hit - skip progress bar
                extraction_status[extraction_id] = {
                    "current_step": "completed",
                    "step_description": "Retrieved from cache",
                    "progress_percent": 100,
                    "skip_progress": True,
                    "from_cache": True,
                    "is_complete": True
                }
                
                # Update dashboard
                update_dashboard(results)
                
                # Save to Excel
                try:
                    excel_path = Path(__file__).parent / "contract_extractions.xlsx"
                    update_contract_excel(
                        extracted_data=extracted_data,
                        file_name=extraction["file_name"],
                        excel_file_path=str(excel_path)
                    )
                except Exception as e:
                    print(f"   [WARNING] Excel export failed - {e}")
                
                # Save extractions to JSON
                save_extractions_to_file()
                
                print(f"\n" + "="*80)
                print(f"[SUCCESS] EXTRACTION COMPLETED FROM CACHE!")
                print(f"="*80)
                print(f"  Summary:")
                print(f"   - Document: {extraction['file_name']}")
                print(f"   - Type: {extracted_data.get('document_type', 'UNKNOWN')}")
                print(f"   - Status: Completed (from cache)")
                print(f"   - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*80 + "\n")
                
                return {"results": results}
            else:
                print(f"   [CACHE MISS] No cached results found, proceeding with extraction...")
        
        # If no cache, proceed with normal extraction
        # NOW set extraction_started status (after confirming it's not cache/duplicate)
        extraction_status[extraction_id] = {
            "current_step": "extraction_started",
            "step_description": "EXTRACTION PROCESS STARTED",
            "progress_percent": 15,
            "skip_progress": False,  # Explicitly show progress bar
            "is_complete": False
        }
        time.sleep(0.5)  # Give frontend time to capture this status (matches 500ms polling interval)
        
        # Convert DOCX to PDF with page numbers if needed
        if should_convert_to_pdf(file_path):
            print(f"\n[STEP 1] Converting DOCX to PDF with page numbers...")
            print(f"   - Source: {Path(file_path).name}")
            
            pdf_path = convert_docx_to_pdf(file_path)
            
            # Update file path to PDF if conversion succeeded
            if pdf_path != file_path and os.path.exists(pdf_path):
                # Clean up original DOCX
                if os.path.exists(file_path):
                    os.remove(file_path)
                file_path = pdf_path
                extraction["file_path"] = pdf_path
                print(f"   [OK] Conversion successful: {Path(pdf_path).name}")
        else:
            print(f"\n[STEP 1] Document is already in {file_ext.upper()} format, no conversion needed")
        
        # Initialize orchestrator (reuse singleton instance to avoid creating multiple OpenAI clients)
        print(f"\n[STEP 2] Initializing Extraction Orchestrator...")
        print(f"   - OpenAI API: Configured")
        print(f"   - GCS Vision: Enabled")
        print(f"   - Semantic Search: Enabled")
        
        if get_orchestrator:
            # Use singleton pattern to reuse orchestrator instance
            orchestrator = get_orchestrator(
                api_key=api_key,
                use_gcs_vision=True,  # Vision API enabled for OCR on image-based PDFs
                use_semantic_search=True
            )
        else:
            # Fallback for LangGraph agent
            orchestrator = ExtractionOrchestrator(
                api_key=api_key,
                use_gcs_vision=True,
                use_semantic_search=True
            )
        print(f"   [OK] Orchestrator initialized (reusing instance)")
        
        print(f"\n[STEP 3] Extracting data from document...")
        # Run extraction in a thread so server can respond to status polling requests
        extracted_data, metadata = await asyncio.to_thread(
            orchestrator.extract_from_file, 
            file_path, 
            use_ocr=False, 
            extraction_id=extraction_id
        )
        
        # Check if OCR was actually used (from metadata)
        if metadata.get("extraction_method") == "vision_api" or metadata.get("used_ocr"):
            print(f"   [OCR] Document processed with OCR (scanned PDF detected)")
        
        doc_type = extracted_data.get("document_type", "UNKNOWN")
        print(f"   [OK] Extraction completed!")
        print(f"   - Document Type: {doc_type}")
        print(f"   - Fields Extracted: {len(extracted_data)} fields")
        
        # ============== DUPLICATE INVOICE ID CHECK (FOR INVOICES ONLY) ==============
        if doc_type == "INVOICE":
            # Extract invoice ID from document_ids (including quotation_number)
            doc_ids = extracted_data.get("document_ids", {})
            invoice_id = doc_ids.get("invoice_id") or doc_ids.get("invoice_number") or doc_ids.get("quotation_number") or ""
            
            if invoice_id and invoice_id.strip():
                print(f"\n[STEP 3.5] Checking for duplicate invoice ID: {invoice_id}")
                
                # Check if this invoice ID already exists
                duplicate = check_duplicate_invoice_id(invoice_id, extraction_id)
                
                if duplicate:
                    # Duplicate found! Don't save, return warning
                    print(f"   [DUPLICATE FOUND] Invoice ID '{invoice_id}' already exists!")
                    print(f"   - Existing file: {duplicate['file_name']}")
                    print(f"   - Processed on: {duplicate['extracted_at']}")
                    print(f"   [ACTION] Blocking save - returning warning to user")
                    
                    # Update extraction status to show duplicate - skip progress bar
                    extraction["status"] = "duplicate"
                    extraction_status[extraction_id] = {
                        "current_step": "duplicate",
                        "step_description": "Duplicate invoice detected",
                        "progress_percent": 100,
                        "skip_progress": True,
                        "is_duplicate": True,
                        "is_complete": True,
                        "duplicate_info": {
                            "invoice_id": invoice_id,
                            "existing_file": duplicate['file_name'],
                            "processed_date": duplicate['extracted_at']
                        }
                    }
                    
                    # Clean up temp file
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    print(f"\n" + "="*80)
                    print(f"[DUPLICATE] INVOICE ALREADY EXISTS - EXTRACTION BLOCKED")
                    print(f"="*80)
                    print(f"  Invoice ID: {invoice_id}")
                    print(f"  New Document: {extraction['file_name']}")
                    print(f"  Existing Document: {duplicate['file_name']}")
                    print(f"  Processed Date: {duplicate['extracted_at']}")
                    print("="*80 + "\n")
                    
                    # Return warning response (DON'T SAVE TO DATABASE)
                    return {
                        "status": "duplicate_invoice",
                        "success": False,
                        "warning": True,
                        "message": f"⚠️ Invoice ID '{invoice_id}' already exists in the system.",
                        "details": {
                            "invoice_id": invoice_id,
                            "existing_document": duplicate["file_name"],
                            "processed_date": duplicate["extracted_at"],
                            "extraction_id": duplicate["extraction_id"],
                            "vendor": duplicate.get("vendor", ""),
                            "amount": duplicate.get("amount", ""),
                            "currency": duplicate.get("currency", "")
                        },
                        "suggestion": "This invoice was previously processed. Please verify if you uploaded the correct document."
                    }
                else:
                    print(f"   [OK] Invoice ID is unique, proceeding with save")
            else:
                print(f"   [WARNING] No invoice ID found in extracted data, skipping duplicate check")
        # ============== END DUPLICATE CHECK ==============
        
        # ============== PO MATCHING CHECK (FOR INVOICES ONLY) ==============
        if doc_type == "INVOICE":
            print(f"\n[STEP 3.6] Checking PO matching for invoice...")
            
            # Match invoice with PO
            po_matched, po_data, po_message = match_invoice(extracted_data)
            
            if not po_matched:
                # No matching PO found! Don't save to Excel, but store for dashboard tracking
                print(f"   [PO NOT FOUND] {po_message}")
                print(f"   [ACTION] Storing extraction for dashboard (NOT saving to Excel)")
                
                # Mark as unmatched
                extracted_data["_po_match"] = {
                    "matched": False,
                    "po_number": "",
                    "po_filename": "",
                    "match_message": po_message
                }
                
                # Store in extraction store for dashboard tracking
                extraction["extracted_data"] = extracted_data
                extraction["metadata"] = metadata
                extraction["status"] = "po_not_found"
                
                # Transform to frontend format
                results = transform_to_frontend_format(extracted_data, metadata)
                extraction["results"] = results
                extraction["extracted_at"] = datetime.now().isoformat()
                
                # Update extraction status
                extraction_status[extraction_id] = {
                    "current_step": "po_not_found",
                    "step_description": "No matching Purchase Order found",
                    "progress_percent": 100,
                    "skip_progress": True,
                    "is_po_missing": True,
                    "is_complete": True,
                    "po_message": po_message
                }
                
                # Update dashboard for unmatched invoice
                update_dashboard(results, po_matched=False)
                
                # Save to extraction cache (so re-upload loads from cache and chatbot can use it)
                file_hash = extraction.get("file_hash")
                if file_hash:
                    document_text = metadata.get("document_text", "")
                    cache_manager.save_extraction_cache(file_hash, extracted_data, metadata, document_text)
                    print(f"   [OK] Saved unmatched invoice to extraction cache")
                
                # Save to file for persistence (so dashboard survives restart)
                save_extractions_to_file()
                
                # Clean up temp file
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                print(f"\n" + "="*80)
                print(f"[PO NOT FOUND] NO MATCHING PURCHASE ORDER - STORED FOR DASHBOARD")
                print(f"="*80)
                print(f"  Invoice Document: {extraction['file_name']}")
                print(f"  Message: {po_message}")
                print(f"  Dashboard: Counted as unmatched invoice")
                print(f"  Cached: Yes (for future re-uploads and chatbot)")
                print(f"  Suggestion: Please upload the corresponding Purchase Order first")
                print("="*80 + "\n")
                
                # Return warning response (DON'T SAVE TO EXCEL, but show in dashboard)
                return {
                    "status": "po_not_found",
                    "success": False,
                    "warning": True,
                    "message": f"⚠️ {po_message}",
                    "details": {
                        "invoice_file": extraction["file_name"],
                        "po_number_in_invoice": extracted_data.get("document_ids", {}).get("po_number", ""),
                        "vendor": extracted_data.get("party_names", {}).get("vendor", ""),
                        "customer": extracted_data.get("party_names", {}).get("customer", ""),
                        "amount": extracted_data.get("amount", "")
                    },
                    "suggestion": "Please upload the corresponding Purchase Order first, then re-upload this invoice.",
                    "extracted_data": extracted_data,
                    "results": results  # Include results for dashboard display
                }
            else:
                print(f"   [OK] PO matched: {po_message}")
                # Store PO matching info in extracted data for Excel export
                extracted_data["_po_match"] = {
                    "matched": True,
                    "po_number": po_data.get("po_number", "") if po_data else "",
                    "po_filename": po_data.get("filename", "") if po_data else "",
                    "match_message": po_message
                }
        # ============== END PO MATCHING CHECK ==============
        
        # Get document text from metadata for caching
        document_text = metadata.get("document_text", "")
        
        # Save to cache for future use
        if file_hash:
            print(f"\n[STEP 4] Saving extraction results to cache...")
            cache_manager.save_extraction_cache(file_hash, extracted_data, metadata, document_text)
            print(f"   [OK] Results cached for future use")
        
        # Store extracted data with metadata for selected factors page
        extraction["extracted_data"] = extracted_data
        extraction["metadata"] = metadata
        
        print(f"\n[STEP 5] Transforming data for frontend...")
        results = transform_to_frontend_format(extracted_data, metadata)
        print(f"   [OK] Data transformation completed")
        
        # Add quality warnings if available
        if metadata.get("quality_warning"):
            results["quality_warning"] = metadata["quality_warning"]
            results["image_quality"] = metadata.get("image_quality", {})
            print(f"   [WARNING] Quality warning added: {metadata['quality_warning']}")
        
        # Update store
        extraction["status"] = "completed"
        extraction["results"] = results
        extraction["extracted_at"] = datetime.now().isoformat()
        
        # Final status update
        extraction_status[extraction_id] = {
            "current_step": "completed",
            "step_description": "Extraction completed",
            "progress_percent": 100
        }
        
        # Update dashboard data
        print(f"\n[STEP 6] Updating dashboard statistics...")
        update_dashboard(results)
        print(f"   [OK] Dashboard updated")
        
        # Save to Excel file
        print(f"\n[STEP 7] Saving to Excel file...")
        try:
            excel_path = Path(__file__).parent / "contract_extractions.xlsx"
            print(f"   - File: {excel_path.name}")
            print(f"   - Document: {extraction['file_name']}")
            
            success = update_contract_excel(
                extracted_data=extracted_data,
                file_name=extraction["file_name"],
                excel_file_path=str(excel_path)
            )
            if success:
                print(f"   [OK] Data saved to Excel successfully")
            else:
                print("   [WARNING] Failed to save data to Excel")
        except Exception as e:
            print(f"   [ERROR] Excel export failed - {e}")
        
        # Clean up temp file
        print(f"\n[STEP 8] Cleaning up temporary files...")
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"   [OK] Temporary files removed")
        
        # Save extractions to JSON file for persistence
        save_extractions_to_file()
        
        print(f"\n" + "="*80)
        print(f"[SUCCESS] EXTRACTION COMPLETED SUCCESSFULLY!")
        print(f"="*80)
        print(f"  Summary:")
        print(f"   - Document: {extraction['file_name']}")
        print(f"   - Type: {doc_type}")
        print(f"   - Status: Completed")
        print(f"   - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80 + "\n")
        
        return {"results": results}
        
    except Exception as e:
        extraction["status"] = "failed"
        print(f"\n" + "="*80)
        print(f"[ERROR] EXTRACTION FAILED!")
        print("="*80)
        print(f"  Extraction ID: {extraction_id}")
        print(f"  Document: {extraction.get('file_name', 'Unknown')}")
        print(f"  Error: {str(e)}")
        print("="*80 + "\n")
        
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboard")
async def get_dashboard():
    """Get dashboard statistics with fresh PO count."""
    # Always get fresh PO count
    try:
        po_matcher = get_po_matcher()
        dashboard_data["total_pos"] = po_matcher.get_po_count()
    except Exception as e:
        print(f"[DASHBOARD] Error getting PO count: {e}")
    
    return dashboard_data


@app.get("/api/json-data")
async def get_json_data():
    """Get all extracted JSON data for dashboard."""
    extractions = []
    
    for extraction_id, extraction in extractions_store.items():
        if extraction.get("status") == "completed" and extraction.get("results"):
            # Use the original extracted_data which contains references
            data = extraction.get("extracted_data", extraction.get("results", {}))
            
            extractions.append({
                "extraction_id": extraction_id,
                "file_name": extraction.get("file_name", "Unknown"),
                "uploaded_at": extraction.get("uploaded_at", ""),
                "extracted_at": extraction.get("extracted_at", ""),
                "data": data
            })
    
    # Sort by extracted_at (newest first)
    extractions.sort(key=lambda x: x.get("extracted_at", ""), reverse=True)
    
    return {"extractions": extractions}


@app.get("/api/extractions-list")
async def get_extractions_list():
    """Get list of all extracted documents from memory and cache."""
    try:
        extractions_list = []
        seen_ids = set()
        
        # Valid statuses for showing in dropdown (completed or po_not_found)
        valid_statuses = ["completed", "po_not_found"]
        
        # First, add from in-memory store
        for extraction_id, extraction in extractions_store.items():
            status = extraction.get("status", "")
            if status in valid_statuses and extraction.get("results"):
                seen_ids.add(extraction_id)
                # Get extracted_at, fall back to uploaded_at or file modification info
                extracted_at = extraction.get("extracted_at") or extraction.get("uploaded_at") or ""
                # Add status indicator to document type for unmatched invoices
                doc_type = extraction.get("results", {}).get("contract_type", "Unknown")
                if status == "po_not_found":
                    doc_type = f"{doc_type} ⚠️"  # Add warning indicator
                extractions_list.append({
                    "extraction_id": extraction_id,
                    "file_name": extraction.get("file_name", "Unknown"),
                    "extracted_at": extracted_at,
                    "document_type": doc_type,
                    "status": status
                })
        
        # Also check cache manager for any extractions not in memory
        try:
            cache_manager = get_cache_manager()
            cached_records = cache_manager.list_extraction_records()
            
            for record in cached_records:
                extraction_id = record.get("extraction_id")
                if extraction_id and extraction_id not in seen_ids:
                    status = record.get("status", "")
                    # Include both completed and po_not_found
                    if status in valid_statuses:
                        seen_ids.add(extraction_id)
                        extracted_at = record.get("extracted_at") or record.get("uploaded_at") or record.get("modified", "")
                        doc_type = record.get("document_type", "Unknown")
                        if status == "po_not_found":
                            doc_type = f"{doc_type} ⚠️"  # Add warning indicator
                        extractions_list.append({
                            "extraction_id": extraction_id,
                            "file_name": record.get("file_name", "Unknown"),
                            "extracted_at": extracted_at,
                            "document_type": doc_type,
                            "status": status
                        })
        except Exception as cache_error:
            print(f"[API] Note: Could not load from cache: {cache_error}")
        
        # Sort by extracted_at (newest first), with fallback for empty dates
        extractions_list.sort(key=lambda x: x.get("extracted_at", "") or "0", reverse=True)
        
        print(f"[API] Returning {len(extractions_list)} extractions for dropdown")
        return {"success": True, "extractions": extractions_list}
    except Exception as e:
        print(f"[API] Error in extractions-list: {e}")
        return {"success": False, "extractions": [], "message": str(e)}


@app.get("/api/extraction/{extraction_id}")
async def get_extraction_by_id(extraction_id: str):
    """Get extraction data by extraction ID from memory or cache."""
    extraction = None
    
    # First check in-memory store
    if extraction_id in extractions_store:
        extraction = extractions_store[extraction_id]
    else:
        # Try loading from cache
        try:
            cache_manager = get_cache_manager()
            cached_data = cache_manager.load_extraction_record(extraction_id)
            if cached_data:
                extraction = cached_data
                # Also add to memory store for future requests
                extractions_store[extraction_id] = extraction
                print(f"[API] Loaded extraction {extraction_id} from cache into memory")
        except Exception as e:
            print(f"[API] Error loading from cache: {e}")
    
    if not extraction:
        raise HTTPException(status_code=404, detail="Extraction not found")
    
    # Accept both "completed" and "po_not_found" status (both have valid results)
    valid_statuses = ["completed", "po_not_found"]
    status = extraction.get("status", "")
    
    if status not in valid_statuses or not extraction.get("results"):
        raise HTTPException(status_code=404, detail=f"Extraction not completed or no results available (status: {status})")
    
    return {
        "success": True,
        "extraction_id": extraction_id,
        "file_name": extraction.get("file_name", "Unknown"),
        "extracted_at": extraction.get("extracted_at") or extraction.get("uploaded_at", ""),
        "status": status,  # Include status so frontend knows if it's matched or not
        "results": extraction.get("results")
    }


@app.get("/api/extraction-status/{extraction_id}")
async def get_extraction_status(extraction_id: str):
    """Get current processing status for an extraction."""
    # Check if extraction exists
    if extraction_id not in extractions_store:
        # Return default status if not found (might be polling before upload completes)
        return {
            "extraction_id": extraction_id,
            "status": "not_found",
            "current_step": "waiting",
            "step_description": "Waiting for extraction to start...",
            "progress_percent": 0,
            "is_complete": False
        }
    
    extraction = extractions_store[extraction_id]
    status_info = extraction_status.get(extraction_id, {})
    
    # If status info is empty but extraction exists, provide default based on status
    if not status_info and extraction.get("status") == "uploaded":
        status_info = {
            "current_step": "uploaded",
            "step_description": "File uploaded, waiting to start extraction...",
            "progress_percent": 0,
            "skip_progress": False,  # Show progress bar for fresh uploads
            "is_complete": False
        }
    elif not status_info and extraction.get("status") == "completed":
        status_info = {
            "current_step": "completed",
            "step_description": "Extraction completed successfully!",
            "progress_percent": 100
        }
    elif not status_info:
        status_info = {
            "current_step": extraction.get("status", "unknown"),
            "step_description": f"Status: {extraction.get('status', 'unknown')}",
            "progress_percent": 0
        }
    
    return {
        "extraction_id": extraction_id,
        "status": extraction.get("status", "unknown"),
        "current_step": status_info.get("current_step", ""),
        "step_description": status_info.get("step_description", ""),
        "progress_percent": status_info.get("progress_percent", 0),
        "is_complete": extraction.get("status") == "completed"
    }


@app.get("/api/excel-data")
async def get_excel_data():
    """Get data from Excel file if it exists."""
    excel_path = Path(__file__).parent / "contract_extractions.xlsx"
    
    if not excel_path.exists():
        return {"success": False, "data": [], "message": "Excel file not found"}
    
    try:
        import pandas as pd
        df = pd.read_excel(excel_path)
        df = df.fillna("")
        
        # Convert datetime columns to string for JSON serialization
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str)
        
        # Convert to dict and ensure all values are JSON serializable
        data = df.to_dict(orient='records')
        
        # Clean up any NaT or NaN string representations
        for row in data:
            for key, value in row.items():
                if value == 'NaT' or value == 'nan':
                    row[key] = ""
        return {"success": True, "data": data}
    except ImportError:
        return {"success": False, "data": [], "message": "pandas not installed"}
    except Exception as e:
        return {"success": False, "data": [], "message": str(e)}


@app.get("/api/download-excel")
async def download_excel():
    """Download the Excel file."""
    excel_path = Path(__file__).parent / "contract_extractions.xlsx"
    
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")
    
    return FileResponse(
        path=excel_path,
        filename="contract_extractions.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# ============== Direct Extraction Endpoints ==============

@app.post("/extract/file", response_model=ExtractionResponse)
async def extract_from_file(
    file: UploadFile = File(...),
    use_ocr: bool = Form(False),
    use_semantic_search: bool = Form(True)
):
    """
    Extract contract data from an uploaded file (direct API).
    Uses caching to avoid re-processing the same files.
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf', '.docx', '.txt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: .pdf, .docx, .txt"
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Compute file hash for cache lookup
        cache_manager = get_cache_manager()
        file_hash = cache_manager.compute_content_hash(content)
        
        # Check cache first
        cached_result = cache_manager.load_extraction_cache(file_hash)
        if cached_result:
            print(f"[CACHE] Using cached extraction results for {file.filename}")
            extracted_data = cached_result.get("extracted_data", {})
            metadata = cached_result.get("metadata", {})
            
            # Remove large fields from metadata for response
            if "document_text" in metadata:
                del metadata["document_text"]
            if "page_map" in metadata:
                del metadata["page_map"]
            
            return ExtractionResponse(
                success=True,
                extracted_data=extracted_data,
                metadata=metadata,
                message=f"Successfully extracted data from {file.filename} (from cache)"
            )
        
        # If not in cache, save to temp file and process
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Use singleton pattern to reuse orchestrator instance
            if get_orchestrator:
                orchestrator = get_orchestrator(
                    api_key=api_key,
                    use_gcs_vision=True,  # Vision API enabled for OCR on image-based PDFs
                    use_semantic_search=use_semantic_search
                )
            else:
                orchestrator = ExtractionOrchestrator(
                    api_key=api_key,
                    use_gcs_vision=True,
                    use_semantic_search=use_semantic_search
                )
            
            extracted_data, metadata = orchestrator.extract_from_file(temp_path, use_ocr=use_ocr, extraction_id=None)
            
            # Save to cache for future use
            document_text = metadata.get("document_text", "")
            cache_manager.save_extraction_cache(file_hash, extracted_data, metadata, document_text)
            print(f"[CACHE] Saved extraction results to cache")
            
            if "document_text" in metadata:
                del metadata["document_text"]
            if "page_map" in metadata:
                del metadata["page_map"]
            
            return ExtractionResponse(
                success=True,
                extracted_data=extracted_data,
                metadata=metadata,
                message=f"Successfully extracted data from {file.filename}"
            )
            
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extract/text", response_model=ExtractionResponse)
async def extract_from_text(request: TextExtractionRequest):
    """
    Extract contract data from raw text (direct API).
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    try:
        # Use singleton pattern to reuse orchestrator instance
        if get_orchestrator:
            orchestrator = get_orchestrator(
                api_key=api_key,
                use_gcs_vision=True,  # Vision API enabled for OCR on image-based PDFs
                use_semantic_search=request.use_semantic_search
            )
        else:
            orchestrator = ExtractionOrchestrator(
                api_key=api_key,
                use_gcs_vision=True,  # Vision API enabled for OCR on image-based PDFs
                use_semantic_search=request.use_semantic_search
            )
        
        extracted_data, metadata = orchestrator.extract_from_text(request.text)
        
        if "document_text" in metadata:
            del metadata["document_text"]
        if "page_map" in metadata:
            del metadata["page_map"]
        
        return ExtractionResponse(
            success=True,
            extracted_data=extracted_data,
            metadata=metadata,
            message="Successfully extracted data from text"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============== Helper Functions ==============

def check_duplicate_invoice_id(invoice_id: str, current_extraction_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Check if an invoice ID already exists in the database.
    
    Args:
        invoice_id: The invoice ID to check
        current_extraction_id: Current extraction ID to exclude from check (for updates)
        
    Returns:
        Dictionary with existing extraction info if duplicate found, None otherwise
    """
    if not invoice_id or not invoice_id.strip():
        return None
    
    # Normalize invoice ID for comparison (case-insensitive, trim whitespace)
    normalized_id = invoice_id.strip().lower()
    
    # Check in-memory store first (fast)
    for extraction_id, extraction in extractions_store.items():
        # Skip current extraction if provided
        if current_extraction_id and extraction_id == current_extraction_id:
            continue
        
        # Only check completed extractions
        if extraction.get("status") == "completed":
            extracted_data = extraction.get("extracted_data", {})
            
            # Only check INVOICE documents
            if extracted_data.get("document_type") == "INVOICE":
                doc_ids = extracted_data.get("document_ids", {})
                
                # Check both invoice_id and invoice_number fields
                existing_invoice_id = (
                    doc_ids.get("invoice_id") or 
                    doc_ids.get("invoice_number") or
                    ""
                )
                
                # Normalize existing ID for comparison
                if existing_invoice_id:
                    normalized_existing = existing_invoice_id.strip().lower()
                    
                    if normalized_existing == normalized_id:
                        # Found duplicate!
                        return {
                            "extraction_id": extraction_id,
                            "invoice_id": existing_invoice_id,
                            "file_name": extraction.get("file_name", "Unknown"),
                            "extracted_at": extraction.get("extracted_at", ""),
                            "vendor": extracted_data.get("party_names", {}).get("vendor", ""),
                            "amount": extracted_data.get("amount", ""),
                            "currency": extracted_data.get("currency", "")
                        }
    
    return None


def _is_bank_address(address: str) -> bool:
    """Check if an address is a bank address based on keywords."""
    if not address or not isinstance(address, str):
        return False
    address_lower = address.lower()
    bank_keywords = ['bank', 'branch', 'iban', 'swift', 'account no', 'account number', 'a/c no', 'bank a/c no', 'bank account']
    return any(keyword in address_lower for keyword in bank_keywords)


def _validate_tax_ids(tax_ids: dict) -> dict:
    """
    Validate tax IDs and remove invalid values (like company names).
    Returns cleaned tax_ids dict with only valid values.
    """
    if not tax_ids or not isinstance(tax_ids, dict):
        return {}
    
    validated = {}
    
    for key, value in tax_ids.items():
        if not value or not isinstance(value, str):
            validated[key] = ""
            continue
        
        value = value.strip()
        
        # PAN validation: exactly 10 chars, format AAAAA9999A (5 letters + 4 digits + 1 letter)
        if key == "pan":
            pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$'
            if re.match(pan_pattern, value.upper()):
                validated[key] = value.upper()
            else:
                print(f"   [VALIDATION] Invalid PAN '{value}' - doesn't match format AAAAA9999A, clearing")
                validated[key] = ""
            continue
        
        # GSTIN validation: 15 chars (2 digits + 10 char PAN + 1 digit + Z + 1 alphanumeric)
        if key == "gstin":
            gstin_pattern = r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z]$'
            if re.match(gstin_pattern, value.upper()):
                validated[key] = value.upper()
            else:
                # Also accept simpler 15-char alphanumeric GSTIN
                if len(value) == 15 and value.replace(" ", "").isalnum():
                    validated[key] = value.upper()
                else:
                    print(f"   [VALIDATION] Invalid GSTIN '{value}' - doesn't match expected format, clearing")
                    validated[key] = ""
            continue
        
        # VAT validation: starts with 2-letter country code followed by numbers/alphanumeric
        if key == "vat":
            # UAE TRN format: 15 digits starting with 100
            trn_pattern = r'^100[0-9]{12}$'
            # EU VAT format: 2 letters + numbers
            vat_pattern = r'^[A-Z]{2}[0-9A-Z]+$'
            if re.match(trn_pattern, value) or re.match(vat_pattern, value.upper()):
                validated[key] = value
            elif value.isdigit() and len(value) >= 8:
                # Accept numeric VAT/TRN numbers
                validated[key] = value
            else:
                print(f"   [VALIDATION] Invalid VAT '{value}' - doesn't match expected format, clearing")
                validated[key] = ""
            continue
        
        # EIN validation: format XX-XXXXXXX
        if key in ["ein", "tax_id"]:
            ein_pattern = r'^[0-9]{2}-[0-9]{7}$'
            if re.match(ein_pattern, value):
                validated[key] = value
            elif value.replace("-", "").isdigit() and len(value.replace("-", "")) >= 7:
                # Accept numeric tax IDs
                validated[key] = value
            else:
                # Check if it looks like a company name (has spaces and multiple words)
                if " " in value and len(value.split()) > 2:
                    print(f"   [VALIDATION] Invalid {key} '{value}' - looks like company name, clearing")
                    validated[key] = ""
                else:
                    validated[key] = value
            continue
        
        # For other fields, check if it looks like a company name
        if " " in value and len(value.split()) > 3:
            # Likely a company name - too many words
            print(f"   [VALIDATION] Invalid {key} '{value}' - looks like company name (too many words), clearing")
            validated[key] = ""
        elif len(value) > 50:
            # Too long for a tax ID
            print(f"   [VALIDATION] Invalid {key} '{value[:30]}...' - too long for tax ID, clearing")
            validated[key] = ""
        else:
            validated[key] = value
    
    return validated


def transform_to_frontend_format(extracted_data: dict, metadata: dict) -> dict:
    """Transform extracted data to frontend expected format."""
    # Get party names
    party_names = extracted_data.get("party_names", {})
    doc_type = extracted_data.get("document_type", "CONTRACT")
    
    # Filter out bank addresses from vendor/customer addresses
    vendor_address = party_names.get("vendor_address", "")
    customer_address = party_names.get("customer_address", "")
    
    # If vendor_address contains bank keywords, it's likely a bank address - clear it
    if vendor_address and _is_bank_address(vendor_address):
        print(f"   [WARNING] Vendor address contains bank keywords, clearing: {vendor_address[:50]}...")
        vendor_address = ""
    
    # If customer_address contains bank keywords, it's likely a bank address - clear it
    if customer_address and _is_bank_address(customer_address):
        print(f"   [WARNING] Customer address contains bank keywords, clearing: {customer_address[:50]}...")
        customer_address = ""
    
    # Get risk score
    risk_score_data = extracted_data.get("risk_score", {})
    risk_score = risk_score_data.get("score", 0) if isinstance(risk_score_data, dict) else 0
    
    # Handle party names for both contracts and invoices
    party_1_name = party_names.get("party_1", "")
    party_2_name = party_names.get("party_2", "")
    
    # Determine which party is customer/vendor
    # Check if we have explicit customer/vendor information
    vendor_name = party_names.get("vendor", "")
    customer_name = party_names.get("customer", "")
    
    # For invoices, use vendor/customer if party_1/party_2 not set
    if doc_type == "INVOICE":
        if not party_1_name and vendor_name:
            party_1_name = vendor_name
        if not party_2_name and customer_name:
            party_2_name = customer_name
    
    # Determine party types based on customer/vendor mapping
    # Default: party_1 is vendor (address comes from vendor_address), party_2 is customer (address comes from customer_address)
    party_1_type = "Vendor"
    party_2_type = "Customer"
    
    # Check if customer name matches either party to determine types
    if customer_name:
        # Normalize names for comparison
        customer_name_normalized = customer_name.lower().strip()
        party_1_name_normalized = party_1_name.lower().strip() if party_1_name else ""
        party_2_name_normalized = party_2_name.lower().strip() if party_2_name else ""
        
        # If customer name matches party_1, then party_1 is customer and party_2 is vendor
        if party_1_name_normalized and customer_name_normalized == party_1_name_normalized:
            party_1_type = "Customer"
            party_2_type = "Vendor"
        # If customer name matches party_2, then party_2 is customer and party_1 is vendor (default case)
        elif party_2_name_normalized and customer_name_normalized == party_2_name_normalized:
            party_2_type = "Customer"
            party_1_type = "Vendor"
        # If customer_name exists but doesn't match either, check address mapping
        # party_2_address comes from customer_address, so party_2 is customer
        else:
            party_2_type = "Customer"
            party_1_type = "Vendor"
    
    # Get document IDs
    doc_ids = extracted_data.get("document_ids", {})
    invoice_id = doc_ids.get("invoice_id") or doc_ids.get("invoice_number") or doc_ids.get("quotation_number") or ""
    
    # Get primary document ID (try multiple fields, including quotation_number)
    document_id = (
        doc_ids.get("invoice_id") or 
        doc_ids.get("invoice_number") or 
        doc_ids.get("quotation_number") or  # Quote number can be invoice number
        doc_ids.get("contract_id") or 
        doc_ids.get("agreement_id") or
        doc_ids.get("lease_id") or
        doc_ids.get("nda_id") or
        doc_ids.get("bill_number") or
        doc_ids.get("document_number") or
        doc_ids.get("reference_id") or
        ""
    )
    
    # Build results in frontend format
    results = {
        "contract_title": extracted_data.get("document_type", "Contract"),
        "contract_type": doc_type,
        "document_id": document_id,
        "execution_date": extracted_data.get("start_date", ""),
        "risk_score": risk_score,
        "parties": {
            "party_1_name": party_1_name,
            "party_1_address": vendor_address,
            "party_1_type": party_1_type,
            "party_2_name": party_2_name,
            "party_2_address": customer_address,
            "party_2_type": party_2_type
        },
        "payment_terms": {
            "amount": extracted_data.get("amount", ""),
            "currency": extracted_data.get("currency", ""),
            "frequency": extracted_data.get("frequency") or "1",  # Default to "1" if empty
            "due_date": extracted_data.get("due_date", ""),
            "amount_explanation": extracted_data.get("amount_explanation", "")
        },
        "payment_details": extracted_data.get("payment_details", {}),
        "termination_clause": "",
        "confidentiality_clause": extracted_data.get("confidentiality_clause", ""),
        "liability_clause": "",
        "governing_law": extracted_data.get("governing_law", ""),
        "deliverables": [],
        "missing_clauses": [f.get("factor", "") for f in risk_score_data.get("risk_factors", [])] if isinstance(risk_score_data, dict) else [],
        "document_ids": doc_ids,  # Include all document IDs
        "references": extracted_data.get("references", {}),  # Include page references for selected factors
        "_extraction_metadata": {
            "method": "hybrid",
            "components": {
                "rule_based": True,
                "spacy_ner": False,
                "graph_based": False
            }
        }
    }
    
    # Add invoice-specific fields if it's an invoice
    if doc_type == "INVOICE":
        payment_details = extracted_data.get("payment_details", {})
        
        # Get tax identifiers - support both old format and new nested format
        vendor_tax_ids = party_names.get("vendor_tax_ids", {})
        customer_tax_ids = party_names.get("customer_tax_ids", {})
        
        # Fallback to old format for backward compatibility
        if not vendor_tax_ids:
            vendor_tax_ids = {
                "gstin": party_names.get("vendor_gstin", ""),
                "pan": party_names.get("vendor_pan", "")
            }
        if not customer_tax_ids:
            customer_tax_ids = {
                "gstin": party_names.get("customer_gstin", "")
            }
        
        # Validate tax IDs - remove invalid values like company names
        vendor_tax_ids = _validate_tax_ids(vendor_tax_ids)
        customer_tax_ids = _validate_tax_ids(customer_tax_ids)
        
        results["invoice_details"] = {
            "invoice_id": invoice_id,
            "invoice_type": extracted_data.get("invoice_type", ""),
            "vendor_tax_ids": vendor_tax_ids,
            "customer_tax_ids": customer_tax_ids,
            # Keep backward compatibility
            "vendor_gstin": vendor_tax_ids.get("gstin", "") or party_names.get("vendor_gstin", ""),
            "vendor_pan": vendor_tax_ids.get("pan", "") or party_names.get("vendor_pan", ""),
            "customer_gstin": customer_tax_ids.get("gstin", "") or party_names.get("customer_gstin", ""),
            "line_items": extracted_data.get("line_items", []),
            "tax_details": extracted_data.get("tax_details", {}),
            "payment_details": payment_details,
            "payment_terms": payment_details.get("payment_terms", ""),
            "payment_method": payment_details.get("payment_method", ""),
            "bank_name": payment_details.get("bank_name", ""),
            "bank_address": payment_details.get("bank_address", ""),
            "notes": extracted_data.get("notes", ""),
            "declaration": extracted_data.get("declaration", ""),
            "terms_and_conditions": extracted_data.get("terms_and_conditions", ""),
            "remarks": extracted_data.get("remarks", ""),
            "additional_info": extracted_data.get("additional_info", ""),
            "dates": extracted_data.get("dates", {}),
            "amounts": extracted_data.get("amounts", {})
        }
    
    return results


def update_dashboard(results: dict, po_matched: bool = True):
    """Update dashboard statistics."""
    global dashboard_data
    
    dashboard_data["total_documents"] += 1
    
    # Check if it's an invoice and update invoice-specific stats
    doc_type = results.get("contract_type", results.get("document_type", "Unknown"))
    if doc_type and doc_type.upper() == "INVOICE":
        dashboard_data["total_invoices"] += 1
        if po_matched:
            dashboard_data["matched_invoices"] += 1
        else:
            dashboard_data["unmatched_invoices"] += 1
    
    # Update average risk score
    current_total = dashboard_data["average_risk_score"] * (dashboard_data["total_documents"] - 1)
    new_risk = results.get("risk_score", 0)
    dashboard_data["average_risk_score"] = int((current_total + new_risk) / dashboard_data["total_documents"])
    
    # Update missing clauses count
    missing = results.get("missing_clauses", [])
    dashboard_data["total_missing_clauses"] += len(missing)
    
    # Update contract types
    contract_type = results.get("contract_type", "Unknown")
    if contract_type in dashboard_data["contract_types"]:
        dashboard_data["contract_types"][contract_type] += 1
    else:
        dashboard_data["contract_types"][contract_type] = 1


# ============== Chatbot Endpoints ==============

class ChatUploadRequest(BaseModel):
    """Request model for chat document upload"""
    session_id: Optional[str] = None


class ChatQuestionRequest(BaseModel):
    """Request model for chat questions"""
    session_id: str
    question: str


@app.post("/api/chat/upload")
async def upload_chat_document(file: UploadFile = File(...)):
    """
    Upload a document for chatbot Q&A.
    Checks cache first (chatbot cache, then extraction cache) to avoid re-processing.
    Saves the file to validation folder for local validation.
    
    Args:
        file: The document file (PDF, DOCX, TXT)
        
    Returns:
        Session information with cache status
    """
    try:
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Read file content once
        content = await file.read()
        
        # Compute file hash for cache lookup
        cache_manager = get_cache_manager()
        file_hash = cache_manager.compute_content_hash(content)
        print(f"[CHATBOT] File hash: {file_hash[:16]}...")
        
        # Check chatbot cache first (fastest - instant load)
        cached_chatbot_data = cache_manager.load_chatbot_cache(file_hash)
        if cached_chatbot_data:
            print(f"[CHATBOT] [CACHE HIT] Found in chatbot cache, loading instantly...")
            
            # Load from chatbot cache
            document_text = cached_chatbot_data.get("document_text", "")
            page_map = {int(k): v for k, v in cached_chatbot_data.get("page_map", {}).items()}
            chunks = cached_chatbot_data.get("chunks", [])
            tables = cached_chatbot_data.get("tables", [])
            is_scanned = cached_chatbot_data.get("is_scanned", False)
            used_ocr = cached_chatbot_data.get("used_ocr", False)
            filename = cached_chatbot_data.get("filename", file.filename)
            
            # Create chatbot session from cache (no re-parsing needed!)
            chatbot = get_cached_chatbot()
            result = chatbot.create_session_from_cache(
                session_id=session_id,
                document_text=document_text,
                page_map=page_map,
                chunks=chunks,
                tables=tables,
                filename=filename,
                is_scanned=is_scanned,
                used_ocr=used_ocr
            )
            
            # Add cache status
            result["from_cache"] = "chatbot"
            result["cache_message"] = "Loaded from chatbot cache (instant)"
            
            # Save to validation folder
            file_ext = Path(file.filename).suffix
            safe_filename = f"{session_id}_{file.filename}"
            validation_path = VALIDATION_FOLDER / safe_filename
            try:
                with open(validation_path, "wb") as f:
                    f.write(content)
                print(f"[CHATBOT] Saved file to validation folder: {validation_path}")
                if validation_path.exists():
                    result["validation_path"] = str(validation_path)
                    result["validation_folder"] = str(VALIDATION_FOLDER)
            except Exception as e:
                print(f"[CHATBOT] Warning: Could not save to validation folder: {e}")
            
            return JSONResponse(content=result)
        
        # Check extraction cache (faster - reuse parsed text)
        cached_extraction_data = cache_manager.load_extraction_cache(file_hash)
        if cached_extraction_data:
            print(f"[CHATBOT] [CACHE HIT] Found in extraction cache, creating session from extraction data...")
            
            # Get document text from extraction cache
            document_text = cached_extraction_data.get("document_text", "")
            metadata = cached_extraction_data.get("metadata", {})
            page_map = metadata.get("page_map", {})
            # Convert page_map keys to int if they're strings
            if page_map and isinstance(next(iter(page_map.keys())), str):
                page_map = {int(k): v for k, v in page_map.items()}
            
            if document_text:
                # Save uploaded file temporarily for table extraction (if needed)
                temp_dir = tempfile.gettempdir()
                file_path = os.path.join(temp_dir, f"chat_{session_id}_{file.filename}")
                with open(file_path, "wb") as f:
                    f.write(content)
                
                # Create chatbot session from extraction cache (no re-parsing!)
                chatbot = get_cached_chatbot()
                result = chatbot.create_session_from_extraction_cache(
                    session_id=session_id,
                    document_text=document_text,
                    page_map=page_map,
                    filename=file.filename,
                    file_path=file_path,  # Pass file_path for table extraction
                    file_hash=file_hash  # Pass hash to save to chatbot cache
                )
                
                # Add cache status
                result["from_cache"] = "extraction"
                result["cache_message"] = "Loaded from extraction cache (reused parsed text)"
                
                # Save to validation folder
                file_ext = Path(file.filename).suffix
                safe_filename = f"{session_id}_{file.filename}"
                validation_path = VALIDATION_FOLDER / safe_filename
                try:
                    with open(validation_path, "wb") as f:
                        f.write(content)
                    print(f"[CHATBOT] Saved file to validation folder: {validation_path}")
                    if validation_path.exists():
                        result["validation_path"] = str(validation_path)
                        result["validation_folder"] = str(VALIDATION_FOLDER)
                except Exception as e:
                    print(f"[CHATBOT] Warning: Could not save to validation folder: {e}")
                
                # Clean up temp file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
                
                return JSONResponse(content=result)
        
        # If not in cache, proceed with normal processing
        print(f"[CHATBOT] [CACHE MISS] Processing new file...")
        
        # Save uploaded file temporarily for processing
        temp_dir = tempfile.gettempdir()
        file_path = os.path.join(temp_dir, f"chat_{session_id}_{file.filename}")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Save to validation folder for local validation
        file_ext = Path(file.filename).suffix
        safe_filename = f"{session_id}_{file.filename}"
        validation_path = VALIDATION_FOLDER / safe_filename
        
        try:
            with open(validation_path, "wb") as f:
                f.write(content)
            print(f"[CHATBOT] Saved file to validation folder: {validation_path}")
        except Exception as e:
            print(f"[CHATBOT] Warning: Could not save to validation folder: {e}")
        
        # Create chat session (reuse cached chatbot instance)
        # Pass file_hash so it can save to cache after processing
        chatbot = get_cached_chatbot()
        result = chatbot.create_session(session_id, file_path, file_hash=file_hash)
        
        # Add cache status
        result["from_cache"] = "none"
        result["cache_message"] = "New file processed"
        
        # Add validation path to result if saved successfully
        if validation_path.exists():
            result["validation_path"] = str(validation_path)
            result["validation_folder"] = str(VALIDATION_FOLDER)
        
        # Clean up temp file if session creation failed
        if not result.get("success", False):
            try:
                os.remove(file_path)
                if validation_path.exists():
                    os.remove(validation_path)
            except:
                pass
        
        return JSONResponse(content=result)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Upload failed: {str(e)}"}
        )


@app.post("/api/chat/load-from-extraction/{extraction_id}")
async def load_chat_from_extraction(extraction_id: str):
    """
    Create a chat session from an existing extraction (reuses parsed document text).
    This avoids re-parsing and re-creating vector database.
    
    Args:
        extraction_id: ID of the extraction
        
    Returns:
        Session information
    """
    try:
        extraction = None
        
        # Check if extraction exists in memory
        if extraction_id in extractions_store:
            extraction = extractions_store[extraction_id]
        else:
            # Try loading from cache
            try:
                cache_manager = get_cache_manager()
                cached_data = cache_manager.load_extraction_record(extraction_id)
                if cached_data:
                    extraction = cached_data
                    # Also add to memory store for future requests
                    extractions_store[extraction_id] = extraction
                    print(f"[CHATBOT] Loaded extraction {extraction_id} from cache into memory")
            except Exception as e:
                print(f"[CHATBOT] Error loading from cache: {e}")
        
        if not extraction:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Extraction not found"}
            )
        
        # Check if extraction is completed or po_not_found (both have valid results)
        valid_statuses = ["completed", "po_not_found"]
        status = extraction.get("status", "")
        if status not in valid_statuses:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Extraction not completed yet (status: {status})"}
            )
        
        # Get document text from metadata (already parsed during extraction)
        metadata = extraction.get("metadata", {})
        document_text = metadata.get("document_text")
        
        # If document_text is not in metadata, try to load from extraction cache
        page_map = metadata.get("page_map", {})
        if not document_text:
            file_hash = extraction.get("file_hash")
            if file_hash:
                print(f"[CHATBOT] Document text not in metadata, trying extraction cache...")
                cache_manager = get_cache_manager()
                cached_data = cache_manager.load_extraction_cache(file_hash)
                if cached_data:
                    document_text = cached_data.get("document_text", "")
                    cached_metadata = cached_data.get("metadata", {})
                    cached_page_map = cached_metadata.get("page_map", {})
                    if document_text:
                        print(f"[CHATBOT] ✓ Loaded document text from extraction cache")
                        # Update metadata with document_text for future use
                        metadata["document_text"] = document_text
                        if cached_page_map:
                            page_map = cached_page_map
                            metadata["page_map"] = page_map
                        extraction["metadata"] = metadata
                        save_extractions_to_file()
        
        if not document_text:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False, 
                    "error": "Document text not available in extraction. The extraction may have failed. Please re-extract the document.",
                    "extraction_status": extraction.get("status"),
                    "has_file_hash": bool(extraction.get("file_hash"))
                }
            )
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Get extracted data to enhance chatbot context
        extracted_data = extraction.get("extracted_data")
        
        # Create chat session from text (reuses parsed text, no re-parsing needed!)
        chatbot = get_cached_chatbot()
        
        # If we have page_map, use create_session_from_extraction_cache for better functionality
        if page_map and len(page_map) > 0:
            # Convert page_map keys to int if they're strings
            try:
                first_key = next(iter(page_map.keys()))
                if isinstance(first_key, str):
                    page_map = {int(k): v for k, v in page_map.items()}
            except (StopIteration, ValueError):
                page_map = {}
            
            if page_map:
                result = chatbot.create_session_from_extraction_cache(
                    session_id=session_id,
                    document_text=document_text,
                    page_map=page_map,
                    filename=extraction.get("file_name", "document.pdf"),
                    file_hash=extraction.get("file_hash")
                )
            else:
                # Fallback to text-only session if page_map conversion failed
                result = chatbot.create_session_from_text(
                    session_id=session_id,
                    document_text=document_text,
                    filename=extraction.get("file_name", "document.pdf"),
                    extracted_data=extracted_data
                )
        else:
            # Fallback to text-only session
            result = chatbot.create_session_from_text(
                session_id=session_id,
                document_text=document_text,
                filename=extraction.get("file_name", "document.pdf"),
                extracted_data=extracted_data  # Pass extracted data for enhanced context
            )
        
        return JSONResponse(content=result)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to load from extraction: {str(e)}"}
        )


@app.post("/api/chat/ask")
async def ask_chat_question(request: ChatQuestionRequest):
    """
    Ask a question about the uploaded document.
    
    Args:
        request: Contains session_id and question
        
    Returns:
        Answer and context
    """
    try:
        chatbot = get_cached_chatbot()
        result = chatbot.simple_ask(request.session_id, request.question)
        return JSONResponse(content=result)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Question processing failed: {str(e)}"}
        )


@app.get("/api/chat/session/{session_id}")
async def get_chat_session(session_id: str):
    """Get information about a chat session."""
    try:
        chatbot = get_cached_chatbot()
        info = chatbot.get_session_info(session_id)
        
        if info is None:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Session not found"}
            )
        
        return JSONResponse(content={"success": True, "session": info})
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.delete("/api/chat/session/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    try:
        chatbot = get_cached_chatbot()
        success = chatbot.delete_session(session_id)
        
        if not success:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Session not found"}
            )
        
        return JSONResponse(content={"success": True, "message": "Session deleted"})
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ============================================================================
# PURCHASE ORDER APIs - PO Upload and Matching
# ============================================================================

# In-memory store for PO extractions (similar to extractions_store)
po_extractions_store: Dict[str, Dict[str, Any]] = {}


@app.post("/api/upload-po")
async def upload_purchase_order(file: UploadFile = File(...)):
    """
    Upload a Purchase Order PDF for extraction.
    PO data is automatically extracted and cached for matching with invoices.
    
    Args:
        file: The PO file (PDF, DOCX, TXT)
        
    Returns:
        Extraction results with PO details
    """
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ['.pdf', '.docx', '.doc', '.txt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: .pdf, .docx, .doc, .txt"
        )
    
    try:
        # Generate extraction ID
        extraction_id = str(uuid.uuid4())
        
        print("\n" + "="*80)
        print(f"[PO UPLOAD] PURCHASE ORDER UPLOAD INITIATED")
        print("="*80)
        print(f"  File Name: {file.filename}")
        print(f"  File Type: {file_ext}")
        print(f"  Extraction ID: {extraction_id}")
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Compute file hash for caching
        cache_manager = get_cache_manager()
        file_hash = cache_manager.compute_content_hash(content)
        print(f"  File Size: {file_size:,} bytes ({file_size/1024:.2f} KB)")
        print(f"  File Hash: {file_hash[:16]}...")
        
        # Check PO cache first
        print(f"\n[STEP 1] Checking PO cache...")
        cached_result = cache_manager.load_po_cache(file_hash)
        
        if cached_result:
            print(f"   [CACHE HIT] Found cached PO extraction!")
            print(f"   - Cached at: {cached_result.get('cached_at', 'Unknown')}")
            
            extracted_data = cached_result.get("extracted_data", {})
            metadata = cached_result.get("metadata", {})
            po_number = extracted_data.get("document_ids", {}).get("po_number", "N/A")
            
            # Transform to frontend format for dashboard display
            results = transform_to_frontend_format(extracted_data, metadata)
            
            print(f"\n" + "="*80)
            print(f"[SUCCESS] PO LOADED FROM CACHE!")
            print(f"="*80)
            print(f"  PO Number: {po_number}")
            print(f"  Document: {file.filename}")
            print("="*80 + "\n")
            
            return {
                "success": True,
                "extraction_id": extraction_id,
                "file_name": file.filename,
                "file_hash": file_hash,
                "from_cache": True,
                "cached": True,
                "extracted_data": extracted_data,
                "results": results,  # For dashboard display
                "po_number": po_number,
                "message": f"PO loaded from cache: {po_number}"
            }
        
        print(f"   [CACHE MISS] PO not in cache, proceeding with extraction...")
        
        # Save to temp file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        print(f"  Temp Path: {temp_path}")
        
        try:
            # Extract PO data
            print(f"\n[STEP 2] Extracting PO data...")
            po_extractor = get_po_extractor(api_key=api_key, use_gcs_vision=True)
            extracted_data, metadata = po_extractor.extract_from_file(temp_path)
            
            # Get PO number for display
            doc_ids = extracted_data.get("document_ids", {})
            po_number = doc_ids.get("po_number", "") or doc_ids.get("order_number", "") or "N/A"
            
            print(f"   [OK] Extraction completed!")
            print(f"   - PO Number: {po_number}")
            print(f"   - Fields Extracted: {len(extracted_data)} fields")
            
            # Upload PO PDF to GCS
            print(f"\n[STEP 3] Uploading PO PDF to GCS...")
            gcs_uri = cache_manager.upload_po_pdf_to_gcs(temp_path, file.filename)
            if gcs_uri:
                print(f"   [OK] Uploaded to: {gcs_uri}")
                metadata["gcs_uri"] = gcs_uri
            else:
                print(f"   [SKIP] GCS upload skipped (local mode)")
            
            # Save to PO cache
            print(f"\n[STEP 4] Saving to PO cache...")
            document_text = metadata.get("document_text", "")
            cache_manager.save_po_cache(file_hash, extracted_data, metadata, document_text, file.filename)
            print(f"   [OK] Saved to cache")
            
            # Store in memory for quick access
            po_extractions_store[extraction_id] = {
                "file_path": temp_path,
                "file_name": file.filename,
                "file_hash": file_hash,
                "status": "completed",
                "extracted_data": extracted_data,
                "metadata": metadata,
                "uploaded_at": datetime.now().isoformat(),
                "extracted_at": datetime.now().isoformat()
            }
            
            # Transform to frontend format for dashboard display
            results = transform_to_frontend_format(extracted_data, metadata)
            
            print(f"\n" + "="*80)
            print(f"[SUCCESS] PO EXTRACTION COMPLETED!")
            print(f"="*80)
            print(f"  Summary:")
            print(f"   - Document: {file.filename}")
            print(f"   - PO Number: {po_number}")
            print(f"   - Status: Completed")
            print(f"   - Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*80 + "\n")
            
            return {
                "success": True,
                "extraction_id": extraction_id,
                "file_name": file.filename,
                "file_hash": file_hash,
                "from_cache": False,
                "cached": False,
                "extracted_data": extracted_data,
                "results": results,  # For dashboard display
                "po_number": po_number,
                "gcs_uri": gcs_uri,
                "message": f"PO extracted successfully: {po_number}"
            }
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
                
    except Exception as e:
        print(f"\n" + "="*80)
        print(f"[ERROR] PO UPLOAD FAILED!")
        print("="*80)
        print(f"  File: {file.filename if file else 'Unknown'}")
        print(f"  Error: {str(e)}")
        print("="*80 + "\n")
        
        import traceback
        traceback.print_exc()
        
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/po/list")
async def list_purchase_orders():
    """
    List all available Purchase Orders.
    
    Returns:
        List of PO summaries from the index
    """
    try:
        cache_manager = get_cache_manager()
        po_index = cache_manager.get_all_pos()
        
        # Convert to list format
        po_list = []
        for file_hash, entry in po_index.items():
            po_list.append({
                "file_hash": file_hash,
                "po_number": entry.get("po_number", "N/A"),
                "filename": entry.get("filename", "Unknown"),
                "vendor": entry.get("vendor", ""),
                "customer": entry.get("customer", ""),
                "total_amount": entry.get("total_amount", ""),
                "indexed_at": entry.get("indexed_at", "")
            })
        
        # Sort by indexed_at (newest first)
        po_list.sort(key=lambda x: x.get("indexed_at", ""), reverse=True)
        
        return {
            "success": True,
            "count": len(po_list),
            "purchase_orders": po_list
        }
        
    except Exception as e:
        print(f"[ERROR] List POs failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/po/{file_hash}")
async def get_purchase_order(file_hash: str):
    """
    Get full details of a specific Purchase Order.
    
    Args:
        file_hash: SHA256 hash of the PO file
        
    Returns:
        Full PO extraction data with frontend-formatted results
    """
    try:
        cache_manager = get_cache_manager()
        po_data = cache_manager.load_po_cache(file_hash)
        
        if not po_data:
            raise HTTPException(status_code=404, detail="Purchase Order not found")
        
        # Extract data for frontend display
        extracted_data = po_data.get("extracted_data", {})
        metadata = po_data.get("metadata", {})
        filename = po_data.get("filename", "Unknown")
        po_number = extracted_data.get("document_ids", {}).get("po_number", "N/A")
        
        # Transform to frontend format for dashboard display
        results = transform_to_frontend_format(extracted_data, metadata)
        
        return {
            "success": True,
            "file_hash": file_hash,
            "filename": filename,
            "po_number": po_number,
            "po_data": po_data,
            "results": results  # Frontend-formatted results for dashboard display
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Get PO failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/po/match")
async def match_invoice_with_po_endpoint(request: Request):
    """
    Match an invoice with a Purchase Order.
    
    Request body:
    {
        "invoice_data": { ... extracted invoice data ... }
    }
    
    Returns:
        Matching result with PO details if found
    """
    try:
        body = await request.json()
        invoice_data = body.get("invoice_data", {})
        
        if not invoice_data:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "invoice_data is required"}
            )
        
        # Match with PO
        matched, po_data, message = match_invoice(invoice_data)
        
        return {
            "success": True,
            "matched": matched,
            "message": message,
            "po_data": po_data
        }
        
    except Exception as e:
        print(f"[ERROR] PO matching failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.get("/api/po/count")
async def get_po_count():
    """
    Get the count of available Purchase Orders.
    
    Returns:
        Number of POs in the system
    """
    try:
        po_matcher = get_po_matcher()
        count = po_matcher.get_po_count()
        
        return {
            "success": True,
            "count": count
        }
        
    except Exception as e:
        print(f"[ERROR] Get PO count failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


# ============================================================================
# FILE MANAGEMENT APIs - Cache and Storage Management
# ============================================================================

@app.get("/api/files/list")
async def list_cached_files():
    """
    List all cached files from local storage and GCS.
    Returns categorized list of files with metadata.
    """
    try:
        cache_manager = get_cache_manager()
        files = cache_manager.list_all_cached_files()
        
        # Add summary counts
        files["summary"] = {
            "total_extraction_cache": len(files.get("extraction_cache", [])),
            "total_po_cache": len(files.get("po_cache", [])),
            "total_chatbot_cache": len(files.get("chatbot_cache", [])),
            "total_extractions_data": len(files.get("extractions_data", [])),
            "total_exports": len(files.get("exports", []))
        }
        
        return JSONResponse(content={"success": True, "data": files})
        
    except Exception as e:
        print(f"[ERROR] List files failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/files/delete")
async def delete_files(request: Request):
    """
    Delete specific files from local and/or GCS storage.
    
    Request body:
    {
        "files": [
            {"path": "path/to/file", "location": "local|gcs"},
            ...
        ],
        "file_hashes": ["hash1", "hash2"],  // Delete all cache for these hashes
        "extraction_ids": ["id1", "id2"]     // Delete these extraction records
    }
    """
    try:
        # Handle empty or invalid JSON body
        try:
            body = await request.json()
        except Exception as json_error:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Invalid or empty request body. Expected JSON with 'files', 'file_hashes', or 'extraction_ids' array."}
            )
        
        if not body:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Empty request body. Provide 'files', 'file_hashes', or 'extraction_ids'."}
            )
        
        results = {
            "deleted": [],
            "failed": [],
            "total_deleted": 0
        }
        
        cache_manager = get_cache_manager()
        
        # Delete specific files
        files_to_delete = body.get("files", [])
        for file_info in files_to_delete:
            file_path = file_info.get("path")
            location = file_info.get("location", "local")
            
            success, message = cache_manager.delete_file(file_path, location)
            if success:
                results["deleted"].append(message)
                results["total_deleted"] += 1
            else:
                results["failed"].append(message)
        
        # Delete by file hashes (deletes both extraction and chatbot cache)
        file_hashes = body.get("file_hashes", [])
        for file_hash in file_hashes:
            hash_result = cache_manager.delete_by_file_hash(
                file_hash, 
                delete_local=True, 
                delete_gcs=True
            )
            results["deleted"].extend(hash_result.get("deleted", []))
            results["failed"].extend(hash_result.get("failed", []))
            results["total_deleted"] += len(hash_result.get("deleted", []))
        
        # Delete extraction records from extractions_data.json
        extraction_ids = body.get("extraction_ids", [])
        for extraction_id in extraction_ids:
            # Also delete from in-memory store
            if extraction_id in extractions_store:
                del extractions_store[extraction_id]
            
            success, message = cache_manager.delete_extraction_record(extraction_id)
            if success:
                results["deleted"].append(message)
                results["total_deleted"] += 1
            else:
                results["failed"].append(message)
        
        # Recalculate dashboard data after deletions
        if extraction_ids:
            recalculate_dashboard_from_extractions()
        
        return JSONResponse(content={"success": True, "results": results})
        
    except Exception as e:
        print(f"[ERROR] Delete files failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.post("/api/files/clear-all")
async def clear_all_cache(request: Request):
    """
    Clear all cache files from local and/or GCS storage.
    
    Request body:
    {
        "clear_local": true,
        "clear_gcs": true,
        "clear_extractions_data": false,
        "clear_in_memory": true
    }
    """
    try:
        # Handle empty or invalid JSON body - use defaults if empty
        try:
            body = await request.json()
        except Exception:
            body = {}  # Use defaults if no body provided
        
        clear_local = body.get("clear_local", True)
        clear_gcs = body.get("clear_gcs", True)
        clear_extractions_data = body.get("clear_extractions_data", False)
        clear_in_memory = body.get("clear_in_memory", True)
        
        cache_manager = get_cache_manager()
        
        results = cache_manager.clear_all_cache(
            clear_local=clear_local,
            clear_gcs=clear_gcs,
            clear_extractions_data=clear_extractions_data
        )
        
        # Clear in-memory store if requested
        if clear_in_memory and clear_extractions_data:
            global extractions_store
            extractions_store.clear()
            results["in_memory_cleared"] = True
            # Recalculate dashboard (will reset to 0 since store is empty)
            recalculate_dashboard_from_extractions()
        
        return JSONResponse(content={"success": True, "results": results})
        
    except Exception as e:
        print(f"[ERROR] Clear all cache failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


@app.delete("/api/files/extraction/{extraction_id}")
async def delete_extraction_complete(extraction_id: str):
    """
    Delete an extraction completely - removes from extractions_data.json,
    in-memory store, and all associated cache files (local and GCS).
    """
    try:
        cache_manager = get_cache_manager()
        results = {
            "extraction_id": extraction_id,
            "deleted": [],
            "failed": []
        }
        
        # Get file hash from in-memory store or extractions_data
        file_hash = None
        if extraction_id in extractions_store:
            extraction_data = extractions_store[extraction_id]
            if extraction_data and isinstance(extraction_data, dict):
                file_hash = extraction_data.get("file_hash")
            del extractions_store[extraction_id]
            results["deleted"].append("Removed from in-memory store")
        
        # Delete from extractions_data.json
        success, message = cache_manager.delete_extraction_record(extraction_id)
        if success:
            results["deleted"].append(message)
        else:
            results["failed"].append(message)
        
        # Delete cache files if we have the file hash
        if file_hash:
            hash_result = cache_manager.delete_by_file_hash(file_hash, delete_local=True, delete_gcs=True)
            results["deleted"].extend(hash_result.get("deleted", []))
            results["failed"].extend(hash_result.get("failed", []))
        
        # Recalculate dashboard data after deletion
        recalculate_dashboard_from_extractions()
        
        return JSONResponse(content={"success": True, "results": results})
        
    except Exception as e:
        print(f"[ERROR] Delete extraction failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )


if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Invoice to Account Payable Application")
    print("=" * 50)
    print()
    print("Starting server...")
    print()
    print("Web UI:  http://localhost:8000")
    print("API:     http://localhost:8000/docs")
    print()
    print("Press CTRL+C to stop the server")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8000)
