"""
Purchase Order / GRN / Invoice Matching Service

Matching hierarchy:
  1. PO is the gatekeeper – no PO → invoice cannot enter AP.
  2. If GRN exists for the PO → match invoice quantities/items against GRN (GRN is truth for what was received).
  3. If GRN is absent → fall back to matching invoice against PO quantities (2-way match).
  4. Vendor/supplier on the invoice must match the vendor on the PO.
"""

import re
from typing import Dict, Any, Optional, Tuple, List
from cache_manager import get_cache_manager


def _normalize(text: str) -> str:
    """Lowercase, strip, collapse whitespace."""
    return re.sub(r'\s+', ' ', (text or "").strip().lower())


def _parse_qty(val) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(re.sub(r'[^\d.\-]', '', str(val)))
    except (ValueError, TypeError):
        return 0.0


def _vendor_match(invoice_vendor: str, po_vendor: str) -> bool:
    """Check whether vendor/supplier names are a reasonable match."""
    a = _normalize(invoice_vendor)
    b = _normalize(po_vendor)
    if not a or not b:
        return True  # if one side is blank we can't verify – allow
    if a == b:
        return True
    if a in b or b in a:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    noise = {'pvt', 'ltd', 'llp', 'inc', 'llc', 'co', 'corp', 'company', 'limited', 'private', 'services', 'solutions', 'india', 'technologies', 'technology', 'the'}
    a_clean = a_tokens - noise
    b_clean = b_tokens - noise
    if a_clean and b_clean:
        overlap = len(a_clean & b_clean)
        max_len = max(len(a_clean), len(b_clean))
        if overlap / max_len >= 0.5:
            return True
    return False


def _match_line_items(invoice_items: List[dict], reference_items: List[dict], ref_label: str) -> List[str]:
    """
    Compare invoice line items against reference (GRN or PO) line items.
    Returns a list of mismatch descriptions (empty = all matched).
    """
    issues: List[str] = []
    if not invoice_items and not reference_items:
        return issues

    ref_by_desc: Dict[str, dict] = {}
    for item in (reference_items or []):
        desc = _normalize(item.get("description", ""))
        if desc:
            ref_by_desc[desc] = item

    matched_refs = set()
    for inv_item in (invoice_items or []):
        inv_desc = _normalize(inv_item.get("description", ""))
        inv_qty = _parse_qty(inv_item.get("quantity"))
        if not inv_desc:
            continue

        best_key = None
        for ref_key in ref_by_desc:
            if ref_key == inv_desc or ref_key in inv_desc or inv_desc in ref_key:
                best_key = ref_key
                break
        if not best_key:
            inv_tokens = set(inv_desc.split())
            for ref_key in ref_by_desc:
                ref_tokens = set(ref_key.split())
                common = inv_tokens & ref_tokens
                if len(common) >= max(1, min(len(inv_tokens), len(ref_tokens)) * 0.5):
                    best_key = ref_key
                    break

        if best_key:
            matched_refs.add(best_key)
            ref_item = ref_by_desc[best_key]
            ref_qty = _parse_qty(ref_item.get("quantity"))
            if inv_qty > 0 and ref_qty > 0 and inv_qty > ref_qty:
                issues.append(
                    f"Item '{inv_item.get('description', inv_desc)}': Invoice qty ({inv_qty}) exceeds {ref_label} qty ({ref_qty})"
                )
        else:
            issues.append(
                f"Item '{inv_item.get('description', inv_desc)}' not found in {ref_label}"
            )

    for ref_key, ref_item in ref_by_desc.items():
        if ref_key not in matched_refs:
            issues.append(
                f"Item '{ref_item.get('description', ref_key)}' in {ref_label} but not in Invoice"
            )
    return issues


