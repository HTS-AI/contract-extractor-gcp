"""
Folder processor: picks up PO, Invoice, and GRN documents from documents_repo subfolders
and processes them (extraction + index). Run on startup and optionally on sync API.
"""

import os
import uuid
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Callable

# Documents repo paths (same as app) - no import of app to avoid circular import
_REPO_BASE = Path(__file__).parent / "documents_repo"
DOCUMENTS_REPO_PO = _REPO_BASE / "PO"
DOCUMENTS_REPO_INVOICE = _REPO_BASE / "Invoice"
DOCUMENTS_REPO_GRN = _REPO_BASE / "GRN"


def _get_repo_paths():
    return DOCUMENTS_REPO_PO, DOCUMENTS_REPO_INVOICE, DOCUMENTS_REPO_GRN


def _allowed_ext(path: Path) -> bool:
    return path.suffix.lower() in (".pdf", ".docx", ".doc", ".txt")


def scan_and_process_documents(
    process_po: bool = True,
    process_invoice: bool = True,
    process_grn: bool = True,
    extractions_store_ref: Optional[Dict[str, Any]] = None,
    extraction_status_ref: Optional[Dict[str, Any]] = None,
    save_extractions_cb: Optional[Callable[[], None]] = None,
) -> Dict[str, Any]:
    """
    Scan documents_repo/PO, Invoice, GRN and process any new files.
    If extractions_store_ref/save_extractions_cb are provided, invoice processing will update store and save.
    Returns summary: { processed: int, po: n, invoice: n, grn: n, errors: [] }.
    """
    from cache_manager import get_cache_manager

    result = {"processed": 0, "po": 0, "invoice": 0, "grn": 0, "errors": []}
    store = extractions_store_ref if extractions_store_ref is not None else {}
    po_dir, invoice_dir, grn_dir = _get_repo_paths()
    cache_manager = get_cache_manager()

    # Collect existing hashes so we don't reprocess
    po_index = cache_manager.get_all_pos()
    existing_po_hashes = set(po_index.keys()) if isinstance(po_index, dict) else set()
    grn_index = cache_manager.get_all_grns()
    existing_grn_hashes = set(grn_index.keys()) if isinstance(grn_index, dict) else set()
    existing_invoice_hashes = set()
    for ext in store.values():
        h = ext.get("file_hash")
        if h:
            existing_invoice_hashes.add(h)

    # Process PO folder
    if process_po and po_dir.exists():
        for file_path in po_dir.iterdir():
            if not file_path.is_file() or not _allowed_ext(file_path):
                continue
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                file_hash = cache_manager.compute_content_hash(content)
                if file_hash in existing_po_hashes:
                    continue
                # Process this PO
                ok = _process_po_file(str(file_path), content, file_path.name, file_hash, cache_manager)
                if ok:
                    result["po"] += 1
                    result["processed"] += 1
                    existing_po_hashes.add(file_hash)
            except Exception as e:
                result["errors"].append(f"PO {file_path.name}: {e}")

    # Process GRN folder
    if process_grn and grn_dir.exists():
        for file_path in grn_dir.iterdir():
            if not file_path.is_file() or not _allowed_ext(file_path):
                continue
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                file_hash = cache_manager.compute_content_hash(content)
                if file_hash in existing_grn_hashes:
                    continue
                ok = _process_grn_file(str(file_path), content, file_path.name, file_hash, cache_manager)
                if ok:
                    result["grn"] += 1
                    result["processed"] += 1
                    existing_grn_hashes.add(file_hash)
            except Exception as e:
                result["errors"].append(f"GRN {file_path.name}: {e}")

    # Process Invoice folder
    if process_invoice and invoice_dir.exists():
        for file_path in invoice_dir.iterdir():
            if not file_path.is_file() or not _allowed_ext(file_path):
                continue
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                file_hash = cache_manager.compute_content_hash(content)
                if file_hash in existing_invoice_hashes:
                    continue
                ok = _process_invoice_file(
                    str(file_path), content, file_path.name, file_hash, cache_manager,
                    store, extraction_status_ref, save_extractions_cb,
                )
                if ok:
                    result["invoice"] += 1
                    result["processed"] += 1
                    existing_invoice_hashes.add(file_hash)
            except Exception as e:
                result["errors"].append(f"Invoice {file_path.name}: {e}")

    return result


def _process_po_file(
    file_path: str, content: bytes, filename: str, file_hash: str, cache_manager
) -> bool:
    """Extract PO and save to index. Returns True on success."""
    from po_extractor import get_po_extractor
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        po_extractor = get_po_extractor(api_key=api_key, use_gcs_vision=True)
        extracted_data, metadata = po_extractor.extract_from_file(tmp_path)
        document_text = (metadata or {}).get("document_text", "")
        cache_manager.save_po_cache(file_hash, extracted_data, metadata or {}, document_text, filename)
        cache_manager.save_all_purchase_orders_json(cache_manager.get_all_pos_full())
        return True
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _process_grn_file(
    file_path: str, content: bytes, filename: str, file_hash: str, cache_manager
) -> bool:
    """Extract GRN (PO-like schema) and save to GRN index. Returns True on success."""
    from grn_extractor import extract_grn_from_file
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        extracted_data, metadata = extract_grn_from_file(tmp_path, api_key=api_key)
        document_text = (metadata or {}).get("document_text", "")
        cache_manager.save_grn(file_hash, extracted_data, metadata or {}, document_text, filename)
        cache_manager.save_all_grns_json(cache_manager.get_all_grns_full())
        return True
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def _process_invoice_file(
    file_path: str,
    content: bytes,
    filename: str,
    file_hash: str,
    cache_manager,
    extractions_store_ref: Dict[str, Any],
    extraction_status_ref: Optional[Dict[str, Any]] = None,
    save_extractions_cb: Optional[Callable[[], None]] = None,
) -> bool:
    """Extract invoice and add to extractions_store. Returns True on success."""
    from extraction_agent import ExtractionAgent
    from datetime import datetime

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return False
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        agent = ExtractionAgent(api_key=api_key)
        extraction_id = str(uuid.uuid4())
        if extraction_status_ref is not None:
            extraction_status_ref[extraction_id] = {
                "current_step": "parsing",
                "step_description": "Processing invoice from folder...",
                "progress_percent": 0,
            }
        extracted_data, metadata = agent.extract_from_file(tmp_path, extraction_id=extraction_id)
        if not extracted_data:
            return False
        status = "completed"
        try:
            from po_matcher import match_invoice
            matched, _po, _msg = match_invoice(extracted_data)
            if not matched:
                status = "po_not_found"
        except Exception:
            pass
        now = datetime.now().isoformat()
        extractions_store_ref[extraction_id] = {
            "file_path": tmp_path,
            "file_name": filename,
            "file_hash": file_hash,
            "status": status,
            "extracted_data": extracted_data,
            "metadata": metadata,
            "uploaded_at": now,
            "extracted_at": now,
            "from_folder": True,
        }
        if save_extractions_cb:
            save_extractions_cb()
        return True
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
