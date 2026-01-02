from google.cloud import vision_v1 as vision
from google.cloud import storage
from google.auth.exceptions import RefreshError, DefaultCredentialsError
from google.api_core import exceptions as api_exceptions
from google.oauth2 import service_account
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Reduce gRPC logging noise
logging.getLogger("google.auth.transport.grpc").setLevel(logging.WARNING)
logging.getLogger("grpc").setLevel(logging.WARNING)


def extract_text_from_vision_output(gcs_output_uri, credentials=None):
    """
    Extract text from Vision API output JSON files stored in GCS, page by page.
    
    Args:
        gcs_output_uri: GCS URI of the output folder (e.g., gs://bucket/prefix/)
        credentials: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        
    Returns:
        list: List of dictionaries, each containing:
            - 'text': Extracted text for the page
            - 'width': Page width in points
            - 'height': Page height in points
            - 'page_number': Page number (1-indexed)
    """
    logger.info("=" * 60)
    logger.info("Extracting text from Vision API output JSON files (page by page)...")
    logger.info("=" * 60)
    
    # Parse GCS URI
    parsed = urlparse(gcs_output_uri)
    bucket_name = parsed.netloc
    prefix = parsed.path.lstrip('/')
    
    # Ensure prefix ends with / if not empty
    if prefix and not prefix.endswith('/'):
        prefix += '/'
    
    logger.info(f"Bucket: {bucket_name}")
    logger.info(f"Prefix: {prefix}")
    
    # Create GCS client using our wrapper to prevent file-based fallback
    try:
        from gcs_utils import get_gcs_client
        # Temporarily clear GOOGLE_APPLICATION_CREDENTIALS to prevent file-based fallback
        old_creds_env = os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
        try:
            storage_client = get_gcs_client()  # Uses GCP_CREDENTIALS_JSON from environment
            bucket = storage_client.bucket(bucket_name)
            logger.info("GCS client created successfully")
        finally:
            # Restore environment variable if it was set
            if old_creds_env:
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = old_creds_env
    except Exception as e:
        error_msg = str(e)
        # Check if error is related to file access (which should never happen)
        if "was not found" in error_msg or "gcp-creds.json" in error_msg.lower() or "practice_testing" in error_msg.lower():
            raise ValueError(
                "GCP_CREDENTIALS_JSON environment variable is required. "
                "File-based credentials are not supported. "
                "Please set GCP_CREDENTIALS_JSON in your .env file."
            ) from e
        logger.error(f"Failed to create GCS client: {e}")
        raise
    
    # List all JSON files in the output folder
    logger.info("Listing JSON files in output folder...")
    blobs = list(bucket.list_blobs(prefix=prefix))
    json_blobs = [blob for blob in blobs if blob.name.endswith('.json')]
    
    if not json_blobs:
        logger.warning("No JSON files found in output folder")
        return []
    
    logger.info(f"Found {len(json_blobs)} JSON file(s)")
    
    # Extract text page by page
    pages_data = []
    page_number = 1
    
    for i, blob in enumerate(sorted(json_blobs, key=lambda x: x.name), 1):
        logger.info(f"Processing JSON file {i}/{len(json_blobs)}: {blob.name}")
        
        try:
            # Download and parse JSON
            json_content = blob.download_as_text()
            data = json.loads(json_content)
            
            # Extract pages from response
            # Vision API response structure: responses array with fullTextAnnotation
            if 'responses' in data:
                for response in data['responses']:
                    if 'fullTextAnnotation' in response:
                        full_text_annotation = response['fullTextAnnotation']
                        
                        # Check if pages array exists (structured page-by-page data)
                        if 'pages' in full_text_annotation and len(full_text_annotation['pages']) > 0:
                            # Extract each page separately
                            for page_data in full_text_annotation['pages']:
                                page_width = page_data.get('width', 612)  # Default to letter width
                                page_height = page_data.get('height', 792)  # Default to letter height
                                
                                # Extract text from blocks in this page
                                page_text_parts = []
                                if 'blocks' in page_data:
                                    for block in page_data['blocks']:
                                        if 'paragraphs' in block:
                                            for paragraph in block['paragraphs']:
                                                if 'words' in paragraph:
                                                    word_texts = []
                                                    for word in paragraph['words']:
                                                        if 'symbols' in word:
                                                            symbol_texts = []
                                                            for symbol in word['symbols']:
                                                                symbol_text = symbol.get('text', '')
                                                                symbol_texts.append(symbol_text)
                                                            word_text = ''.join(symbol_texts)
                                                            word_texts.append(word_text)
                                                    paragraph_text = ' '.join(word_texts)
                                                    page_text_parts.append(paragraph_text)
                                
                                page_text = '\n'.join(page_text_parts)
                                
                                # If no structured text found, try to get text from fullTextAnnotation.text
                                # This is a fallback for cases where structure is different
                                if not page_text.strip() and 'text' in full_text_annotation:
                                    # Use full text as fallback (will be assigned to first page only if multiple pages)
                                    # This handles edge cases where structure parsing fails
                                    full_text = full_text_annotation.get('text', '')
                                    if full_text and page_number == len(pages_data) + 1:
                                        # Only use fallback for the first page in this response to avoid duplication
                                        page_text = full_text
                                
                                if page_text.strip():
                                    pages_data.append({
                                        'text': page_text,
                                        'width': page_width,
                                        'height': page_height,
                                        'page_number': page_number
                                    })
                                    logger.info(f"Extracted page {page_number}: {len(page_text)} characters (size: {page_width}x{page_height})")
                                    page_number += 1
                        else:
                            # Fallback: no pages array, use full text annotation text
                            text = full_text_annotation.get('text', '')
                            if text:
                                # Try to get page dimensions from first block if available
                                page_width = 612  # Default letter width
                                page_height = 792  # Default letter height
                                
                                # Try to infer from blocks if available
                                if 'blocks' in full_text_annotation and len(full_text_annotation['blocks']) > 0:
                                    # Get dimensions from first page if available
                                    first_block = full_text_annotation['blocks'][0]
                                    if 'boundingBox' in first_block:
                                        vertices = first_block['boundingBox'].get('vertices', [])
                                        if len(vertices) >= 2:
                                            # Estimate page size from bounding box
                                            x_coords = [v.get('x', 0) for v in vertices]
                                            y_coords = [v.get('y', 0) for v in vertices]
                                            if x_coords and y_coords:
                                                page_width = max(x_coords) if max(x_coords) > 0 else 612
                                                page_height = max(y_coords) if max(y_coords) > 0 else 792
                                
                                pages_data.append({
                                    'text': text,
                                    'width': page_width,
                                    'height': page_height,
                                    'page_number': page_number
                                })
                                logger.info(f"Extracted page {page_number}: {len(text)} characters (size: {page_width}x{page_height})")
                                page_number += 1
                    elif 'textAnnotations' in response and len(response['textAnnotations']) > 0:
                        # Fallback to textAnnotations if fullTextAnnotation not available
                        text = response['textAnnotations'][0].get('description', '')
                        if text:
                            pages_data.append({
                                'text': text,
                                'width': 612,  # Default
                                'height': 792,  # Default
                                'page_number': page_number
                            })
                            logger.info(f"Extracted page {page_number}: {len(text)} characters (fallback method)")
                            page_number += 1
            else:
                # Direct text annotation (fallback)
                if 'fullTextAnnotation' in data:
                    full_text_annotation = data['fullTextAnnotation']
                    if 'pages' in full_text_annotation and len(full_text_annotation['pages']) > 0:
                        for page_data in full_text_annotation['pages']:
                            page_width = page_data.get('width', 612)
                            page_height = page_data.get('height', 792)
                            
                            # Extract text from blocks
                            page_text_parts = []
                            if 'blocks' in page_data:
                                for block in page_data['blocks']:
                                    if 'paragraphs' in block:
                                        for paragraph in block['paragraphs']:
                                            if 'words' in paragraph:
                                                word_texts = []
                                                for word in paragraph['words']:
                                                    if 'symbols' in word:
                                                        symbol_texts = []
                                                        for symbol in word['symbols']:
                                                            symbol_texts.append(symbol.get('text', ''))
                                                        word_texts.append(''.join(symbol_texts))
                                                page_text_parts.append(' '.join(word_texts))
                            
                            page_text = '\n'.join(page_text_parts) or full_text_annotation.get('text', '')
                            
                            if page_text.strip():
                                pages_data.append({
                                    'text': page_text,
                                    'width': page_width,
                                    'height': page_height,
                                    'page_number': page_number
                                })
                                logger.info(f"Extracted page {page_number}: {len(page_text)} characters")
                                page_number += 1
                    else:
                        text = full_text_annotation.get('text', '')
                        if text:
                            pages_data.append({
                                'text': text,
                                'width': 612,
                                'height': 792,
                                'page_number': page_number
                            })
                            logger.info(f"Extracted page {page_number}: {len(text)} characters")
                            page_number += 1
                elif 'textAnnotations' in data and len(data['textAnnotations']) > 0:
                    text = data['textAnnotations'][0].get('description', '')
                    if text:
                        pages_data.append({
                            'text': text,
                            'width': 612,
                            'height': 792,
                            'page_number': page_number
                        })
                        logger.info(f"Extracted page {page_number}: {len(text)} characters")
                        page_number += 1
        except Exception as e:
            logger.error(f"Error processing {blob.name}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    total_chars = sum(len(page['text']) for page in pages_data)
    
    logger.info("=" * 60)
    logger.info(f"Text extraction completed!")
    logger.info(f"Total pages extracted: {len(pages_data)}")
    logger.info(f"Total characters extracted: {total_chars}")
    logger.info(f"Total JSON files processed: {len(json_blobs)}")
    logger.info("=" * 60)
    
    return pages_data


def create_text_based_pdf(pages_data, output_file_path):
    """
    Create a text-based PDF from extracted page data.
    
    Args:
        pages_data: List of dictionaries containing page text and dimensions
        output_file_path: Local file path where PDF will be saved
    """
    logger.info("=" * 60)
    logger.info("Creating text-based PDF from extracted pages...")
    logger.info(f"Output file: {output_file_path}")
    logger.info(f"Total pages: {len(pages_data)}")
    
    try:
        # Create directory if it doesn't exist
        output_dir = os.path.dirname(output_file_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"Created output directory: {output_dir}")
        
        if not pages_data:
            logger.warning("No page data to create PDF from")
            return
        
        # Get page dimensions from first page (or use defaults)
        first_page = pages_data[0]
        page_width = first_page.get('width', 612)  # Default letter width in points
        page_height = first_page.get('height', 792)  # Default letter height in points
        
        # Convert to inches for reportlab (1 point = 1/72 inch)
        page_width_inch = page_width / 72.0
        page_height_inch = page_height / 72.0
        
        # Use standard sizes if dimensions are close to standard
        if abs(page_width - 612) < 10 and abs(page_height - 792) < 10:
            page_size = letter  # 8.5 x 11 inches
        elif abs(page_width - 595) < 10 and abs(page_height - 842) < 10:
            page_size = A4  # A4 size
        else:
            # Custom size
            page_size = (page_width, page_height)
        
        logger.info(f"Page size: {page_width}x{page_height} points ({page_width_inch:.2f}x{page_height_inch:.2f} inches)")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            output_file_path,
            pagesize=page_size,
            rightMargin=72,  # 1 inch margins
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Build content
        story = []
        styles = getSampleStyleSheet()
        
        # Create a style similar to the original document
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=6
        )
        
        for i, page_data in enumerate(pages_data, 1):
            logger.info(f"Adding page {i}/{len(pages_data)} to PDF...")
            
            page_text = page_data.get('text', '')
            
            if page_text.strip():
                # Split text into paragraphs
                paragraphs = page_text.split('\n')
                
                for para in paragraphs:
                    para = para.strip()
                    if para:
                        # Escape special characters for reportlab
                        para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        story.append(Paragraph(para, normal_style))
                        story.append(Spacer(1, 6))  # Small spacing between paragraphs
                
                # Add page break (except for last page)
                if i < len(pages_data):
                    story.append(PageBreak())
        
        # Build PDF
        doc.build(story)
        
        file_size_kb = os.path.getsize(output_file_path) / 1024
        logger.info("=" * 60)
        logger.info(f"✅ Text-based PDF created successfully!")
        logger.info(f"File: {output_file_path}")
        logger.info(f"Size: {file_size_kb:.2f} KB")
        logger.info(f"Pages: {len(pages_data)}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Failed to create text-based PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


def _get_gcp_credentials_for_vision():
    """
    Get GCP credentials from GCP_CREDENTIALS_JSON environment variable.
    
    Returns:
        service_account.Credentials: GCP service account credentials
        
    Raises:
        ValueError: If GCP_CREDENTIALS_JSON is not set
        RefreshError: If credentials are invalid
    """
    # Get credentials from environment variable
    credentials_json = os.getenv('GCP_CREDENTIALS_JSON')
    
    if not credentials_json:
        raise ValueError(
            "GCP_CREDENTIALS_JSON environment variable is not set. "
            "Please set it in your .env file or environment."
        )
    
    # Verify variable exists (but don't parse/print its value)
    if not credentials_json.strip():
        raise ValueError(
            "GCP_CREDENTIALS_JSON environment variable is empty. "
            "Please provide valid credentials JSON."
        )
    
    try:
        # Parse JSON and create credentials (internal operation, no logging of values)
        sa_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(sa_info)
        return credentials
    except json.JSONDecodeError as e:
        raise ValueError(
            "GCP_CREDENTIALS_JSON contains invalid JSON. "
            "Please verify the credentials format."
        ) from e
    except RefreshError as e:
        error_msg = str(e)
        if "Invalid JWT Signature" in error_msg or "invalid_grant" in error_msg:
            logger.error("=" * 60)
            logger.error("AUTHENTICATION ERROR: Invalid Credentials")
            logger.error("=" * 60)
            logger.error("The credentials in GCP_CREDENTIALS_JSON are invalid.")
            logger.error("")
            logger.error("This usually means:")
            logger.error("  1. The service account key was regenerated/deleted in Google Cloud Console")
            logger.error("  2. The credentials JSON is corrupted or modified")
            logger.error("  3. The private key in the credentials is no longer valid")
            logger.error("")
            logger.error("SOLUTION: Update GCP_CREDENTIALS_JSON with a new service account key:")
            logger.error("  1. Go to https://console.cloud.google.com/iam-admin/serviceaccounts")
            logger.error("  2. Select your service account")
            logger.error("  3. Go to 'Keys' tab > 'Add Key' > 'Create new key' > 'JSON'")
            logger.error("  4. Update GCP_CREDENTIALS_JSON in your .env file with the new key")
            logger.error("=" * 60)
        raise


def vision_ocr_pdf(gcs_input_uri, gcs_output_uri, gcs_input_path=None, service_account_file=None):
    """
    Process scanned PDF with Vision API OCR and create text-based PDF.
    
    Args:
        gcs_input_uri: GCS URI of the input PDF file
        gcs_output_uri: GCS URI for JSON output folder
        gcs_input_path: GCS path where text-based PDF should be saved (e.g., gs://bucket/input-docs/)
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        
    Returns:
        str: Combined extracted text from all pages
    """
    logger.info("=" * 60)
    logger.info("Starting Vision API OCR processing")
    logger.info(f"Input URI: {gcs_input_uri}")
    logger.info(f"Output URI: {gcs_output_uri}")
    logger.info("=" * 60)
    
    if service_account_file:
        logger.warning(
            "service_account_file parameter is deprecated. "
            "Using GCP_CREDENTIALS_JSON from environment instead."
        )
    
    # Create Vision API client with credentials from environment variable
    logger.info("Creating Vision API client...")
    
    # Temporarily clear GOOGLE_APPLICATION_CREDENTIALS to prevent file-based fallback
    old_creds_env = os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
    
    try:
        credentials = _get_gcp_credentials_for_vision()
        # Explicitly pass credentials to prevent any fallback to default credentials
        client = vision.ImageAnnotatorClient(credentials=credentials)
        logger.info("Client created successfully")
    except (ValueError, RefreshError) as e:
        # Re-raise credential errors as-is
        raise
    except Exception as e:
        error_msg = str(e)
        # Check if error is related to file access (which should never happen)
        if "was not found" in error_msg or "gcp-creds.json" in error_msg.lower() or "practice_testing" in error_msg.lower():
            raise ValueError(
                "GCP_CREDENTIALS_JSON environment variable is required. "
                "File-based credentials are not supported. "
                "Please set GCP_CREDENTIALS_JSON in your .env file."
            ) from e
        logger.error("=" * 60)
        logger.error("FAILED TO CREATE VISION API CLIENT")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 60)
        raise
    finally:
        # Restore environment variable if it was set
        if old_creds_env:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = old_creds_env

    # Configure source PDF
    logger.info("Configuring input source...")
    gcs_source = vision.GcsSource(uri=gcs_input_uri)
    input_config = vision.InputConfig(
        gcs_source=gcs_source, mime_type="application/pdf"
    )
    logger.info(f"Input config created: MIME type = application/pdf")

    # Configure output destination
    logger.info("Configuring output destination...")
    gcs_destination = vision.GcsDestination(uri=gcs_output_uri)
    output_config = vision.OutputConfig(
        gcs_destination=gcs_destination,
        batch_size=2  # pages per JSON output
    )
    logger.info(f"Output config created: batch_size = 2 pages per JSON")

    # Configure feature
    logger.info("Configuring OCR feature...")
    feature = vision.Feature(
        type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION
    )
    logger.info("Feature type: DOCUMENT_TEXT_DETECTION")

    # Create request
    logger.info("Creating async annotation request...")
    request = vision.AsyncAnnotateFileRequest(
        features=[feature],
        input_config=input_config,
        output_config=output_config,
    )
    logger.info("Request created successfully")

    # Submit async batch annotation
    logger.info("Submitting async batch annotation request...")
    try:
        operation = client.async_batch_annotate_files(requests=[request])
        logger.info("Request submitted. Operation started.")
        logger.info(f"Operation name: {operation.operation.name if hasattr(operation, 'operation') else 'N/A'}")
    except RefreshError as e:
        logger.error("=" * 60)
        logger.error("AUTHENTICATION ERROR during API call")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("")
        logger.error("Your Google account appears to be restricted.")
        logger.error("Please check:")
        logger.error("1. Service account key file exists and is valid")
        logger.error("2. Service account has Vision API permissions")
        logger.error("3. Billing is enabled for your GCP project")
        logger.error("=" * 60)
        raise
    except api_exceptions.PermissionDenied as e:
        logger.error("=" * 60)
        logger.error("PERMISSION ERROR")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("")
        logger.error("Service account doesn't have permission to use Vision API.")
        logger.error("Please assign 'Cloud Vision API User' role to the service account.")
        logger.error("=" * 60)
        raise
    except Exception as e:
        logger.error(f"Failed to submit annotation request: {e}")
        raise

    # Wait for operation to complete
    logger.info("=" * 60)
    logger.info("Waiting for Vision OCR to complete...")
    logger.info("This may take several minutes depending on document size...")
    logger.info("=" * 60)
    
    try:
        operation.result(timeout=600)
        logger.info("=" * 60)
        logger.info("✅ OCR processing completed successfully!")
        logger.info(f"Results stored at: {gcs_output_uri}")
        logger.info("=" * 60)
    except RefreshError as e:
        logger.error("=" * 60)
        logger.error("AUTHENTICATION ERROR during operation")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("Account may be restricted. Please check service account permissions.")
        logger.error("=" * 60)
        raise
    except api_exceptions.PermissionDenied as e:
        logger.error("=" * 60)
        logger.error("PERMISSION ERROR during operation")
        logger.error("=" * 60)
        logger.error(f"Error: {str(e)}")
        logger.error("Service account lacks required permissions.")
        logger.error("=" * 60)
        raise
    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ OCR processing failed or timed out")
        logger.error(f"Error: {e}")
        logger.error("=" * 60)
        raise
    
    # Extract text from output JSON files (page by page)
    try:
        pages_data = extract_text_from_vision_output(gcs_output_uri, credentials=None)  # Uses GCP_CREDENTIALS_JSON from environment
        
        if not pages_data:
            logger.warning("No pages extracted from OCR output")
            return ""
        
        # Combine all page text for contract extraction
        combined_text = '\n\n'.join([page.get('text', '') for page in pages_data])
        
        # Create text-based PDF and save to input folder if path provided
        if gcs_input_path:
            try:
                import tempfile
                from pathlib import Path
                from gcs_utils import upload_file_to_gcs
                
                # Get original filename and create text-based PDF name
                original_filename = Path(gcs_input_uri).name
                base_name = Path(original_filename).stem
                text_pdf_filename = f"{base_name}_text_based.pdf"
                
                # Create temporary local file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                    temp_pdf_path = temp_file.name
                
                # Create text-based PDF locally
                logger.info("Creating text-based PDF from extracted text...")
                create_text_based_pdf(pages_data, temp_pdf_path)
                
                # Upload text-based PDF to input folder
                gcs_text_pdf_uri = f"{gcs_input_path.rstrip('/')}/{text_pdf_filename}"
                logger.info(f"Uploading text-based PDF to {gcs_text_pdf_uri}...")
                upload_file_to_gcs(temp_pdf_path, gcs_text_pdf_uri, None)  # Uses GCP_CREDENTIALS_JSON from environment
                
                # Clean up temporary file
                try:
                    os.remove(temp_pdf_path)
                except Exception:
                    pass
                
                logger.info(f"✅ Text-based PDF saved to {gcs_text_pdf_uri}")
            except Exception as e:
                logger.warning(f"Failed to create/upload text-based PDF: {e}")
                logger.warning("Text extraction completed, but PDF creation failed. Continuing with text extraction.")
        
        return combined_text
    except Exception as e:
        logger.error(f"Failed to extract text from output files: {e}")
        logger.warning("OCR completed but text extraction failed. Check JSON files manually.")
        return ""


