"""
Expense Chatbot — Q&A over human-verified cash bill / expense data.

Reads from the expense store (which contains HITL-edited records) so answers
always reflect the latest human-corrected values.

Uses the same LangChain + FAISS + GPT-4o-mini stack as the Invoice-to-AP chatbot
but is completely separate.
"""

import os
import re
import json
import uuid
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS


EXPENSE_SYSTEM_PROMPT = """You are an intelligent expense data assistant.
You have access to cash bill and expense records that have been extracted from receipts,
invoices, and quotations, then verified and corrected by a human reviewer.

Your capabilities:
- Answer questions about specific expenses (vendor, amounts, dates, line items)
- Compute totals, averages, and summaries across multiple expenses
- Filter and group expenses by vendor, date range, payment method, currency, etc.
- Identify patterns (e.g., most frequent vendor, highest expense)
- Flag missing or unusual data (e.g., bills with no VAT, zero amounts)

IMPORTANT INSTRUCTIONS:
- All expense amounts use 3 decimal places (Omani Rial / OMR format)
- Search ALL provided context chunks thoroughly before answering
- When asked about totals, sum the relevant amounts precisely
- If asked about a vendor, match by partial name too (e.g., "Omanoil" matches "Oman Oil Company")
- Provide specific numbers, dates, and details — not vague summaries
- If you cannot find the information, say so clearly

RESPONSE FORMAT — STRICT (plain text only):
- Do NOT use markdown: no asterisks, no bold, no bullet points with **
- Use plain conversational text with line breaks for readability
- For lists, use simple labels and line breaks
- Be concise but thorough"""


def _expense_to_text(record: Dict[str, Any]) -> str:
    """Convert a single expense record to searchable text."""
    parts = [f"--- Expense: {record.get('expense_id', 'unknown')} ---"]

    if record.get("document_name"):
        parts.append(f"Document: {record['document_name']}")
    if record.get("document_type"):
        parts.append(f"Type: {record['document_type']}")
    if record.get("vendor"):
        parts.append(f"Vendor: {record['vendor']}")
    if record.get("vendor_address"):
        parts.append(f"Address: {record['vendor_address']}")
    if record.get("receipt_no") or record.get("invoice_no"):
        parts.append(f"Receipt/Invoice No: {record.get('receipt_no') or record.get('invoice_no')}")
    if record.get("receipt_date"):
        parts.append(f"Date: {record['receipt_date']}")
    if record.get("receipt_time"):
        parts.append(f"Time: {record['receipt_time']}")
    if record.get("site_vat_no"):
        parts.append(f"VAT Number: {record['site_vat_no']}")
    if record.get("cr_no"):
        parts.append(f"C.R. No: {record['cr_no']}")
    if record.get("customer_name"):
        parts.append(f"Customer: {record['customer_name']}")
    if record.get("site_name"):
        parts.append(f"Site: {record['site_name']}")

    items = record.get("line_items") or []
    if items:
        parts.append("Line Items:")
        for i, it in enumerate(items, 1):
            if not isinstance(it, dict):
                continue
            desc = it.get("description", "")
            qty = it.get("qty", "")
            unit = it.get("unit", "")
            up = it.get("unit_price", "")
            amt = it.get("amount", "")
            parts.append(f"  {i}. {desc} | Qty: {qty} {unit} | Unit Price: {up} | Amount: {amt}")

    currency = record.get("currency", "OMR")
    if record.get("subtotal") is not None:
        parts.append(f"Subtotal: {record['subtotal']} {currency}")
    if record.get("vat_rate") is not None:
        parts.append(f"VAT Rate: {record['vat_rate']}%")
    if record.get("vat_amount") is not None:
        parts.append(f"VAT Amount: {record['vat_amount']} {currency}")

    total = record.get("total_amount") or record.get("amount")
    if total is not None:
        parts.append(f"Total Amount: {total} {currency}")

    if record.get("payment_method"):
        parts.append(f"Payment: {record['payment_method']}")
    if record.get("plate_number"):
        parts.append(f"Plate/Vehicle: {record['plate_number']}")
    if record.get("pump_no"):
        parts.append(f"Pump: {record['pump_no']}")
    if record.get("extracted_at"):
        parts.append(f"Extracted At: {record['extracted_at']}")

    return "\n".join(parts)


def _build_summary(expenses: List[Dict[str, Any]]) -> str:
    """Build a global summary block so the LLM knows the full dataset shape."""
    total_amt = 0.0
    vendors = set()
    currencies = set()
    for r in expenses:
        amt = r.get("total_amount") or r.get("amount")
        if amt is not None:
            try:
                total_amt += float(amt)
            except (ValueError, TypeError):
                pass
        v = r.get("vendor")
        if v:
            vendors.add(v)
        c = r.get("currency")
        if c:
            currencies.add(c)

    return (
        f"=== EXPENSE DATA SUMMARY ===\n"
        f"Total records: {len(expenses)}\n"
        f"Combined amount: {total_amt:.3f} {', '.join(sorted(currencies)) or 'OMR'}\n"
        f"Unique vendors: {len(vendors)} ({', '.join(sorted(vendors))})\n"
        f"============================\n"
    )


