"""
Main entry point for Contract Extraction Engine.
"""

import os
import json
import argparse
from pathlib import Path
# Use LangGraph-based agent instead of traditional orchestrator
try:
    from extraction_agent import ExtractionAgent as ExtractionOrchestrator
    USING_LANGGRAPH = True
except ImportError:
    # Fallback to traditional orchestrator if LangGraph not available
    from extraction_orchestrator import ExtractionOrchestrator
    USING_LANGGRAPH = False

from document_parser import DocumentParser


def main():
    """Main function to run contract extraction."""
    parser = argparse.ArgumentParser(
        description="Contract Extraction Engine - Extract structured data from contract documents"
    )
    
    parser.add_argument(
        'input',
        type=str,
        help='Path to contract document (PDF, DOCX, TXT) or raw text string'
    )
    
    parser.add_argument(
        '--output',
        '-o',
        type=str,
        help='Output JSON file path (default: print to stdout)'
    )
    
    parser.add_argument(
        '--ocr',
        action='store_true',
        help='Use OCR for PDF files (for scanned documents)'
    )
    
    parser.add_argument(
        '--tesseract-cmd',
        type=str,
        help='Path to tesseract executable (for OCR on Windows)'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='OpenAI API key (or set OPENAI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '--text-input',
        action='store_true',
        help='Treat input as raw text string instead of file path'
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("ERROR: OpenAI API key is required.")
        print("Provide it via --api-key argument or OPENAI_API_KEY environment variable.")
        return 1
    
    try:
        # Initialize orchestrator (LangGraph agent or traditional)
        if USING_LANGGRAPH:
            print("Using LangGraph-based ExtractionAgent")
            orchestrator = ExtractionOrchestrator(
                api_key=api_key,
                use_gcs_vision=True  # Enable Vision API for scanned PDFs
            )
        else:
            print("Using traditional ExtractionOrchestrator")
            orchestrator = ExtractionOrchestrator(
                api_key=api_key,
                use_gcs_vision=True,  # Enable Vision API for scanned PDFs
                use_semantic_search=True,
                document_id=Path(args.input).stem if not args.text_input else f"text_{hash(args.input) % 100000}"
            )
        
        # Extract contract data
        print("Extracting contract data...", flush=True)
        if args.text_input:
            # Input is raw text
            extracted_data, metadata = orchestrator.extract_from_text(args.input)
        else:
            # Input is a file path
            extracted_data, metadata = orchestrator.extract_from_file(args.input, use_ocr=args.ocr)
        
        # Output results
        output_json = json.dumps(extracted_data, indent=2, ensure_ascii=False)
        
        if args.output:
            # Write to file
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_json)
            print(f"Extraction complete! Results saved to: {args.output}")
        else:
            # Print to stdout
            print("\n" + "="*80)
            print("EXTRACTED CONTRACT DATA:")
            print("="*80)
            print(output_json)
        
        return 0
        
    except FileNotFoundError as e:
        print(f"ERROR: {str(e)}")
        return 1
    except ValueError as e:
        print(f"ERROR: {str(e)}")
        return 1
    except ImportError as e:
        print(f"ERROR: {str(e)}")
        return 1
    except Exception as e:
        print(f"ERROR: Unexpected error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())