# if __name__ == "__main__":
#     logger.info("Initializing Vision API OCR processor...")
    
#     # Input PDF (Note: Vision API requires GCS URIs, not local paths)
#     # input_pdf = "gs://data-pdf-extractor/Mutual Non-Disclosure Agreement (NDA) for HYPERTHINK SYSTEMS (FZE) (1).pdf"
#     input_pdf = "gs://data-pdf-extractor/input-docs/Mutual Non-Disclosure Agreement (NDA) for HYPERTHINK SYSTEMS (FZE) (1).pdf"
#     # Output location (folder, not a file)
#     output_path = "gs://data-pdf-extractor/processed-documents/"
    
#     # Validate input paths
#     # Check if using GCS URIs (required for Vision API async batch processing)
#     if input_pdf.startswith("gs://"):
#         logger.info(f"Input GCS URI: {input_pdf}")
#         logger.info("Note: Cannot validate GCS file existence locally. Vision API will validate during processing.")
#     else:
#         # Local file path validation
#         if not os.path.exists(input_pdf):
#             logger.error(f"Input file not found: {input_pdf}")
#             logger.error("Please ensure the file exists and the path is correct.")
#             exit(1)
#         file_size_mb = os.path.getsize(input_pdf) / (1024 * 1024)
#         logger.info(f"Input file found: {input_pdf}")
#         logger.info(f"File size: {file_size_mb:.2f} MB")
#         logger.warning("=" * 60)
#         logger.warning("⚠️  WARNING: Vision API async batch processing requires GCS URIs")
#         logger.warning("Local file paths will not work for async_batch_annotate_files().")
#         logger.warning("Please upload your file to Google Cloud Storage first.")
#         logger.warning("Example GCS URI format: gs://your-bucket-name/path/to/file.pdf")
#         logger.warning("=" * 60)
#         logger.error("Cannot proceed with local file path. Please use GCS URI.")
#         exit(1)
    
