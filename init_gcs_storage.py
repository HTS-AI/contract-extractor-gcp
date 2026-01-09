"""
Initialize GCS Storage Structure for Document Extraction App

This script creates the necessary folder structure in Google Cloud Storage
for persistent storage of cache, extraction history, and Excel exports.

Run this once to set up the GCS bucket structure:
    python init_gcs_storage.py

Required environment variable:
    GCP_CREDENTIALS_JSON - Your GCP service account credentials JSON
"""

import os
import json
from datetime import datetime

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed, using system environment variables")

from gcs_utils import get_gcs_client

# GCS bucket configuration
GCS_BUCKET = "data-pdf-extractor"
GCS_CACHE_PREFIX = "cache/"

# Folder structure to create
FOLDERS_TO_CREATE = [
    "cache/extraction_cache/",
    "cache/chatbot_cache/",
    "cache/exports/",
]

# Initial files to create
INITIAL_FILES = {
    "cache/extractions_data.json": json.dumps([], indent=2),
    "cache/extraction_cache/.gitkeep": "# This folder contains extraction cache files",
    "cache/chatbot_cache/.gitkeep": "# This folder contains chatbot cache files",
    "cache/exports/.gitkeep": "# This folder contains Excel exports (contract_extractions.xlsx)",
}


def create_gcs_folders():
    """Create folder structure in GCS bucket."""
    print("=" * 60)
    print("Initializing GCS Storage Structure")
    print("=" * 60)
    print(f"Bucket: {GCS_BUCKET}")
    print(f"Cache Prefix: {GCS_CACHE_PREFIX}")
    print()
    
    try:
        # Get GCS client
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        
        print("Creating folder structure...")
        print()
        
        # Create initial files (which creates the folders)
        for file_path, content in INITIAL_FILES.items():
            blob = bucket.blob(file_path)
            
            # Check if file already exists
            if blob.exists():
                print(f"  [OK] {file_path} (already exists)")
            else:
                blob.upload_from_string(content, content_type='text/plain')
                print(f"  [OK] {file_path} (created)")
        
        print()
        print("=" * 60)
        print("[SUCCESS] GCS Storage Structure Initialized Successfully!")
        print("=" * 60)
        print()
        print("Folder structure created:")
        print(f"  gs://{GCS_BUCKET}/cache/")
        print(f"    - extraction_cache/    (for document extraction cache)")
        print(f"    - chatbot_cache/       (for chatbot session cache)")
        print(f"    - exports/             (for Excel exports)")
        print(f"    - extractions_data.json (extraction history)")
        print()
        print("Next steps:")
        print("  1. Set GCS_CACHE_BUCKET environment variable in Cloud Run:")
        print(f"     GCS_CACHE_BUCKET=gs://{GCS_BUCKET}/cache/")
        print()
        print("  2. Redeploy your Cloud Run service")
        print()
        
    except Exception as e:
        print(f"[ERROR] {e}")
        print()
        print("Make sure:")
        print("  1. GCP_CREDENTIALS_JSON environment variable is set")
        print("  2. Service account has Storage Admin permissions")
        print(f"  3. Bucket '{GCS_BUCKET}' exists")
        raise


def verify_gcs_structure():
    """Verify the GCS folder structure exists."""
    print("Verifying GCS structure...")
    
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET)
        
        # List all files in cache folder
        blobs = list(bucket.list_blobs(prefix=GCS_CACHE_PREFIX))
        
        print(f"\nFiles in gs://{GCS_BUCKET}/{GCS_CACHE_PREFIX}:")
        for blob in blobs:
            print(f"  - {blob.name}")
        
        if not blobs:
            print("  (no files found)")
            
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    create_gcs_folders()
    print()
    verify_gcs_structure()
