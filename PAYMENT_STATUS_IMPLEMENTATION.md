# Payment Status Table – Explanation

## Reference: how the invoice payment table looks

The target **Invoice Details / payment table** is an AP-style view with:

- **Header**: Title (“Invoice Details”), Help, **filters** (e.g. All / Due Date range), and **Select / Deselect** for rows.
- **Columns**:
  - **Selected** – checkboxes to select invoices (e.g. for batch payment or export).
  - **Disputed** – dispute status (e.g. New Dispute Issued, Open, Dispute Cleared); can be links to open/clear disputes.
  - **Credit/Debit** – credit or debit indicator if applicable.
  - **Printed** – whether the invoice has been printed (if you track that).
  - **Account Type Desc** – payment/account status text, e.g. **UNPAID - PAST DUE**, **UNPAID - CURRENT**, **BALANCE DUE - PAST DUE**.
  - **Aging Desc** – aging bucket (e.g. **91+**, **0–15** days).
  - **Invoice #** – invoice number (often a link to details).
  - **Inv Date** – invoice date.
  - **Due Date** – payment due date.
  - **Billed Amount** – total invoice amount.
  - **Amt Rec** – amount received (payments applied).
  - **Bal Due** – balance due (billed minus received).
- **Totals row** – sum of Billed Amount, Amount Received, and Balance Due.
- **Pagination** – e.g. “Page 1 of 1” when all rows fit on one page.

So the payment table is **invoice-centric**, with focus on **payment state** (unpaid/balance due, past due/current), **aging**, **amounts** (billed, received, balance due), and **disputes**, plus selection and totals. Your app’s three-way match (Ready for payment / Pending) can map into “Account Type Desc” or an extra column (e.g. **Match status**).

---

## Yes: the payment table is different from existing tables

Your app already has several lists/tables. A **payment status table** is a separate, dedicated view for “who can be paid” and “who has been paid,” in the style of the reference above. Here’s how it differs from what you have now.

---

## Existing tables/views in your app

| What exists                                  | Purpose                                      | What it shows                                                                                             |
| -------------------------------------------- | -------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| **Extraction list / dropdown**               | Choose a document to view extraction results | All extracted documents (invoices, etc.) by file name and date.                                           |
| **Dashboard (matched / not matched)**        | High-level counts                            | Total invoices, POs, GRNs, and how many invoices are three-way matched vs not.                            |
| **Match status (buyer portal)**              | PO-centric “ready vs pending”                | One block per PO: “Ready for payment” (PO + GRN + Invoice) or “Pending” (missing GRN or Invoice).         |
| **Excel export (contract_extractions.xlsx)** | Export for downstream use                    | Only **matched** invoices (three-way) are written to Excel; each row is one invoice with matched PO info. |

None of these is a single, dedicated **invoice payment table** like the reference: row-per-invoice with dispute, account type, aging, dates, billed/received/balance due, selection, and totals.

---

## What a payment status table is (and how it’s different)

A **payment status table** in the style of your reference is:

- **Invoice-centric**: one row per invoice.
- **Columns** aligned with the reference: Selected, Disputed, Account Type Desc (e.g. UNPAID - PAST DUE, UNPAID - CURRENT, BALANCE DUE - PAST DUE), Aging Desc, Invoice #, Inv Date, Due Date, Billed Amount, Amt Rec, Bal Due. You can add **Match status** (Ready for payment / Pending) from your three-way match.
- **Totals row** for Billed Amount, Amount Received, Balance Due.
- **Filters** (e.g. All, Due Date range) and **Select / Deselect** for batch actions.

So:

- **Different from the extraction list**: The extraction list is “all documents we extracted.” The payment table is “invoices only” with payment state, aging, and amounts.
- **Different from the dashboard**: The dashboard is **summary numbers**. The payment table is **row-by-row** with full payment and dispute info.
- **Different from buyer portal match status**: That view is **PO-centric** cards. The payment table is **invoice-centric** with columns like the reference.
- **Different from Excel**: Excel is an export of matched invoices. The payment table is a **live view** of all invoices with status, amounts, and totals.

---

## What the payment table would contain (aligned with the reference)

- **Selected** – checkbox per row.
- **Disputed** – dispute status (e.g. New Dispute Issued, Open, Dispute Cleared); requires dispute tracking if you add it.
- **Credit/Debit** – optional.
- **Printed** – optional, if you track it.
- **Account Type Desc** – derived from due date and balance: e.g. UNPAID - PAST DUE, UNPAID - CURRENT, BALANCE DUE - PAST DUE (and later PAID when you track payments).
- **Aging Desc** – aging bucket (e.g. 91+, 31–60, 0–15) from due date vs today.
- **Invoice #** – from extraction (document_ids).
- **Inv Date** – start_date / invoice date from extraction.
- **Due Date** – due_date from extraction.
- **Billed Amount** – amount from extraction.
- **Amt Rec** – amount received (needs payment/application data if you track it; otherwise 0).
- **Bal Due** – Billed Amount minus Amt Rec (or Billed Amount when no payments tracked).
- **Match status** (optional extra column) – Ready for payment (three-way match) / Pending, from `_po_match.matched`.

**Totals row**: Sum Billed Amount, Amt Rec, Bal Due across visible rows.

**Header**: Filters (e.g. All, Due Date range), Select / Deselect.

The data for invoice #, dates, amount, and three-way match already exists in your extractions. Aging and “Account Type Desc” can be derived from due date. Dispute, Amt Rec, and Printed would need to be added if you want those columns.

---

## Summary

- The **payment table** should look like your reference: invoice-centric, with Selected, Disputed, Account Type Desc, Aging, Invoice #, dates, Billed Amount, Amt Rec, Bal Due, totals, and filters.
- It is **not** the same as: extraction list, dashboard counts, buyer portal match cards, or Excel export.
- Implementing it means adding this as a **new** screen or section (and an API that returns these rows), without changing existing tables.
