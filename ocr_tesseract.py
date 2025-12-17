"""
Local OCR using Tesseract (free alternative to Google Cloud Vision)
"""
import os
from pathlib import Path
from typing import Tuple, Dict

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    pytesseract = None
    convert_from_path = None


def ocr_pdf_with_tesseract(pdf_path: str) -> Tuple[str, Dict[int, str]]:
    """
    Extract text from image-based PDF using Tesseract OCR.
    
    Args:
        pdf_path: Path to PDF file
        
    Returns:
        Tuple of (full_text, page_map)
    """
    if not TESSERACT_AVAILABLE:
        raise ImportError(
            "Tesseract OCR is not available. Please install:\n"
            "1. pip install pytesseract pdf2image Pillow\n"
            "2. Install Tesseract executable:\n"
            "   - Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
            "   - Set path: pytesseract.pytesseract.tesseract_cmd = r'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'"
        )
    
    # Set Tesseract path (adjust if installed elsewhere)
    if os.name == 'nt':  # Windows
        possible_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\Admin\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        ]
        for path in possible_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break
    
    print(f"Converting PDF to images for OCR: {Path(pdf_path).name}")
    
    # Convert PDF pages to images
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as e:
        raise ValueError(f"Failed to convert PDF to images: {str(e)}")
    
    print(f"Extracted {len(images)} pages, performing OCR...")
    
    # Extract text from each image
    page_map = {}
    text_parts = []
    
    for page_num, image in enumerate(images, start=1):
        try:
            # Perform OCR on the image
            text = pytesseract.image_to_string(image, lang='eng')
            page_map[page_num] = text
            text_parts.append(text)
            print(f"  Page {page_num}: Extracted {len(text)} characters")
        except Exception as e:
            print(f"  ⚠️ Page {page_num}: OCR failed - {str(e)}")
            page_map[page_num] = ""
            text_parts.append("")
    
    full_text = '\n\n'.join(text_parts)
    print(f"✓ OCR complete: Total {len(full_text)} characters extracted")
    
    return full_text, page_map


def check_tesseract_installation():
    """Check if Tesseract is properly installed."""
    if not TESSERACT_AVAILABLE:
        return False, "Python packages not installed (pytesseract, pdf2image, Pillow)"
    
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract {version} is installed"
    except Exception as e:
        return False, f"Tesseract executable not found: {str(e)}"


if __name__ == "__main__":
    # Check installation
    installed, message = check_tesseract_installation()
    print("="*80)
    print("TESSERACT OCR CHECK")
    print("="*80)
    print(f"Status: {'✓ INSTALLED' if installed else '❌ NOT INSTALLED'}")
    print(f"Message: {message}")
    print("="*80)
    
    if installed:
        # Test on construction invoice
        pdf_path = r"c:\Users\Admin\Account_payable\invoices\construction-invoice-template-1x-1-compressed.pdf"
        print(f"\nTesting OCR on: {Path(pdf_path).name}")
        try:
            full_text, page_map = ocr_pdf_with_tesseract(pdf_path)
            print(f"\n--- EXTRACTED TEXT (first 500 chars) ---")
            print(full_text[:500])
        except Exception as e:
            print(f"❌ Error: {e}")