#     # Validate output path
#     if not output_path.startswith("gs://"):
#         logger.warning("=" * 60)
#         logger.warning("⚠️  WARNING: Output path should be a GCS URI (gs://bucket/path/)")
#         logger.warning("=" * 60)
#         logger.error("Cannot proceed with local output path. Please use GCS URI.")
#         exit(1)
    
#     logger.info(f"Output GCS URI: {output_path}")
    
#     # Check service account key file exists
#     service_account_file = "gcp-creds.json"
#     if not os.path.exists(service_account_file):
#         logger.error(f"Service account key file not found: {service_account_file}")
#         logger.error("Please ensure the service account JSON key file exists.")
#         exit(1)
#     logger.info(f"Using service account: {service_account_file}")
    
#     try:
#         pages_data = vision_ocr_pdf(input_pdf, output_path)
        
#         # Process extracted pages
#         if pages_data:
#             logger.info(f"Successfully extracted {len(pages_data)} page(s)")
            
#             # Display first page text as preview
#             if pages_data and len(pages_data) > 0:
#                 first_page_text = pages_data[0].get('text', '')
#                 preview_length = min(500, len(first_page_text))
#                 print("\n" + "=" * 60)
#                 print("EXTRACTED TEXT PREVIEW (First Page)")
#                 print("=" * 60)
#                 print(first_page_text[:preview_length])
#                 if len(first_page_text) > preview_length:
#                     print("\n... (truncated)")
#                 print("=" * 60)
            
