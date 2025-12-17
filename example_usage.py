"""
Example usage of the Contract Extraction Engine.
"""

import os
import json
from pathlib import Path
from extraction_orchestrator import ExtractionOrchestrator

from dotenv import load_dotenv
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')


def example_extract_from_file():
    """Example: Extract contract data from a PDF file."""
    
    # Set your OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return
    
    # Initialize orchestrator
    orchestrator = ExtractionOrchestrator(
        api_key=api_key,
        use_gcs_vision=True,  # Enable Vision API for scanned PDFs
        use_semantic_search=True
    )
    
    # File path
    file_path = "contract_documents/NDA-NSIL.pdf"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        print("Please provide a valid contract document path")
        return
    
    print(f"Processing document: {file_path}")
    print("(Orchestrator will handle parsing, classification, and extraction)")
    
    # Extract contract data (orchestrator handles everything)
    contract_data, metadata = orchestrator.extract_from_file(file_path)
    
    print(f"\nDocument Type: {metadata.get('document_type', 'Unknown')}")
    print(f"Confidence: {metadata.get('classification_confidence', 'Unknown')}")
    
    # Display results
    print("\n" + "="*80)
    print("EXTRACTED CONTRACT DATA:")
    print("="*80)
    print(json.dumps(contract_data, indent=2, ensure_ascii=False))
    
    # Save to file
    output_file = "extracted_contract.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(contract_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {output_file}")


def example_extract_from_text():
    """Example: Extract contract data from raw text."""
    
    # Set your OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return
    
    # Sample contract text
    contract_text = """
    NON-DISCLOSURE AGREEMENT
    
    This Non-Disclosure Agreement ("Agreement") is entered into on January 15, 2024,
    between ABC Corporation, located at 123 Main Street, New York, NY 10001 ("Party A"),
    and XYZ Inc., located at 456 Business Ave, Los Angeles, CA 90001 ("Party B").
    
    The parties agree to maintain confidentiality of all proprietary information
    shared during the course of business discussions.
    
    This Agreement shall remain in effect until December 31, 2024.
    
    Signed by:
    Party A: John Doe
    Party B: Jane Smith
    """
    
    # Initialize orchestrator
    orchestrator = ExtractionOrchestrator(
        api_key=api_key,
        use_gcs_vision=True,
        use_semantic_search=True
    )
    
    print("Extracting contract data from text...")
    contract_data, metadata = orchestrator.extract_from_text(contract_text)
    
    print(f"\nDocument Type: {metadata.get('document_type', 'Unknown')}")
    print(f"Confidence: {metadata.get('classification_confidence', 'Unknown')}")
    
    # Display results
    print("\n" + "="*80)
    print("EXTRACTED CONTRACT DATA:")
    print("="*80)
    print(json.dumps(contract_data, indent=2, ensure_ascii=False))


def example_with_ocr():
    """Example: Extract from scanned PDF using OCR."""
    
    # Set your OpenAI API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Please set OPENAI_API_KEY environment variable")
        return
    
    # Initialize orchestrator (automatically uses vision_gcp.py for scanned PDFs)
    orchestrator = ExtractionOrchestrator(
        api_key=api_key,
        use_gcs_vision=True,  # Enable Vision API for scanned PDFs
        service_account_file="gcp-creds.json",
        use_semantic_search=True
    )
    
    # Parse scanned PDF with OCR
    file_path = "contract_documents/scanned_contract.pdf"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        print("Please provide a valid scanned contract document path")
        return
    
    print(f"Processing scanned document with OCR: {file_path}")
    print("(Orchestrator will automatically use vision_gcp.py for OCR)")
    
    # Extract contract data (orchestrator handles OCR automatically)
    contract_data, metadata = orchestrator.extract_from_file(file_path, use_ocr=True)
    
    print(f"\nDocument Type: {metadata.get('document_type', 'Unknown')}")
    print(f"Confidence: {metadata.get('classification_confidence', 'Unknown')}")
    
    # Display results
    print("\n" + "="*80)
    print("EXTRACTED CONTRACT DATA:")
    print("="*80)
    print(json.dumps(contract_data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    print("Contract Extraction Engine - Example Usage")
    print("="*80)
    
    # Run example
    example_extract_from_file()
    
    # Uncomment to try other examples:
    # example_extract_from_text()
    # example_with_ocr()

