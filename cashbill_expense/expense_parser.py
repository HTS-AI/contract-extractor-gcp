"""
Parse raw OCR text from a receipt/cash bill into structured expense fields.
Extracts all common fields: vendor, address, document type, receipt/invoice numbers,
date/time, line items, subtotal, VAT, total, payment method, plate, etc.
Handles Omani Rial (RO, R.O, Bz.) with 3 decimal places, and varied bill types.
"""

import re
from typing import Dict, Any, List, Optional

# Currency: OMR/RO common in Oman; also USD, INR, etc.
CURRENCY_ALIASES = {
    "RO": "OMR", "R.O": "OMR", "R.O.": "OMR", "OMR": "OMR",
    "OMANI RIAL": "OMR", "RIYAL OMANI": "OMR", "ريال عماني": "OMR",
    "USD": "USD", "$": "USD", "INR": "INR", "Rs": "INR", "₹": "INR",
    "GBP": "GBP", "£": "GBP", "EUR": "EUR", "€": "EUR",
    "SAR": "SAR", "QAR": "QAR", "AED": "AED",
}


def _clean_unit_field(unit: Any) -> str:
    """
    Unit should be a measure (pcs, kg, lt), NOT currency.
    Strip R.O., Bz., ريال, baisa, OMR etc. If result is empty or only currency-like, return "".
    """
    if unit is None:
        return ""
    s = str(unit).strip()
    if not s:
        return ""
    cleaned = re.sub(
        r"\bR\.?O\.?\b|\bBz\.?\b|\bOMR\b|ريال|بيسة|baisa|rial|omani",
        " ", s, flags=re.I
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if re.match(r"^[A-Za-z]?\d*$", cleaned) or len(cleaned) <= 2:
        return ""
    if re.match(r"^[a-zA-Z]{1,6}$", cleaned):
        return cleaned.lower()
    return cleaned[:20] if cleaned else ""


def _infer_missing_line_item_amounts(record: Dict[str, Any]) -> None:
    """
    When line items have missing or zero unit_price/amount but we have subtotal (or total),
    infer from totals. Single line item: amount = subtotal, unit_price = subtotal / qty.
    """
    items = record.get("line_items")
    if not items or not isinstance(items, list):
        return
    subtotal = record.get("subtotal")
    if subtotal is None:
        subtotal = record.get("total_amount")
    if subtotal is None and record.get("vat_amount") is not None and record.get("total_amount") is not None:
        subtotal = round(record["total_amount"] - record["vat_amount"], 3)
    if subtotal is None:
        return
    try:
        st = float(subtotal)
    except (TypeError, ValueError):
        return
    if len(items) == 1:
        it = items[0]
        amt = it.get("amount")
        up = it.get("unit_price")
        qty_val = it.get("qty")
        try:
            qty_num = int(float(qty_val)) if qty_val is not None and str(qty_val).strip() else 0
        except (TypeError, ValueError):
            qty_num = 0
        if (amt is None or float(amt) == 0) and st > 0:
            it["amount"] = round(st, 3)
            if qty_num > 0:
                it["unit_price"] = round(st / qty_num, 3)
            elif up is not None and float(up) > 0:
                pass
            else:
                it["unit_price"] = round(st, 3)
        elif (up is None or float(up) == 0) and qty_num > 0 and st > 0:
            it["unit_price"] = round(st / qty_num, 3)
            it["amount"] = round(st, 3)
    else:
        total_filled = sum(
            float(it.get("amount") or 0) for it in items
            if it.get("amount") is not None and float(it.get("amount")) > 0
        )
        missing = [it for it in items if it.get("amount") is None or float(it.get("amount") or 0) == 0]
        if len(missing) == 1 and abs(total_filled - st) > 0.001:
            missing[0]["amount"] = round(st - total_filled, 3)
            qty_val = missing[0].get("qty")
            try:
                qty_num = int(float(qty_val)) if qty_val else 0
            except (TypeError, ValueError):
                qty_num = 0
            if qty_num > 0:
                missing[0]["unit_price"] = round(missing[0]["amount"] / qty_num, 3)


def _normalize_omr_amount(s: str) -> Optional[float]:
    """
    Parse Omani Rial amount from OCR text.
    Oman currency: 1 RO (Rial Omani) = 1000 Bz (Baisa).
    Handles formats:
      '01-300'        => 1.300  (01 RO 300 Bz, leading zero)
      '1-660'         => 1.660  (1 RO 660 Bz)
      '9-100'         => 9.100  (9 RO 100 Bz)
      '7/650'         => 7.650  (7 RO 650 Bz)
      '1 660'         => 1.660  (RO Bz split by space in OCR)
      '01 300'        => 1.300  (leading zero, space separator)
      'R.O 1 Bz 660'  => 1.660
      '9.100'         => 9.100  (already decimal)
      '245'           => 245.0  (plain number)
      '0.350'         => 0.350  (Baisa only, already decimal)
    """
    if not s or not s.strip():
        return None
    s = s.replace(",", "").strip()

    # Strip currency labels (R.O., RO, Bz., Bz, OMR) but keep the numbers
    cleaned = re.sub(r"(?:R\.?O\.?|OMR|Bz\.?|baisa|rial)", " ", s, flags=re.I).strip()
    # Collapse multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Pattern: two groups separated by dash, slash → RO and Bz
    # e.g. "1-660", "01-300", "7/650", "9-100"
    m = re.match(r"^0*(\d+)\s*[-/]\s*(\d{1,3})$", cleaned)
    if m:
        try:
            ro = int(m.group(1))
            bz = int(m.group(2))
            return round(ro + bz / 1000, 3)
        except ValueError:
            pass

    # Pattern: "1 660" or "01 300" — RO then Bz separated by space (Bz is 1-3 digits)
    m = re.match(r"^0*(\d+)\s+(\d{1,3})$", cleaned)
    if m:
        try:
            ro = int(m.group(1))
            bz = int(m.group(2))
            return round(ro + bz / 1000, 3)
        except ValueError:
            pass

    # Pattern: already a proper decimal like "1.660" or "0.350" or "9.100"
    m = re.match(r"^(\d+\.\d+)$", cleaned)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Pattern: plain integer like "245" or "01" (just Rial, no Baisa)
    m = re.match(r"^0*(\d+)$", cleaned)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass

    # Fallback: extract all digits and dots
    try:
        return float(re.sub(r"[^\d.]", "", cleaned) or "0")
    except ValueError:
        return None


def _parse_ro_bz_pair(text: str, label_pattern: str) -> Optional[float]:
    """
    Find a labeled amount with separate R.O and Bz columns/values.
    Handles OCR patterns like:
      "Total  R.O  1  Bz.  660"
      "Total Amount  R.O. 7  Bz 650"
      "Total R.O. ... 9-100"
      "Total  9  100"  (when RO/Bz are in adjacent cells)
    Returns combined OMR decimal value.
    """
    # Pattern 1: label ... R.O <num> Bz <num>
    pat = label_pattern + r"[:\s]*(?:R\.?O\.?|OMR)?\s*(\d+)\s+(?:Bz\.?|بيسة|baisa)\s*(\d{1,3})"
    m = re.search(pat, text, re.I)
    if m:
        try:
            ro = int(m.group(1))
            bz = int(m.group(2))
            return round(ro + bz / 1000, 3)
        except (ValueError, IndexError):
            pass

    # Pattern 2: label ... <num>-<num> (dash-separated RO-Bz near the label)
    pat2 = label_pattern + r"[\s.:]*(?:R\.?O\.?)?\s*(\d+)\s*[-/]\s*(\d{1,3})"
    m = re.search(pat2, text, re.I)
    if m:
        try:
            ro = int(m.group(1))
            bz = int(m.group(2))
            return round(ro + bz / 1000, 3)
        except (ValueError, IndexError):
            pass

    return None


def _extract_currency(text: str) -> str:
    for pattern, code in [
        (r"\b(?:R\.O\.?|RO|OMR|Omani\s*Rial|ريال\s*عماني)\b", "OMR"),
        (r"\bUSD\b|\$", "USD"),
        (r"\bINR\b|Rs\.?|₹", "INR"),
        (r"\bGBP\b|£", "GBP"),
        (r"\bEUR\b|€", "EUR"),
        (r"\bSAR\b", "SAR"),
        (r"\bQAR\b", "QAR"),
        (r"\bAED\b", "AED"),
    ]:
        if re.search(pattern, text, re.I):
            return code
    return "OMR"  # default for Oman bills


def _extract_dates_and_time(text: str) -> tuple:
    """
    Returns (receipt_date YYYY-MM-DD, receipt_time HH:MM:SS).
    Omani/GCC dates are DD/MM/YYYY. Prioritizes labeled dates (Date:, التاريخ:).
    """
    date_str = ""
    time_str = ""
    # Prefer labeled date (Date:, التاريخ:) to avoid picking up "No. 4852"
    for pat in [
        r"(?:date|التاريخ)\s*[:\s]*(\d{1,2})\s*[/\-]\s*(\d{1,2})\s*[/\-]\s*(\d{2,4})",
        r"(?:sale|invoice|bill)\s*(?:date)?\s*[:\s]*(\d{1,2})\s*[/\-]\s*(\d{1,2})\s*[/\-]\s*(\d{2,4})",
    ]:
        m = re.search(pat, text, re.I)
        if m:
            d, mo, y = m.groups()
            try:
                yy = int(y)
                if yy < 100:
                    yy += 2000 if yy < 50 else 1900
                date_str = f"{yy}-{mo.zfill(2)}-{d.zfill(2)}"
                break
            except (ValueError, IndexError):
                pass
    # Fallback: any DD/MM/YYYY or DD-MM-YYYY (but only if 3 segments, not 2)
    if not date_str:
        m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})\b", text)
        if m:
            d, mo, y = m.groups()
            try:
                yy = int(y)
                if yy < 100:
                    yy += 2000 if yy < 50 else 1900
                date_str = f"{yy}-{mo.zfill(2)}-{d.zfill(2)}"
            except (ValueError, IndexError):
                pass
    # Time: 14:47:58, 10:22:34
    m = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", text)
    if m:
        time_str = f"{m.group(1).zfill(2)}:{m.group(2)}:{m.group(3) or '00'}"
    return (date_str, time_str)


