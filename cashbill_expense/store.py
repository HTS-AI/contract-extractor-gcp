"""
In-memory expense store with optional JSON file persistence.
Separate from Invoice to AP extractions; used only by Cash bill to Expense.
"""

import os
import json
import shutil
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

# Default path for persistence (project data folder)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
EXPENSE_FILE = os.path.join(DATA_DIR, "expense_records.json")
EXPENSE_FILES_DIR = os.path.join(DATA_DIR, "expense_files")

_expense_list: List[Dict[str, Any]] = []
_loaded = False


def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _load_from_file():
    global _expense_list, _loaded
    if _loaded:
        return
    _loaded = True
    if not os.path.isfile(EXPENSE_FILE):
        _expense_list[:] = []
        return
    try:
        with open(EXPENSE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _expense_list[:] = data.get("expenses", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
    except Exception:
        _expense_list[:] = []


def _save_to_file():
    _ensure_data_dir()
    try:
        with open(EXPENSE_FILE, "w", encoding="utf-8") as f:
            json.dump({"expenses": _expense_list, "updated": datetime.utcnow().isoformat() + "Z"}, f, indent=2)
    except Exception:
        pass


def get_expense_store() -> List[Dict[str, Any]]:
    _load_from_file()
    return _expense_list


def add_expense(record: Dict[str, Any]) -> str:
    """Append an expense record; generate expense_id if missing. Returns expense_id."""
    _load_from_file()
    record = dict(record)
    if not record.get("expense_id"):
        record["expense_id"] = str(uuid.uuid4())
    record.setdefault("extracted_at", datetime.utcnow().isoformat() + "Z")
    _expense_list.append(record)
    _save_to_file()
    return record["expense_id"]


def get_expense_by_id(expense_id: str) -> Optional[Dict[str, Any]]:
    _load_from_file()
    for r in _expense_list:
        if r.get("expense_id") == expense_id:
            return r
    return None


def update_expense(expense_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update fields on an expense record. Returns the updated record or None."""
    _load_from_file()
    for r in _expense_list:
        if r.get("expense_id") == expense_id:
            for k, v in updates.items():
                if k == "expense_id":
                    continue
                r[k] = v
            r["updated_at"] = datetime.utcnow().isoformat() + "Z"
            _save_to_file()
            return r
    return None


def delete_expense(expense_id: str) -> bool:
    _load_from_file()
    for i, r in enumerate(_expense_list):
        if r.get("expense_id") == expense_id:
            file_path = r.get("source_file_path")
            _expense_list.pop(i)
            _save_to_file()
            if file_path:
                try:
                    os.unlink(file_path)
                except Exception:
                    pass
            return True
    return False


def save_expense_file(expense_id: str, src_path: str, filename: str) -> str:
    """Copy the uploaded source file into persistent storage. Returns the saved path."""
    os.makedirs(EXPENSE_FILES_DIR, exist_ok=True)
    ext = os.path.splitext(filename)[1] or ".pdf"
    dest = os.path.join(EXPENSE_FILES_DIR, f"{expense_id}{ext}")
    shutil.copy2(src_path, dest)
    return dest


class expense_store:
    """Namespace for store operations."""
    get_all = get_expense_store
    add = add_expense
    get_by_id = get_expense_by_id
    update = update_expense
    delete = delete_expense
    save_file = save_expense_file
