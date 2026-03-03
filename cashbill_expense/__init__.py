"""
Cash bill to Expense module.
Uses GCP Vision API for receipt/cash bill OCR and stores results in the expense table.
Independent of Invoice to AP; no shared state.
"""

from cashbill_expense.store import get_expense_store, expense_store
from cashbill_expense.vision_extract import extract_expense_from_file

__all__ = [
    "get_expense_store",
    "expense_store",
    "extract_expense_from_file",
]
