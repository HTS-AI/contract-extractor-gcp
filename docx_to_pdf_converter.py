"""
DOCX to PDF Converter with Page Numbers
Converts DOCX files to PDF format with page numbers added at the bottom.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from PyPDF2 import PdfReader, PdfWriter
import io


def convert_docx_to_pdf(docx_path: str, output_pdf_path: Optional[str] = None) -> str:
    """
    Convert DOCX to PDF with page numbers.
    
    Args:
        docx_path: Path to the DOCX file
        output_pdf_path: Optional output PDF path. If None, creates temp file.
        
    Returns:
        Path to the generated PDF file
    """
    try:
        # First, convert DOCX to PDF using docx2pdf (Windows-specific)
        import platform
        
        if platform.system() == 'Windows':
            # Use docx2pdf for Windows (requires Microsoft Word)
            from docx2pdf import convert as docx2pdf_convert
            
            # Create temp file if output not specified
            if output_pdf_path is None:
                temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                output_pdf_path = temp_pdf.name
                temp_pdf.close()
            
            # Convert DOCX to PDF
            docx2pdf_convert(docx_path, output_pdf_path)
            
        else:
            # For Linux/Mac, use LibreOffice command line
            import subprocess
            
            # Create temp file if output not specified
            if output_pdf_path is None:
                temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                output_pdf_path = temp_pdf.name
                temp_pdf.close()
            
            # Try using LibreOffice
            try:
                output_dir = os.path.dirname(output_pdf_path)
                subprocess.run([
                    'libreoffice',
                    '--headless',
                    '--convert-to',
                    'pdf',
                    '--outdir',
                    output_dir,
                    docx_path
                ], check=True, capture_output=True)
                
                # LibreOffice creates PDF with same name as DOCX
                docx_filename = Path(docx_path).stem
                generated_pdf = os.path.join(output_dir, f"{docx_filename}.pdf")
                
                # Rename to desired output path
                if generated_pdf != output_pdf_path and os.path.exists(generated_pdf):
                    os.rename(generated_pdf, output_pdf_path)
                    
            except (subprocess.CalledProcessError, FileNotFoundError):
                # LibreOffice not available, use python-docx and reportlab
                output_pdf_path = convert_docx_to_pdf_manual(docx_path, output_pdf_path)
        
        # Add page numbers to the PDF
        output_pdf_with_numbers = add_page_numbers_to_pdf(output_pdf_path)
        
        # Replace original with numbered version
        if output_pdf_with_numbers != output_pdf_path:
            os.replace(output_pdf_with_numbers, output_pdf_path)
        
        return output_pdf_path
        
    except Exception as e:
        print(f"Error converting DOCX to PDF: {e}")
        # If conversion fails, return original DOCX path
        # The extraction will handle it as DOCX
        return docx_path


def convert_docx_to_pdf_manual(docx_path: str, output_pdf_path: str) -> str:
    """
    Manual DOCX to PDF conversion using python-docx and reportlab.
    This is a fallback method with basic formatting.
    
    Args:
        docx_path: Path to DOCX file
        output_pdf_path: Path for output PDF
        
    Returns:
        Path to generated PDF
    """
    from docx import Document
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    
    # Read DOCX content
    doc = Document(docx_path)
    
    # Create PDF
    pdf_doc = SimpleDocTemplate(output_pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Convert paragraphs
    for para in doc.paragraphs:
        if para.text.strip():
            p = Paragraph(para.text, styles['Normal'])
            story.append(p)
            story.append(Spacer(1, 0.2 * inch))
    
    # Build PDF
    pdf_doc.build(story)
    
    return output_pdf_path


def add_page_numbers_to_pdf(pdf_path: str) -> str:
    """
    Add page numbers to an existing PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Path to the PDF with page numbers
    """
    try:
        # Read the existing PDF
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        # Process each page
        for page_num, page in enumerate(reader.pages, start=1):
            # Create a new PDF with just the page number
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            
            # Get page dimensions
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)
            
            # Add page number at the bottom center
            can.setFont("Helvetica", 10)
            text = f"Page {page_num}"
            text_width = can.stringWidth(text, "Helvetica", 10)
            x = (page_width - text_width) / 2
            y = 30  # 30 points from bottom
            
            can.drawString(x, y, text)
            can.save()
            
            # Move to the beginning of the StringIO buffer
            packet.seek(0)
            
            # Read the page number PDF
            page_num_pdf = PdfReader(packet)
            page_num_page = page_num_pdf.pages[0]
            
            # Merge the page number onto the original page
            page.merge_page(page_num_page)
            writer.add_page(page)
        
        # Write the output to a new file
        output_path = pdf_path.replace('.pdf', '_numbered.pdf')
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        return output_path
        
    except Exception as e:
        print(f"Error adding page numbers: {e}")
        # Return original PDF if adding page numbers fails
        return pdf_path


def should_convert_to_pdf(file_path: str) -> bool:
    """
    Check if a file should be converted to PDF.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file should be converted, False otherwise
    """
    file_ext = Path(file_path).suffix.lower()
    return file_ext in ['.docx', '.doc']

