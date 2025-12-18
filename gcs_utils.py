"""
Google Cloud Storage utilities for file upload/download.
"""

import os
import json
import logging
from google.cloud import storage
from google.oauth2 import service_account
from google.auth.exceptions import RefreshError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def _get_gcp_credentials():
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
            logger.error("INVALID CREDENTIALS ERROR")
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


def get_gcs_client(service_account_file: str = None):
    """
    Create and return a GCS client using credentials from environment variable.
    
    Args:
        service_account_file: DEPRECATED - This parameter is ignored.
                             Credentials are now loaded from GCP_CREDENTIALS_JSON environment variable.
        
    Returns:
        storage.Client: GCS client instance
        
    Raises:
        ValueError: If GCP_CREDENTIALS_JSON is not set or invalid
        RefreshError: If credentials are invalid
    """
    if service_account_file:
        logger.warning(
            "service_account_file parameter is deprecated. "
            "Using GCP_CREDENTIALS_JSON from environment instead."
        )
    
    # Temporarily clear GOOGLE_APPLICATION_CREDENTIALS to prevent file-based fallback
    old_creds_env = os.environ.pop('GOOGLE_APPLICATION_CREDENTIALS', None)
    
    try:
        credentials = _get_gcp_credentials()
        # Explicitly pass credentials to prevent any fallback to default credentials
        client = storage.Client(credentials=credentials, project=credentials.project_id)
        return client
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
        logger.error(f"Unexpected error creating GCS client: {e}")
        raise
    finally:
        # Restore environment variable if it was set
        if old_creds_env:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = old_creds_env


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
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        
    Returns:
        str: GCS URI of uploaded file
    """
    logger.info(f"Uploading {local_file_path} to {gcs_uri}")
    
    # Parse GCS URI
    parsed = urlparse(gcs_uri)
    bucket_name = parsed.netloc
    blob_name = parsed.path.lstrip('/')
    
    # Create GCS client (uses GCP_CREDENTIALS_JSON from environment)
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
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
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
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        
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
        service_account_file: DEPRECATED - Credentials are loaded from GCP_CREDENTIALS_JSON environment variable
        
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