class ExpenseChatbot:
    """Chatbot for querying human-verified expense data."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for the expense chatbot.")

        self.llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=self.api_key)
        self.embeddings = OpenAIEmbeddings(api_key=self.api_key)
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def start_session(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create or refresh a session by loading all expense records from the store,
        converting to text, chunking, and building a FAISS index.
        """
        from cashbill_expense.store import get_expense_store

        sid = session_id or str(uuid.uuid4())
        expenses = get_expense_store()

        if not expenses:
            return {"success": False, "error": "No expense records found. Upload some cash bills first."}

        text_blocks = [_build_summary(expenses)]
        for record in expenses:
            text_blocks.append(_expense_to_text(record))

        combined_text = "\n\n".join(text_blocks)

        splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=200)
        chunks = splitter.split_text(combined_text)

        if not chunks:
            return {"success": False, "error": "Failed to process expense data."}

        vectorstore = FAISS.from_texts(chunks, self.embeddings)

        all_data_json = json.dumps(expenses, indent=2, default=str)

        self.sessions[sid] = {
            "vectorstore": vectorstore,
            "chunk_texts": chunks,
            "all_data_json": all_data_json[:60000],
            "record_count": len(expenses),
        }

        return {
            "success": True,
            "session_id": sid,
            "record_count": len(expenses),
            "chunks": len(chunks),
        }

    def ask(self, session_id: str, question: str) -> Dict[str, Any]:
        """Answer a question using retrieval over the expense data."""
        if session_id not in self.sessions:
            return {"success": False, "error": "Session not found. Please start a session first."}

        session = self.sessions[session_id]
        vectorstore = session["vectorstore"]

        try:
            relevant_docs = vectorstore.similarity_search(question, k=10)

            question_lower = question.lower()
            stop_words = {
                "the", "is", "are", "what", "which", "when", "where", "who", "how",
                "does", "do", "did", "has", "have", "had", "was", "were", "will",
                "would", "can", "could", "should", "may", "might", "must", "about",
                "with", "from", "for", "and", "or", "but", "not", "this", "that",
                "these", "those", "a", "an", "of", "to", "in", "on", "at", "by", "as",
                "me", "my", "all", "show", "tell", "give", "list", "much", "many",
            }
            terms = [
                t.strip(".,!?;:()[]{}\"'")
                for t in question_lower.split()
                if len(t.strip(".,!?;:()[]{}\"'")) > 2
                and t.strip(".,!?;:()[]{}\"'") not in stop_words
            ]

            if terms:
                from langchain_core.documents import Document
                existing = {doc.page_content[:100] for doc in relevant_docs}
                for chunk_text in session.get("chunk_texts", []):
                    cl = chunk_text.lower()
                    if sum(1 for t in terms if t in cl) > 0 and chunk_text[:100] not in existing:
                        relevant_docs.append(Document(page_content=chunk_text))
                        existing.add(chunk_text[:100])
                        if len(relevant_docs) >= 15:
                            break

            context = "\n\n".join(doc.page_content for doc in relevant_docs)

            needs_full = any(
                kw in question_lower
                for kw in ["total", "sum", "all", "how many", "count", "average", "every", "each"]
            )
            data_context = ""
            if needs_full:
                data_context = (
                    "\n\nFULL EXPENSE DATA (JSON — use for calculations):\n"
                    + session["all_data_json"]
                )

            user_prompt = (
                f"EXPENSE RECORDS CONTEXT:\n{context}{data_context}\n\n"
                f"QUESTION: {question}\n\nANSWER:"
            )

            response = self.llm.invoke([
                SystemMessage(content=EXPENSE_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ])

            answer = response.content or ""
            answer = self._clean_answer(answer)

            return {"success": True, "answer": answer}

        except Exception as e:
            print(f"[EXPENSE-CHAT] Error: {e}")
            return {"success": False, "error": f"Error processing question: {e}"}

    def refresh_session(self, session_id: str) -> Dict[str, Any]:
        """Rebuild the index for an existing session from latest store data."""
        if session_id not in self.sessions:
            return self.start_session(session_id)
        return self.start_session(session_id)

    @staticmethod
    def _clean_answer(text: str) -> str:
        if not text:
            return text
        out = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
        out = re.sub(r"\*([^*]*)\*", r"\1", out)
        return out.strip()
