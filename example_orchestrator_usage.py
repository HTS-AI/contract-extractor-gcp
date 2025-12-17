"""
Example usage of the Extraction Orchestrator
Demonstrates how to use the orchestrator with vision_gcp.py for scanned PDFs
"""

import os
from pathlib import Path
from extraction_orchestrator import ExtractionOrchestrator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def example_extract_from_file():
    """Example: Extract data from a file (works with vision_gcp.py for scanned PDFs)."""
    
    # Initialize orchestrator
    # It will automatically use vision_gcp.py if scanned PDF is detected
    orchestrator = ExtractionOrchestrator(
        api_key=os.getenv('OPENAI_API_KEY'),
        use_gcs_vision=True,  # Enable Vision API for scanned PDFs
        service_account_file="gcp-creds.json"
    )
    
    # Example file path
    file_path = "contract_documents/example.pdf"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        print("Please provide a valid document path")
        return
    
    try:
        # Extract data (orchestrator handles everything)
        # - Parses document (uses vision_gcp.py if scanned PDF)
        # - Classifies document type (Lease, NDA, or Contract)
        # - Routes to appropriate extractor
        # - Returns unified results
        extracted_data, metadata = orchestrator.extract_from_file(
            file_path,
            use_ocr=False  # Set to True to force OCR, or let it auto-detect
        )
        
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"\nDocument Type: {metadata['document_type']}")
        print(f"Confidence: {metadata['classification_confidence']}")
        print(f"Reasoning: {metadata['classification_reasoning']}")
        print(f"\nExtracted Data Keys: {list(extracted_data.keys())}")
        
        # Display some key information
        if extracted_data.get("contract_title"):
            print(f"\nContract Title: {extracted_data['contract_title']}")
        
        if extracted_data.get("contract_type"):
            print(f"Contract Type: {extracted_data['contract_type']}")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()


def example_extract_from_text():
    """Example: Extract data from raw text."""
    
    # Initialize orchestrator
    orchestrator = ExtractionOrchestrator(
        api_key=os.getenv('OPENAI_API_KEY'),
        use_gcs_vision=True
    )
    
    # Example text
    sample_text = """
    NON-DISCLOSURE AGREEMENT
    
    This Non-Disclosure Agreement is entered into between Company A and Company B...
    """
    
    try:
        # Extract data from text
        extracted_data, metadata = orchestrator.extract_from_text(sample_text)
        
        print("\n" + "="*80)
        print("EXTRACTION COMPLETE")
        print("="*80)
        print(f"\nDocument Type: {metadata['document_type']}")
        print(f"Extracted Data Keys: {list(extracted_data.keys())}")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Extraction Orchestrator Example")
    print("="*80)
    print("\nThis example demonstrates:")
    print("1. Automatic document type detection (Lease, NDA, or Contract)")
    print("2. Routing to appropriate extractor")
    print("3. Integration with vision_gcp.py for scanned PDFs")
    print("\n" + "="*80)
    
    # Run example
    example_extract_from_file()

