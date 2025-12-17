"""
Google Cloud Storage utilities for file upload/download.
"""

import os
import logging
from pathlib import Path
from google.cloud import storage
from google.oauth2 import service_account
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def get_gcs_client(service_account_file: str = None):
    """
    Create and return a GCS client.
    
    Args:
        service_account_file: Path to service account JSON key file
        
    Returns:
        storage.Client: GCS client instance
    """
    if service_account_file and os.path.exists(service_account_file):
        credentials = service_account.Credentials.from_service_account_file(
            service_account_file
        )
        return storage.Client(credentials=credentials)
    else:
        # Use default credentials
        return storage.Client()


def upload_file_to_gcs(
    local_file_path: str,
    gcs_uri: str,
    service_account_file: str = None
) -> str:
    """
    Upload a local file to Google Cloud Storage.
    
    Args:
        local_file_path: Path to local file to upload
        gcs_uri: GCS URI where file should be uploaded (e.g., gs://bucket/path/filename.pdf)
        service_account_file: Path to service account JSON key file
        
    Returns:
        str: GCS URI of uploaded file
    """
    logger.info(f"Uploading {local_file_path} to {gcs_uri}")
    
    # Parse GCS URI
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip('/')
    
    # Create GCS client
    client = get_gcs_client(service_account_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Upload file
    blob.upload_from_filename(local_file_path)
    
    logger.info(f"✅ File uploaded successfully to {gcs_uri}")
    return gcs_uri


def download_file_from_gcs(
    gcs_uri: str,
    local_file_path: str,
    service_account_file: str = None
):
    """
    Download a file from Google Cloud Storage.
    
    Args:
        gcs_uri: GCS URI of file to download (e.g., gs://bucket/path/filename.pdf)
        local_file_path: Local path where file should be saved
        service_account_file: Path to service account JSON key file
    """
    logger.info(f"Downloading {gcs_uri} to {local_file_path}")
    
    # Parse GCS URI
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip('/')
    
    # Create GCS client
    client = get_gcs_client(service_account_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Create local directory if needed
    os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
    
    # Download file
    blob.download_to_filename(local_file_path)
    
    logger.info(f"✅ File downloaded successfully to {local_file_path}")


def save_text_to_gcs(
    text: str,
    gcs_uri: str,
    service_account_file: str = None
) -> str:
    """
    Save text content to a file in Google Cloud Storage.
    
    Args:
        text: Text content to save
        gcs_uri: GCS URI where text should be saved (e.g., gs://bucket/path/filename.txt)
        service_account_file: Path to service account JSON key file
        
    Returns:
        str: GCS URI of saved file
    """
    logger.info(f"Saving text to {gcs_uri}")
    
    # Parse GCS URI
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip('/')
    
    # Create GCS client
    client = get_gcs_client(service_account_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Upload text
    blob.upload_from_string(text, content_type='text/plain')
    
    logger.info(f"✅ Text saved successfully to {gcs_uri}")
    return gcs_uri


def read_text_from_gcs(
    gcs_uri: str,
    service_account_file: str = None
) -> str:
    """
    Read text content from a file in Google Cloud Storage.
    
    Args:
        gcs_uri: GCS URI of file to read (e.g., gs://bucket/path/filename.txt)
        service_account_file: Path to service account JSON key file
        
    Returns:
        str: Text content of the file
    """
    logger.info(f"Reading text from {gcs_uri}")
    
    # Parse GCS URI
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip('/')
    
    # Create GCS client
    client = get_gcs_client(service_account_file)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Download text
    text = blob.download_as_text()
    
    logger.info(f"✅ Text read successfully from {gcs_uri}")
    return text