def _extract_vendor_and_address(text: str) -> tuple:
    """Returns (vendor_name, vendor_address). First substantial lines often vendor."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name = ""
    address_lines = []
    skip_labels = re.compile(
        r"^(total|tax|vat|date|receipt|invoice|amount|payment|plate|qty|description|s\.no|number|receiver|signature)",
        re.I,
    )
    for i, line in enumerate(lines[:20]):
        if not line or len(line) < 3:
            continue
        if re.match(r"^[\d\s\$₹£€.,\-/]+$", line):
            continue
        if skip_labels.match(line):
            continue
        # Document type lines (QUOTATION, TAX INVOICE, etc.)
        if re.search(r"simplified\s*tax\s*invoice|cash\s*/\s*credit\s*memo|quotation|tax\s*invoice|فاتورة|عرض\s*أشعار", line, re.I):
            if not name and i > 0:
                name = lines[i - 1][:200]
            continue
        # Skip "Accredited Supplier" taglines — but they confirm the vendor
        if re.search(r"accredited|supplier|fire\s*alarm|security|safety|equipment", line, re.I):
            continue
        # Skip Mr./M/s., Address: label lines
        if re.search(r"^(?:Mr\.?|M/?s\.?|Address|العنوان|الأفاضل|الفاضل)", line, re.I):
            continue
        # Skip "No. XXXX" lines
        if re.match(r"^No\.?\s*\d+", line, re.I):
            continue
        if not name and len(line) > 4:
            name = line[:200]
            continue
        # Address components: P.O. Box, Tel, Fax, Email, C.R., Sultanate, etc.
        if name and (
            re.search(
                r"p\.?o\.?\s*box|postal|tel|fax|gsm|mob|e-?mail|sultanate|oman|sohar|muscat|salalah|"
                r"الغبرة|ص\.?ب|هاتف|C\.?R\.?\s*NO|@|\.\s*com",
                line, re.I,
            )
            or "," in line
        ):
            address_lines.append(line[:200])

    # Also extract email explicitly
    m = re.search(r"[Ee]-?mail\s*[:\s]*(\S+@\S+)", text)
    if m:
        email = m.group(1).strip()
        if email and not any(email in al for al in address_lines):
            address_lines.append(f"Email: {email}")

    address = " | ".join(address_lines[:6]) if address_lines else ""
    return (name or (lines[0][:200] if lines else ""), address)


def _extract_document_type(text: str) -> str:
    if re.search(r"simplified\s*tax\s*invoice", text, re.I):
        return "Simplified Tax Invoice"
    if re.search(r"cash\s*/\s*credit\s*memo|فاتورة نقدية", text, re.I):
        return "CASH/CREDIT MEMO"
    if re.search(r"quotation|عرض\s*أشعار", text, re.I):
        return "QUOTATION"
    if re.search(r"tax\s*invoice|فاتورة ضريبية", text, re.I):
        return "TAX INVOICE"
    return ""


def _extract_receipt_and_site(text: str) -> Dict[str, str]:
    out = {}
    # Receipt No / Invoice No / Quotation No
    for label, key in [
        (r"receipt\s*no\.?\s*[:\s]*(\d+)", "receipt_no"),
        (r"invoice\s*no\.?\s*[:\s]*(\d+)", "invoice_no"),
        (r"quotation\s*no\.?\s*[:\s]*(\d+)", "receipt_no"),
        (r"(?:bill|memo)\s*no\.?\s*[:\s]*(\d+)", "receipt_no"),
        (r"^No\.?\s*[:\s]*(\d{3,})", "receipt_no"),
        (r"\bNo\.?\s+(\d{4,})\b", "receipt_no"),
    ]:
        m = re.search(label, text, re.I | re.M)
        if m and not out.get(key):
            out[key] = m.group(1).strip()
    # C.R. NO / Commercial Registration
    m = re.search(r"C\.?R\.?\s*(?:NO|Number)?\.?\s*[:\s]*(\d+)", text, re.I)
    if m:
        out["cr_no"] = m.group(1).strip()
    # Site VAT NO / VATIN
    m = re.search(r"(?:site\s*)?vat\s*(?:no\.?|number|in)?\s*[:\s]*([OM\d\s]+)", text, re.I)
    if m:
        out["site_vat_no"] = re.sub(r"\s+", "", m.group(1))
    m = re.search(r"VATIN\s*[:\s]*([OM\s\d]+)", text, re.I)
    if m:
        out["site_vat_no"] = re.sub(r"\s+", "", m.group(1))
    # Site name / location
    m = re.search(r"site[\s/:]+([A-Z0-9\s]+?)(?:\s*\d{5,}|$|pump)", text, re.I)
    if m:
        out["site_name"] = m.group(1).strip()[:80]
    # Site code
    m = re.search(r"(?:site\s*code|code)\s*[:\s]*(\d+)", text, re.I)
    if m:
        out["site_code"] = m.group(1)
    # Pump No
    m = re.search(r"pump\s*no\.?\s*[:\s]*(\d+)", text, re.I)
    if m:
        out["pump_no"] = m.group(1)
    return out


def _extract_totals(text: str) -> Dict[str, Any]:
    """
    Extract subtotal, vat_rate, vat_amount, total.
    Handles Omani currency: RO (Rial Omani) and Bz (Baisa). 1 RO = 1000 Bz.
    Both are numerical currency units (like Dollar and Cent).
    """
    text_clean = text.replace(",", "")
    out = {"subtotal": None, "vat_rate": None, "vat_amount": None, "total_amount": None}

    # VAT rate: 5%, 5.00
    m = re.search(r"vat\s*(\d+(?:\.\d+)?)\s*%", text, re.I)
    if m:
        try:
            out["vat_rate"] = float(m.group(1))
        except ValueError:
            pass

    # --- Total Amount ---
    # First try "Total R.O <num> Bz <num>" or "Total ... 9-100" pattern
    val = _parse_ro_bz_pair(text_clean, r"(?:grand\s*)?total(?:\s*(?:amount|r\.?o\.?))?")
    if val is not None:
        out["total_amount"] = val

    if out["total_amount"] is None:
        for label in [
            r"total\s*(?:amount|r\.?o\.?)\s*[:\s.]*([\d]+\s*[-/]\s*[\d]{1,3})",
            r"total\s*[:\s.]*([\d]+\s*[-/]\s*[\d]{1,3})",
            r"total\s*(?:amount|r\.?o\.?)\s*[:\s.]*([\d.]+)",
            r"grand\s*total\s*[:\s.]*([\d.\-/]+)",
            r"total\s*[:\s.]*([\d.]+)",
            r"(?<!actual\s)amount\s*[:\s.]*([\d.\-/]+)",
            r"(\d+[-/]\d{1,3})\s*(?:R\.?O\.?|RO|OMR)",
            r"(\d+\.\d{3})\s*(?:R\.?O\.?|RO|OMR)",
        ]:
            m = re.search(label, text_clean, re.I)
            if m:
                val = _normalize_omr_amount(m.group(1))
                if val is not None and val > 0:
                    out["total_amount"] = val
                    break

    # --- VAT Amount ---
    val = _parse_ro_bz_pair(text_clean, r"vat(?:\s*amount)?")
    if val is not None:
        out["vat_amount"] = val

    if out["vat_amount"] is None:
        m = re.search(r"vat\s*amount\s*[:\s]*([\d.\-/]+)", text_clean, re.I)
        if m:
            out["vat_amount"] = _normalize_omr_amount(m.group(1))
    if out["vat_amount"] is None:
        m = re.search(r"vat\s*\d*%?\s*[:\s]*([\d.\-/]+)", text_clean, re.I)
        if m:
            out["vat_amount"] = _normalize_omr_amount(m.group(1))

    # --- Subtotal ---
    val = _parse_ro_bz_pair(text_clean, r"sub\s*total")
    if val is not None:
        out["subtotal"] = val

    if out["subtotal"] is None:
        val = _parse_ro_bz_pair(text_clean, r"actual\s*amount")
        if val is not None:
            out["subtotal"] = val

    if out["subtotal"] is None and out["total_amount"] is not None and out["vat_amount"] is not None:
        out["subtotal"] = round(out["total_amount"] - out["vat_amount"], 3)

    if out["subtotal"] is None:
        m = re.search(r"sub\s*total\s*[:\s]*([\d.\-/]+)", text_clean, re.I)
        if m:
            out["subtotal"] = _normalize_omr_amount(m.group(1))
        if out["subtotal"] is None:
            m = re.search(r"actual\s*amount\s*[:\s]*([\d.\-/]+)", text_clean, re.I)
            if m:
                out["subtotal"] = _normalize_omr_amount(m.group(1))

    return out


def _extract_payment_and_plate(text: str) -> Dict[str, str]:
    out = {}
    # Explicit payment method field
    m = re.search(r"payment\s*(?:method|type)?\s*[:\s]*(\w+)", text, re.I)
    if m:
        out["payment_method"] = m.group(1).strip().upper()
    # "Mr./M/s. Cash" or "Customer: Cash" → cash payment
    if not out.get("payment_method"):
        m = re.search(r"(?:Mr\.?\s*/?\s*M/?s\.?|customer|sold\s*to)\s*[:\s.]*\b(cash)\b", text, re.I)
        if m:
            out["payment_method"] = "CASH"
    # Customer name (for "Mr./M/s." field)
    m = re.search(r"(?:Mr\.?\s*/?\s*M/?s\.?|customer)\s*[:\s.]*([^\n]{2,40})", text, re.I)
    if m:
        cust = m.group(1).strip().rstrip(".")
        if cust and len(cust) > 1:
            out["customer_name"] = cust
    # Plate / vehicle number
    m = re.search(r"plate\s*(?:no\.?|number)?\s*[:\s]*([A-Z0-9]+)", text, re.I)
    if m:
        out["plate_number"] = m.group(1).strip()
    m = re.search(r"vehicle\s*[:\s]*([A-Z0-9]+)", text, re.I)
    if m and not out.get("plate_number"):
        out["plate_number"] = m.group(1).strip()
    return out


def _extract_line_items(text: str) -> List[Dict[str, Any]]:
    """
    Extract line items from table-like content.
    Handles tables with separate R.O. and Bz. columns (common in Omani receipts),
    as well as standard decimal columns. 1 RO = 1000 Bz.
    """
    items = []
    lines = text.splitlines()
    in_table = False
    # Detect if table has separate RO/Bz columns
    has_ro_bz_cols = bool(re.search(r"R\.?O\.?\s+Bz\.?|Bz\.?\s+R\.?O\.?", text, re.I))

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Detect table header rows (English + Arabic, including common misspellings)
        if re.search(
            r"description|qty|rate|amount|unite?\s*price|total\s*amount|sl\.?\s*no|"
            r"السعر|المبلغ|الكمية|التفاصيل|الرقم|سعر\s*الوحدة|الإجمالي|التقاصيل|"
            r"R\.?O\.?\s+Bz\.?|بيسة|ريال",
            line, re.I
        ) and not re.search(r"^\d+\s+\D", line):
            in_table = True
            continue
        if in_table and (re.match(r"^\d+\s+", line) or re.search(r"\d+\.\d{3}|\d+\s*[-/]\s*\d{1,3}", line)):
            parts = re.split(r"\s{2,}|\t", line, maxsplit=6)
            if len(parts) >= 2:
                try:
                    sl_no = parts[0].strip()
                    desc = parts[1].strip() if len(parts) > 1 else ""
                    qty = parts[2].strip() if len(parts) > 2 else ""
                    rate = None
                    amt = None

                    if has_ro_bz_cols and len(parts) >= 5:
                        ro_val = parts[3].strip() if len(parts) > 3 else "0"
                        bz_val = parts[4].strip() if len(parts) > 4 else "0"
                        rate = _normalize_omr_amount(f"{ro_val}-{bz_val}")
                        if len(parts) > 6:
                            amt = _normalize_omr_amount(f"{parts[5].strip()}-{parts[6].strip()}")
                        elif len(parts) > 5:
                            amt = _normalize_omr_amount(parts[5])
                        else:
                            amt = rate
                    else:
                        rate = _normalize_omr_amount(parts[3]) if len(parts) > 3 else None
                        amt = _normalize_omr_amount(parts[4]) if len(parts) > 4 else rate

                    if desc and not re.match(r"^[\d.\-/]+$", desc):
                        items.append({
                            "sl_no": sl_no,
                            "description": desc[:200],
                            "qty": qty,
                            "unit_price": rate,
                            "amount": amt,
                        })
                except (IndexError, ValueError, TypeError):
                    pass
        if re.search(r"total\s*r\.?o|sub\s*total|vat\s*\d|المجموع", line, re.I):
            in_table = False

    # Product line (fuel receipts): Product, Unit Price, Volume
    m = re.search(r"(?:product|item)\s*[:\s]*([^\n]+?)(?:\s*unit\s*price|$)", text, re.I)
    if m:
        prod = m.group(1).strip()
        if prod and prod not in [it.get("description") for it in items]:
            up = re.search(r"unit\s*price\s*[:\s]*([\d.\-/]+)", text, re.I)
            vol = re.search(r"volume\s*[:\s]*([\d.]+)\s*(?:lt|l)?", text, re.I)
            amt = re.search(r"actual\s*amount\s*[:\s]*([\d.\-/]+)", text, re.I)
            items.insert(0, {
                "sl_no": "1",
                "description": prod[:200],
                "qty": vol.group(1) if vol else "",
                "unit": "lt" if vol else "",
                "unit_price": _normalize_omr_amount(up.group(1)) if up else None,
                "amount": _normalize_omr_amount(amt.group(1)) if amt else None,
            })
    return items


def parse_expense_from_text(raw_text: str, document_name: str = "") -> Dict[str, Any]:
    """
    Parse raw OCR text into structured expense fields.
    Returns a dict with all common cash bill fields for storage and display.
    """
    raw_text = (raw_text or "").strip()
    currency = _extract_currency(raw_text)
    receipt_date, receipt_time = _extract_dates_and_time(raw_text)
    vendor_name, vendor_address = _extract_vendor_and_address(raw_text)
    document_type = _extract_document_type(raw_text)
    receipt_site = _extract_receipt_and_site(raw_text)
    totals = _extract_totals(raw_text)
    payment_plate = _extract_payment_and_plate(raw_text)
    line_items = _extract_line_items(raw_text)

    # Clean unit field: never store currency (R.O, Bz, ريال) as unit
    for it in line_items:
        if it.get("unit"):
            it["unit"] = _clean_unit_field(it["unit"])

    # Single amount for backward compatibility and table display
    amount = totals.get("total_amount") or totals.get("subtotal")
    tax_amount = totals.get("vat_amount")
    if amount is None and line_items:
        amount = sum((item.get("amount") or 0) for item in line_items if item.get("amount"))

    # Build validation notes from consistency checks
    validation_notes_parts = []
    if amount and totals.get("subtotal") and tax_amount:
        expected = round(totals["subtotal"] + tax_amount, 3)
        if abs(expected - amount) > 0.01:
            validation_notes_parts.append(
                f"Subtotal ({totals['subtotal']}) + VAT ({tax_amount}) = {expected}, but total is {amount}"
            )
    if totals.get("vat_rate") and totals.get("subtotal") and tax_amount:
        expected_vat = round(totals["subtotal"] * totals["vat_rate"] / 100, 3)
        if abs(expected_vat - tax_amount) > 0.01:
            validation_notes_parts.append(
                f"Calculated VAT ({totals['vat_rate']}% of {totals['subtotal']}) = {expected_vat}, actual VAT = {tax_amount}"
            )

    record = {
        "document_name": document_name or "",
        "vendor": vendor_name,
        "vendor_address": vendor_address or "",
        "document_type": document_type or "",
        "receipt_no": receipt_site.get("receipt_no") or receipt_site.get("invoice_no") or "",
        "invoice_no": receipt_site.get("invoice_no") or receipt_site.get("receipt_no") or "",
        "site_vat_no": receipt_site.get("site_vat_no") or "",
        "cr_no": receipt_site.get("cr_no") or "",
        "site_name": receipt_site.get("site_name") or "",
        "site_code": receipt_site.get("site_code") or "",
        "pump_no": receipt_site.get("pump_no") or "",
        "customer_name": payment_plate.get("customer_name") or "",
        "receipt_date": receipt_date or "",
        "receipt_time": receipt_time or "",
        "line_items": line_items,
        "subtotal": totals.get("subtotal"),
        "vat_rate": totals.get("vat_rate"),
        "tax_amount": tax_amount,
        "vat_amount": tax_amount,
        "total_amount": amount,
        "amount": amount,
        "currency": currency or "OMR",
        "payment_method": payment_plate.get("payment_method") or "",
        "plate_number": payment_plate.get("plate_number") or "",
        "confidence_score": None,
        "validation_notes": "; ".join(validation_notes_parts) if validation_notes_parts else "",
        "description": raw_text[:1000] if raw_text else "",
        "raw_text": raw_text[:5000] if raw_text else "",
    }
    _infer_missing_line_item_amounts(record)
    return record
