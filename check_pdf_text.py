"""
Check what text can be extracted from a PDF
"""
import sys
import PyPDF2
from pathlib import Path

def check_pdf_text(pdf_path):
    """Check if PDF has extractable text."""
    print(f"\nAnalyzing: {Path(pdf_path).name}")
    print("="*80)
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            total_pages = len(pdf_reader.pages)
            print(f"Total Pages: {total_pages}")
            
            for page_num in range(min(3, total_pages)):  # Check first 3 pages
                page = pdf_reader.pages[page_num]
                text = page.extract_text()
                
                print(f"\n--- Page {page_num + 1} ---")
                if text and text.strip():
                    print(f"Extracted {len(text)} characters")
                    print(f"First 200 chars: {text[:200]}")
                else:
                    print("⚠️ NO TEXT FOUND - This page is likely an image/scanned")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    # Check construction invoice
    pdf_path = r"c:\Users\Admin\Account_payable\invoices\construction-invoice-template-1x-1-compressed.pdf"
    check_pdf_text(pdf_path)
    
    # Compare with lease invoice
    print("\n" + "="*80)
    print("COMPARISON WITH LEASE INVOICE:")
    print("="*80)
    pdf_path2 = r"c:\Users\Admin\Account_payable\invoices\lease_invoice_LS-2025-203.pdf"
    check_pdf_text(pdf_path2)