#             # Generate output filename from input PDF name
#             input_filename = os.path.basename(input_pdf)
#             # Remove extension and add _text_based.pdf
#             base_name = os.path.splitext(input_filename)[0]
#             output_dir = "C:/Users/Admin/GCP_document AI/contract_documents/extracted_text/"
#             output_filename = f"{base_name}_text_based.pdf"
#             output_file_path = os.path.join(output_dir, output_filename)
            
#             try:
#                 # Create text-based PDF
#                 create_text_based_pdf(pages_data, output_file_path)
#                 logger.info("✅ Text-based PDF created successfully!")
#             except Exception as e:
#                 logger.error(f"Failed to create text-based PDF: {e}")
#                 logger.warning("Text was extracted but could not be saved to PDF file.")
#         else:
#             logger.warning("No text was extracted from the output files.")
#             logger.info("Please check the JSON files in the output folder manually.")
#     except RefreshError as e:
#         logger.error("=" * 60)
#         logger.error("AUTHENTICATION ERROR during Vision OCR processing")
#         logger.error("=" * 60)
#         logger.error(f"Error: {str(e)}")
#         logger.error("")
#         logger.error("Your Google account appears to be restricted.")
#         logger.error("Please check:")
#         logger.error("1. Visit the error URL provided in the error details")
#         logger.error("2. Verify service account key file is valid")
#         logger.error("3. Check if billing is enabled for your GCP project")
#         logger.error("4. Ensure service account has Vision API access")
#         logger.error("=" * 60)
#         import traceback
#         traceback.print_exc()
#         exit(1)
#     except api_exceptions.PermissionDenied as e:
#         logger.error("=" * 60)
#         logger.error("PERMISSION ERROR")
#         logger.error("=" * 60)
#         logger.error(f"Error: {str(e)}")
#         logger.error("")
#         logger.error("Service account doesn't have permission to use Vision API.")
#         logger.error("Please verify:")
#         logger.error("1. Service account has 'Cloud Vision API User' role")
#         logger.error("2. Vision API is enabled for your project")
#         logger.error("3. Service account has access to the GCS bucket")
#         logger.error("=" * 60)
#         import traceback
#         traceback.print_exc()
#         exit(1)
#     except Exception as e:
#         logger.error("=" * 60)
#         logger.error("ERROR: Vision OCR processing failed")
#         logger.error("=" * 60)
#         logger.error(f"Error type: {type(e).__name__}")
#         logger.error(f"Error message: {str(e)}")
#         logger.error("=" * 60)
#         import traceback
#         traceback.print_exc()
#         exit(1)
