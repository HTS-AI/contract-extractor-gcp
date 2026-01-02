"""
Excel Export Module
Creates and updates an Excel file with extracted contract data.
"""

import os
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from zoneinfo import ZoneInfo


class ExcelExporter:
    """Handles Excel file creation and updates for contract extraction data."""
    
    def __init__(self, excel_file_path: str = "contract_extractions.xlsx"):
        """
        Initialize the Excel exporter.
        
        Args:
            excel_file_path: Path to the Excel file to create/update
        """
        self.excel_file_path = excel_file_path
        # Column order drives both Excel export and UI display
        self.columns = [
            "Extracted At",
            "Document Name",
            "ID",
            "Document Type",
            "Account Type (Head)",
            "Party Names",
            "Start Date",
            "Due Date",
            "Amount",
            "Currency",
            "Frequency",
            "Risk Score",
        ]
    
    def _format_party_names(self, party_names: Dict[str, Any]) -> str:
        """Format party names for Excel display (supports both contract and invoice formats)."""
        if not party_names:
            return ""
        
        party_list = []
        
        # For invoices: vendor and customer
        if party_names.get("vendor"):
            party_list.append(f"Vendor: {party_names['vendor']}")
        if party_names.get("customer"):
            party_list.append(f"Customer: {party_names['customer']}")
        
        # For contracts: party_1 and party_2 (only if vendor/customer not present)
        if not party_names.get("vendor") and party_names.get("party_1"):
            party_list.append(party_names["party_1"])
        if not party_names.get("customer") and party_names.get("party_2"):
            party_list.append(party_names["party_2"])
        
        # Additional parties
        if party_names.get("additional_parties"):
            for party in party_names["additional_parties"]:
                if isinstance(party, dict):
                    party_list.append(party.get("name", str(party)))
                else:
                    party_list.append(str(party))
        
        return ", ".join(party_list) if party_list else ""
    
    def _format_risk_score(self, risk_score: Any) -> str:
        """Format risk score for Excel display."""
        if not risk_score:
            return ""
        
        if isinstance(risk_score, dict):
            score = risk_score.get("score", "")
            level = risk_score.get("level", "")
            if score and level:
                return f"{score}/100 ({level})"
            elif score:
                return f"{score}/100"
            else:
                return ""
        else:
            return str(risk_score)
    
    def _format_document_ids(self, document_ids: Dict[str, Any]) -> str:
        """Format all document IDs into a single string for Excel display."""
        if not document_ids:
            return ""
        
        id_parts = []
        
        # Primary Document IDs
        if document_ids.get("invoice_id"):
            id_parts.append(f"Invoice: {document_ids['invoice_id']}")
        elif document_ids.get("invoice_number"):
            id_parts.append(f"Invoice: {document_ids['invoice_number']}")
        
        if document_ids.get("bill_number"):
            id_parts.append(f"Bill: {document_ids['bill_number']}")
        
        if document_ids.get("contract_id"):
            id_parts.append(f"Contract: {document_ids['contract_id']}")
        
        if document_ids.get("agreement_id"):
            id_parts.append(f"Agreement: {document_ids['agreement_id']}")
        
        if document_ids.get("lease_id"):
            id_parts.append(f"Lease: {document_ids['lease_id']}")
        
        if document_ids.get("nda_id"):
            id_parts.append(f"NDA: {document_ids['nda_id']}")
        
        if document_ids.get("order_number"):
            id_parts.append(f"Order: {document_ids['order_number']}")
        
        if document_ids.get("reference_id"):
            id_parts.append(f"Ref: {document_ids['reference_id']}")
        
        if document_ids.get("document_number"):
            id_parts.append(f"Doc#: {document_ids['document_number']}")
        
        # Business Transaction IDs
        if document_ids.get("po_number"):
            id_parts.append(f"PO: {document_ids['po_number']}")
        if document_ids.get("quotation_number"):
            id_parts.append(f"Quote: {document_ids['quotation_number']}")
        if document_ids.get("work_order_number"):
            id_parts.append(f"WO: {document_ids['work_order_number']}")
        if document_ids.get("project_id"):
            id_parts.append(f"Project: {document_ids['project_id']}")
        if document_ids.get("file_number"):
            id_parts.append(f"File: {document_ids['file_number']}")
        
        # Indian Tax/Registration IDs
        if document_ids.get("gst_number"):
            id_parts.append(f"GST: {document_ids['gst_number']}")
        if document_ids.get("pan_number"):
            id_parts.append(f"PAN: {document_ids['pan_number']}")
        if document_ids.get("cin_number"):
            id_parts.append(f"CIN: {document_ids['cin_number']}")
        if document_ids.get("tan_number"):
            id_parts.append(f"TAN: {document_ids['tan_number']}")
        
        # Financial IDs
        if document_ids.get("payment_reference"):
            id_parts.append(f"Payment Ref: {document_ids['payment_reference']}")
        if document_ids.get("transaction_id"):
            id_parts.append(f"Transaction: {document_ids['transaction_id']}")
        if document_ids.get("receipt_number"):
            id_parts.append(f"Receipt: {document_ids['receipt_number']}")
        if document_ids.get("bank_reference"):
            id_parts.append(f"Bank Ref: {document_ids['bank_reference']}")
        
        # Compliance/Certification IDs
        if document_ids.get("certificate_number"):
            id_parts.append(f"Certificate: {document_ids['certificate_number']}")
        if document_ids.get("license_number"):
            id_parts.append(f"License: {document_ids['license_number']}")
        if document_ids.get("authorization_number"):
            id_parts.append(f"Authorization: {document_ids['authorization_number']}")
        if document_ids.get("approval_number"):
            id_parts.append(f"Approval: {document_ids['approval_number']}")
        
        # Other IDs (catch-all)
        if document_ids.get("other_ids"):
            for other_id in document_ids["other_ids"]:
                id_parts.append(str(other_id))
        
        return "; ".join(id_parts) if id_parts else ""
    
    def _format_compliance_violation(self, violation: Any) -> str:
        """Format compliance violation for Excel display."""
        if not violation:
            return ""
        
        violation_str = str(violation)
        # Truncate if too long for Excel cell
        if len(violation_str) > 32767:  # Excel cell limit
            violation_str = violation_str[:32700] + "..."
        
        return violation_str
    
    def create_or_update_excel(self, extracted_data: Dict[str, Any], file_name: str) -> bool:
        """
        Create or update Excel file with extracted contract data.
        
        Args:
            extracted_data: Extracted contract data dictionary
            file_name: Name of the uploaded document file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            print(f"[EXCEL] Starting export for '{file_name}'")
            print(f"[EXCEL] Target path: {os.path.abspath(self.excel_file_path)}")
            # Format document IDs into a single string
            document_ids_str = self._format_document_ids(extracted_data.get("document_ids", {}))
            # Use Qatar time (Asia/Qatar) for Extracted At
            try:
                # Store as tz-naive string to avoid tz-aware/naive mixing in pandas
                extracted_at = datetime.now(ZoneInfo("Asia/Qatar")).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                extracted_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                print("[EXCEL] Warning: ZoneInfo Asia/Qatar unavailable, using UTC fallback (tz-naive)")
            
            # Prepare row data (aligned to column order)
            row_data = {
                "Extracted At": extracted_at,
                "Document Name": file_name,
                "ID": document_ids_str,
                "Document Type": extracted_data.get("document_type", ""),
                "Account Type (Head)": extracted_data.get("account_type", ""),
                "Party Names": self._format_party_names(extracted_data.get("party_names", {})),
                "Start Date": extracted_data.get("start_date", ""),
                "Due Date": extracted_data.get("due_date", ""),
                "Amount": extracted_data.get("amount", ""),
                "Currency": extracted_data.get("currency", ""),
                "Frequency": extracted_data.get("frequency") or "1",  # Default to "1" if empty
                "Risk Score": self._format_risk_score(extracted_data.get("risk_score")),
            }
            
            # Check if Excel file exists
            if os.path.exists(self.excel_file_path):
                print("[EXCEL] Existing file found, attempting to read")
                # Read existing Excel file. Force all columns to string to avoid tz-aware mixing.
                try:
                    df = pd.read_excel(self.excel_file_path, dtype=str)
                    if "Extracted At" in df.columns:
                        df["Extracted At"] = df["Extracted At"].astype(str)
                    print(f"[EXCEL] Existing rows: {len(df)}")
                except Exception as e:
                    print(f"Warning: Could not read existing Excel file: {e}. Creating new file.")
                    df = pd.DataFrame(columns=self.columns)
            else:
                print("[EXCEL] No existing file. Creating new workbook")
                # Create new DataFrame with columns
                df = pd.DataFrame(columns=self.columns)
            
            # Append new row
            new_row = pd.DataFrame([row_data])
            df = pd.concat([df, new_row], ignore_index=True)
            print(f"[EXCEL] Added new row. Total rows now: {len(df)}")

            # Ensure columns are present and in the desired order for both Excel and UI
            for col in self.columns:
                if col not in df.columns:
                    df[col] = ""
            df = df[self.columns]
            
            # Force all columns to string to avoid tz-aware/naive conflicts
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            # Save to Excel with proper datetime formatting
            with pd.ExcelWriter(self.excel_file_path, engine='openpyxl', datetime_format='YYYY-MM-DD HH:MM:SS') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                
                # Get the worksheet and set column width for better visibility
                worksheet = writer.sheets['Sheet1']
                # Set 'Extracted At' column width (column A) to 20 characters
                worksheet.column_dimensions['A'].width = 20
            
            print(f"[EXCEL] Excel file updated: {self.excel_file_path}")
            return True
            
        except ImportError:
            print("Warning: pandas or openpyxl not installed. Cannot export to Excel.")
            print("Please install: pip install pandas openpyxl")
            return False
        except Exception as e:
            print(f"[EXCEL] Error updating Excel file: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_excel_path(self) -> str:
        """Get the path to the Excel file."""
        return os.path.abspath(self.excel_file_path)


def update_contract_excel(extracted_data: Dict[str, Any], file_name: str, excel_file_path: str = "contract_extractions.xlsx") -> bool:
    """
    Convenience function to update Excel file with extracted contract data.
    
    Args:
        extracted_data: Extracted contract data dictionary
        file_name: Name of the uploaded document file
        excel_file_path: Path to the Excel file (default: "contract_extractions.xlsx")
        
    Returns:
        True if successful, False otherwise
    """
    exporter = ExcelExporter(excel_file_path)
    return exporter.create_or_update_excel(extracted_data, file_name)