class POMatcher:
    """
    Matching hierarchy:
      1. PO must exist (gatekeeper).
      2. Vendor on invoice must match vendor on PO.
      3. If GRN exists → match invoice qty/items against GRN.
      4. If GRN absent → match invoice qty/items against PO (2-way).
    Returns (matched, po_data, message, notifications).
    """

    def __init__(self):
        self.cache_manager = get_cache_manager()

    def match_invoice_with_po(
        self, invoice_data: Dict[str, Any]
    ) -> Tuple[bool, Optional[Dict[str, Any]], str, List[Dict[str, str]]]:
        """
        Returns (matched, po_data, message, notifications).
        notifications is a list of {type, title, detail} dicts for the UI bell.
        """
        notifications: List[Dict[str, str]] = []

        doc_type = invoice_data.get("document_type", "").upper()
        if doc_type != "INVOICE":
            return True, None, "Not an invoice, no matching required", notifications

        doc_ids = invoice_data.get("document_ids", {})
        party_names = invoice_data.get("party_names", {})
        po_number = (doc_ids.get("po_number", "") or doc_ids.get("order_number", "") or "").strip()
        invoice_vendor = party_names.get("vendor", "") or party_names.get("party_1", "") or ""
        customer = party_names.get("customer", "") or party_names.get("party_2", "") or ""
        invoice_items = invoice_data.get("line_items", [])
        total_amount = invoice_data.get("amount", "") or invoice_data.get("amounts", {}).get("total", "")

        # ── Step 1: Find PO (gatekeeper) ──
        po_match = None
        if po_number:
            print(f"[PO_MATCHER] Searching for PO by number: {po_number}")
            po_match = self.cache_manager.find_po_by_number(po_number)
            if po_match:
                print(f"[PO_MATCHER] Found PO: {po_match.get('filename', 'Unknown')}")
            else:
                msg = f"PO not found: No Purchase Order with number '{po_number}' exists. Upload the PO first."
                print(f"[PO_MATCHER] {msg}")
                notifications.append({
                    "type": "error",
                    "title": "PO Not Found",
                    "detail": f"No Purchase Order with number '{po_number}' found. Invoice cannot be processed in Accounts Payable. Please upload the corresponding PO."
                })
                return False, None, msg, notifications
        else:
            print(f"[PO_MATCHER] No PO number in invoice, attempting fallback matching...")
            item_descriptions = [i.get("description", "") for i in invoice_items if i.get("description")]
            po_match = self.cache_manager.find_po_by_details(
                vendor=invoice_vendor, customer=customer,
                items=item_descriptions, amount=total_amount
            )
            if po_match:
                po_number = (po_match.get("po_number") or "").strip()
                print(f"[PO_MATCHER] Found PO by details: {po_match.get('filename')} (PO# {po_number})")
            else:
                msg = "PO not found: No matching Purchase Order found. Please upload the corresponding PO first."
                print(f"[PO_MATCHER] {msg}")
                notifications.append({
                    "type": "error",
                    "title": "PO Not Found",
                    "detail": "No matching Purchase Order found for this invoice. Invoice cannot be processed in Accounts Payable. Please upload the corresponding PO."
                })
                return False, None, msg, notifications

        # ── Step 2: Vendor / Supplier match ──
        po_full = (po_match.get("full_data") or {}) if isinstance(po_match, dict) else {}
        po_extracted = po_full.get("extracted_data", {}) if po_full else {}
        po_party = po_extracted.get("party_names", {})
        po_vendor = po_party.get("vendor", "") or po_party.get("party_1", "") or po_match.get("vendor", "")

        if not _vendor_match(invoice_vendor, po_vendor):
            msg = f"Vendor mismatch: Invoice vendor '{invoice_vendor}' does not match PO vendor '{po_vendor}'. Invoice cannot be processed."
            print(f"[PO_MATCHER] {msg}")
            notifications.append({
                "type": "error",
                "title": "Vendor Mismatch",
                "detail": f"Invoice vendor '{invoice_vendor}' does not match PO vendor '{po_vendor}'. Invoice cannot be processed until vendor details match."
            })
            if isinstance(po_match, dict):
                po_match["_grn_matched"] = False
                po_match["_grn_data"] = None
            return False, po_match, msg, notifications

        notifications.append({
            "type": "success",
            "title": "Vendor Matched",
            "detail": f"Invoice vendor '{invoice_vendor}' matches PO vendor '{po_vendor}'."
        })

        # ── Step 3: GRN check ──
        if not po_number:
            notifications.append({
                "type": "warning",
                "title": "PO Number Missing",
                "detail": "PO matched by details but PO number could not be determined for GRN lookup."
            })
            return False, po_match, "PO matched but could not determine PO number for GRN check.", notifications

        grn_match = self.cache_manager.find_grn_by_po_number(po_number)

        po_items = po_extracted.get("line_items", [])

        if grn_match:
            # ── 3-way: Invoice vs GRN ──
            print(f"[PO_MATCHER] Found GRN for PO {po_number}: {grn_match.get('filename')}")
            grn_full = grn_match.get("full_data", {}) or {}
            grn_extracted = grn_full.get("extracted_data", {}) if grn_full else {}
            grn_items = grn_extracted.get("line_items", [])

            notifications.append({
                "type": "info",
                "title": "GRN Found",
                "detail": f"GRN '{grn_match.get('filename', '')}' found for PO '{po_number}'. Matching invoice quantities against GRN (received quantities)."
            })

            item_issues = _match_line_items(invoice_items, grn_items, "GRN")
            if item_issues:
                detail_text = "Invoice matched against GRN (received goods). Issues:\n" + "\n".join(f"  - {i}" for i in item_issues)
                notifications.append({
                    "type": "warning",
                    "title": "Invoice-GRN Quantity Mismatch",
                    "detail": detail_text
                })
                if isinstance(po_match, dict):
                    po_match["_grn_matched"] = True
                    po_match["_grn_data"] = grn_match
                    po_match["_item_issues"] = item_issues
                msg = f"PO + GRN found for '{po_number}' but invoice items/quantities do not match GRN. {'; '.join(item_issues)}"
                return False, po_match, msg, notifications
            else:
                notifications.append({
                    "type": "success",
                    "title": "3-Way Match Successful",
                    "detail": f"Invoice matched with PO '{po_number}' and GRN '{grn_match.get('filename', '')}'. All quantities and items verified against GRN. Ready for payment."
                })
                if isinstance(po_match, dict):
                    po_match["_grn_matched"] = True
                    po_match["_grn_data"] = grn_match
                return True, po_match, f"Matched (PO + GRN): {po_number}. Ready for payment.", notifications
        else:
            # ── 2-way: Invoice vs PO (no GRN) ──
            print(f"[PO_MATCHER] No GRN found for PO {po_number}, falling back to 2-way match (Invoice vs PO)")
            notifications.append({
                "type": "warning",
                "title": "GRN Not Found",
                "detail": f"No GRN uploaded for PO '{po_number}'. Matching invoice quantities against PO instead."
            })

            item_issues = _match_line_items(invoice_items, po_items, "PO")
            if item_issues:
                detail_text = "Invoice matched against PO (no GRN available). Issues:\n" + "\n".join(f"  - {i}" for i in item_issues)
                notifications.append({
                    "type": "warning",
                    "title": "Invoice-PO Quantity Mismatch",
                    "detail": detail_text
                })
                if isinstance(po_match, dict):
                    po_match["_grn_matched"] = False
                    po_match["_grn_data"] = None
                    po_match["_item_issues"] = item_issues
                msg = f"PO found for '{po_number}' but invoice items/quantities do not match PO. GRN not available. {'; '.join(item_issues)}"
                return False, po_match, msg, notifications
            else:
                notifications.append({
                    "type": "info",
                    "title": "2-Way Match (PO Only)",
                    "detail": f"Invoice quantities match PO '{po_number}'. However, GRN is not uploaded yet. Upload GRN for full 3-way verification."
                })
                if isinstance(po_match, dict):
                    po_match["_grn_matched"] = False
                    po_match["_grn_data"] = None
                return False, po_match, f"PO matched for '{po_number}' but GRN not yet uploaded. Upload GRN for 3-way match.", notifications

    def get_all_pos(self) -> Dict[str, Any]:
        return self.cache_manager.get_all_pos()

    def get_po_count(self) -> int:
        po_index = self.cache_manager.get_all_pos()
        return len(po_index)


_po_matcher_instance: Optional[POMatcher] = None


def get_po_matcher() -> POMatcher:
    global _po_matcher_instance
    if _po_matcher_instance is None:
        _po_matcher_instance = POMatcher()
    return _po_matcher_instance


def match_invoice(invoice_data: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]], str, List[Dict[str, str]]]:
    """
    Returns (matched, po_data, message, notifications).
    """
    matcher = get_po_matcher()
    return matcher.match_invoice_with_po(invoice_data)
