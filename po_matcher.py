"""
Purchase Order Matching Service
Matches invoices with Purchase Orders for validation before saving to Excel.
"""

import os
from typing import Dict, Any, Optional, Tuple
from cache_manager import get_cache_manager


class POMatcher:
    """
    Matches invoices with Purchase Orders.
    
    Matching priority:
    1. PO Number match (if invoice has po_number)
    2. Fallback matching by:
       - Vendor/Customer names
       - Item descriptions
       - Amounts
    """
    
    def __init__(self):
        """Initialize PO matcher."""
        self.cache_manager = get_cache_manager()
    
    def match_invoice_with_po(self, invoice_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Try to match an invoice with a Purchase Order.
        
        Args:
            invoice_data: Extracted invoice data
            
        Returns:
            Tuple of (matched: bool, po_data: Optional[Dict], message: str)
        """
        # Check if document is an invoice
        doc_type = invoice_data.get("document_type", "").upper()
        if doc_type != "INVOICE":
            return True, None, "Not an invoice, no PO matching required"
        
        # Get invoice details for matching
        doc_ids = invoice_data.get("document_ids", {})
        party_names = invoice_data.get("party_names", {})
        
        # Get PO number from invoice (if present)
        po_number = doc_ids.get("po_number", "") or doc_ids.get("order_number", "") or ""
        
        # Get vendor/customer names
        vendor = party_names.get("vendor", "") or party_names.get("party_1", "") or ""
        customer = party_names.get("customer", "") or party_names.get("party_2", "") or ""
        
        # Get line items
        line_items = invoice_data.get("line_items", [])
        item_descriptions = [item.get("description", "") for item in line_items if item.get("description")]
        
        # Get total amount
        total_amount = invoice_data.get("amount", "") or invoice_data.get("amounts", {}).get("total", "")
        
        # Primary matching: by PO number
        if po_number and po_number.strip():
            print(f"[PO_MATCHER] Searching for PO by number: {po_number}")
            po_match = self.cache_manager.find_po_by_number(po_number)
            
            if po_match:
                print(f"[PO_MATCHER] ✓ Found matching PO: {po_match.get('filename', 'Unknown')}")
                return True, po_match, f"Matched by PO number: {po_number}"
            else:
                print(f"[PO_MATCHER] ✗ No PO found with number: {po_number}")
                return False, None, f"PO not found: No Purchase Order with number '{po_number}' exists in the system"
        
        # Fallback matching: by vendor, customer, items, amount
        print(f"[PO_MATCHER] No PO number in invoice, attempting fallback matching...")
        print(f"[PO_MATCHER]   Vendor: {vendor[:50] if vendor else 'N/A'}")
        print(f"[PO_MATCHER]   Customer: {customer[:50] if customer else 'N/A'}")
        print(f"[PO_MATCHER]   Items: {len(item_descriptions)} items")
        print(f"[PO_MATCHER]   Amount: {total_amount or 'N/A'}")
        
        po_match = self.cache_manager.find_po_by_details(
            vendor=vendor,
            customer=customer,
            items=item_descriptions,
            amount=total_amount
        )
        
        if po_match:
            match_score = po_match.get("match_score", 0)
            print(f"[PO_MATCHER] ✓ Found matching PO (score: {match_score}): {po_match.get('filename', 'Unknown')}")
            return True, po_match, f"Matched by vendor/customer/items (score: {match_score})"
        
        print(f"[PO_MATCHER] ✗ No matching PO found")
        return False, None, "PO not found: No matching Purchase Order found. Please upload the corresponding PO first."
    
    def get_all_pos(self) -> Dict[str, Any]:
        """
        Get all available POs for display/selection.
        
        Returns:
            Dictionary of all PO index entries
        """
        return self.cache_manager.get_all_pos()
    
    def get_po_count(self) -> int:
        """
        Get the count of available POs.
        
        Returns:
            Number of POs in the system
        """
        po_index = self.cache_manager.get_all_pos()
        return len(po_index)


# Singleton instance
_po_matcher_instance: Optional[POMatcher] = None


def get_po_matcher() -> POMatcher:
    """Get or create the PO matcher singleton instance."""
    global _po_matcher_instance
    if _po_matcher_instance is None:
        _po_matcher_instance = POMatcher()
    return _po_matcher_instance


def match_invoice(invoice_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Convenience function to match an invoice with a PO.
    
    Args:
        invoice_data: Extracted invoice data
        
    Returns:
        Tuple of (matched: bool, po_data: Optional[Dict], message: str)
    """
    matcher = get_po_matcher()
    return matcher.match_invoice_with_po(invoice_data)
