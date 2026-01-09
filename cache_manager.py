"""
Cache Manager for Document Processing
Handles content-based caching to avoid re-processing the same files.
Uses SHA256 hash of file content as cache key.

Supports both local file storage and Google Cloud Storage (GCS) for persistence.
GCS is used automatically in cloud deployments (Cloud Run) to persist cache across container restarts.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# GCS support flag
GCS_AVAILABLE = False
try:
    from gcs_utils import get_gcs_client
    GCS_AVAILABLE = True
except ImportError:
    pass


class CacheManager:
    """Manages caching of document processing results.
    
    Supports two storage backends:
    1. Local file storage (default for local development)
    2. Google Cloud Storage (for cloud deployments like Cloud Run)
    
    Set GCS_CACHE_BUCKET environment variable to enable GCS storage.
    Example: GCS_CACHE_BUCKET=gs://your-bucket/cache/
    """
    
    def __init__(self, cache_base_dir: Optional[Path] = None):
        """
        Initialize cache manager.
        
        Args:
            cache_base_dir: Base directory for local cache (defaults to project root)
        """
        if cache_base_dir is None:
            cache_base_dir = Path(__file__).parent
        
        self.cache_base_dir = cache_base_dir
        self.extraction_cache_dir = cache_base_dir / "extraction_cache"
        self.chatbot_cache_dir = cache_base_dir / "chatbot_cache"
        
        # Create local cache directories (used as fallback and for temp files)
        self.extraction_cache_dir.mkdir(exist_ok=True)
        self.chatbot_cache_dir.mkdir(exist_ok=True)
        
        # Check for GCS cache configuration
        self.gcs_cache_bucket = os.environ.get("GCS_CACHE_BUCKET", "")
        self.use_gcs = bool(self.gcs_cache_bucket and GCS_AVAILABLE)
        
        if self.use_gcs:
            # Ensure bucket path ends with /
            if not self.gcs_cache_bucket.endswith("/"):
                self.gcs_cache_bucket += "/"
            print(f"[CACHE] Using GCS storage: {self.gcs_cache_bucket}")
            print(f"[CACHE] Local cache (fallback): {self.extraction_cache_dir.absolute()}")
        else:
            print(f"[CACHE] Using local storage")
            print(f"[CACHE] Extraction cache: {self.extraction_cache_dir.absolute()}")
            print(f"[CACHE] Chatbot cache: {self.chatbot_cache_dir.absolute()}")
            if not GCS_AVAILABLE:
                print(f"[CACHE] Note: GCS not available (gcs_utils import failed)")
            elif not self.gcs_cache_bucket:
                print(f"[CACHE] Note: Set GCS_CACHE_BUCKET env var to enable GCS persistent cache")
    
    def compute_file_hash(self, file_path: str) -> str:
        """
        Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA256 hash as hex string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            # Read file in chunks to handle large files
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def compute_content_hash(self, content: bytes) -> str:
        """
        Compute SHA256 hash of content bytes.
        
        Args:
            content: File content as bytes
            
        Returns:
            SHA256 hash as hex string
        """
        return hashlib.sha256(content).hexdigest()
    
    def get_extraction_cache_path(self, file_hash: str) -> Path:
        """Get local cache file path for extraction results."""
        return self.extraction_cache_dir / f"{file_hash}_extraction.json"
    
    def get_chatbot_cache_path(self, file_hash: str) -> Path:
        """Get local cache file path for chatbot data."""
        return self.chatbot_cache_dir / f"{file_hash}_chatbot.json"
    
    def _get_gcs_extraction_path(self, file_hash: str) -> str:
        """Get GCS path for extraction cache."""
        return f"{self.gcs_cache_bucket}extraction_cache/{file_hash}_extraction.json"
    
    def _get_gcs_chatbot_path(self, file_hash: str) -> str:
        """Get GCS path for chatbot cache."""
        return f"{self.gcs_cache_bucket}chatbot_cache/{file_hash}_chatbot.json"
    
    def _get_gcs_extractions_data_path(self) -> str:
        """Get GCS path for extractions_data.json."""
        return f"{self.gcs_cache_bucket}extractions_data.json"
    
    def _save_to_gcs(self, gcs_path: str, data: Dict[str, Any]) -> bool:
        """Save JSON data to GCS."""
        if not self.use_gcs:
            return False
        
        try:
            from urllib.parse import urlparse
            
            # Parse GCS URI
            parsed = urlparse(gcs_path)
            bucket_name = parsed.netloc
            blob_name = parsed.path.lstrip('/')
            
            # Get GCS client and upload
            client = get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Upload JSON content
            json_content = json.dumps(data, indent=2, ensure_ascii=False, default=str)
            blob.upload_from_string(json_content, content_type='application/json')
            
            print(f"[CACHE] Saved to GCS: {blob_name}")
            return True
        except Exception as e:
            print(f"[CACHE] Error saving to GCS: {e}")
            return False
    
    def _load_from_gcs(self, gcs_path: str) -> Optional[Dict[str, Any]]:
        """Load JSON data from GCS."""
        if not self.use_gcs:
            return None
        
        try:
            from urllib.parse import urlparse
            
            # Parse GCS URI
            parsed = urlparse(gcs_path)
            bucket_name = parsed.netloc
            blob_name = parsed.path.lstrip('/')
            
            # Get GCS client and download
            client = get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                return None
            
            # Download and parse JSON
            json_content = blob.download_as_text()
            data = json.loads(json_content)
            
            print(f"[CACHE] Loaded from GCS: {blob_name}")
            return data
        except Exception as e:
            print(f"[CACHE] Error loading from GCS: {e}")
            return None
    
    def load_extraction_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Load extraction results from cache.
        
        Args:
            file_hash: SHA256 hash of file content
            
        Returns:
            Cached extraction data or None if not found
        """
        # Try GCS first if enabled
        if self.use_gcs:
            gcs_path = self._get_gcs_extraction_path(file_hash)
            gcs_data = self._load_from_gcs(gcs_path)
            if gcs_data:
                return gcs_data
        
        # Fall back to local cache
        cache_path = self.get_extraction_cache_path(file_hash)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"[CACHE] Loaded extraction cache (local) for hash: {file_hash[:16]}...")
            return cache_data
        except Exception as e:
            print(f"[CACHE] Error loading extraction cache: {e}")
            return None
    
    def save_extraction_cache(self, file_hash: str, extracted_data: Dict[str, Any], 
                             metadata: Dict[str, Any], document_text: str):
        """
        Save extraction results to cache.
        
        Args:
            file_hash: SHA256 hash of file content
            extracted_data: Extracted data dictionary
            metadata: Metadata dictionary
            document_text: Full document text
        """
        try:
            cache_data = {
                "file_hash": file_hash,
                "cached_at": datetime.now().isoformat(),
                "extracted_data": extracted_data,
                "metadata": metadata,
                "document_text": document_text
            }
            
            # Save to GCS if enabled
            if self.use_gcs:
                gcs_path = self._get_gcs_extraction_path(file_hash)
                self._save_to_gcs(gcs_path, cache_data)
            
            # Also save locally (for faster access and as fallback)
            cache_path = self.get_extraction_cache_path(file_hash)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CACHE] Saved extraction cache for hash: {file_hash[:16]}...")
        except Exception as e:
            print(f"[CACHE] Error saving extraction cache: {e}")
    
    def load_chatbot_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Load chatbot data from cache.
        
        Args:
            file_hash: SHA256 hash of file content
            
        Returns:
            Cached chatbot data or None if not found
        """
        # Try GCS first if enabled
        if self.use_gcs:
            gcs_path = self._get_gcs_chatbot_path(file_hash)
            gcs_data = self._load_from_gcs(gcs_path)
            if gcs_data:
                return gcs_data
        
        # Fall back to local cache
        cache_path = self.get_chatbot_cache_path(file_hash)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"[CACHE] Loaded chatbot cache (local) for hash: {file_hash[:16]}...")
            return cache_data
        except Exception as e:
            print(f"[CACHE] Error loading chatbot cache: {e}")
            return None
    
    def save_chatbot_cache(self, file_hash: str, document_text: str, page_map: Dict[int, str],
                          chunks: list, tables: list, is_scanned: bool, used_ocr: bool,
                          filename: str):
        """
        Save chatbot data to cache.
        
        Args:
            file_hash: SHA256 hash of file content
            document_text: Full document text
            page_map: Page number to text mapping
            chunks: List of text chunks
            tables: List of extracted tables
            is_scanned: Whether document is scanned
            used_ocr: Whether OCR was used
            filename: Original filename
        """
        try:
            cache_data = {
                "file_hash": file_hash,
                "filename": filename,
                "cached_at": datetime.now().isoformat(),
                "document_text": document_text,
                "page_map": {str(k): v for k, v in page_map.items()},  # Convert keys to strings
                "chunks": chunks,
                "tables": tables,
                "is_scanned": is_scanned,
                "used_ocr": used_ocr,
                "metadata": {
                    "document_length": len(document_text),
                    "total_pages": len(page_map),
                    "total_chunks": len(chunks),
                    "total_tables": len(tables)
                }
            }
            
            # Save to GCS if enabled
            if self.use_gcs:
                gcs_path = self._get_gcs_chatbot_path(file_hash)
                self._save_to_gcs(gcs_path, cache_data)
            
            # Also save locally (for faster access and as fallback)
            cache_path = self.get_chatbot_cache_path(file_hash)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CACHE] Saved chatbot cache for hash: {file_hash[:16]}...")
        except Exception as e:
            print(f"[CACHE] Error saving chatbot cache: {e}")
    
    def load_extractions_data(self) -> list:
        """
        Load extractions_data.json from GCS or local storage.
        
        Returns:
            List of extraction records
        """
        # Try GCS first if enabled
        if self.use_gcs:
            gcs_path = self._get_gcs_extractions_data_path()
            gcs_data = self._load_from_gcs(gcs_path)
            if gcs_data and isinstance(gcs_data, list):
                print(f"[CACHE] Loaded extractions_data from GCS ({len(gcs_data)} records)")
                return gcs_data
        
        # Fall back to local file
        local_path = self.cache_base_dir / "extractions_data.json"
        if local_path.exists():
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"[CACHE] Loaded extractions_data from local ({len(data)} records)")
                    return data
            except Exception as e:
                print(f"[CACHE] Error loading local extractions_data: {e}")
        
        return []
    
    def save_extractions_data(self, data: list):
        """
        Save extractions_data.json to GCS and local storage.
        
        Args:
            data: List of extraction records
        """
        try:
            # Save to GCS if enabled
            if self.use_gcs:
                gcs_path = self._get_gcs_extractions_data_path()
                self._save_to_gcs(gcs_path, data)
            
            # Also save locally
            local_path = self.cache_base_dir / "extractions_data.json"
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CACHE] Saved extractions_data ({len(data)} records)")
        except Exception as e:
            print(f"[CACHE] Error saving extractions_data: {e}")
    
    def _get_gcs_excel_export_path(self, filename: str = "contract_extractions.xlsx") -> str:
        """Get GCS path for Excel export."""
        return f"{self.gcs_cache_bucket}exports/{filename}"
    
    def save_excel_to_gcs(self, local_file_path: str, filename: str = "contract_extractions.xlsx") -> bool:
        """
        Save Excel file to GCS.
        
        Args:
            local_file_path: Path to the local Excel file
            filename: Name of the file in GCS
            
        Returns:
            True if saved to GCS successfully
        """
        if not self.use_gcs:
            return False
        
        try:
            from urllib.parse import urlparse
            
            gcs_path = self._get_gcs_excel_export_path(filename)
            
            # Parse GCS URI
            parsed = urlparse(gcs_path)
            bucket_name = parsed.netloc
            blob_name = parsed.path.lstrip('/')
            
            # Get GCS client and upload
            client = get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            # Upload file
            blob.upload_from_filename(local_file_path, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
            print(f"[CACHE] Saved Excel to GCS: {blob_name}")
            return True
        except Exception as e:
            print(f"[CACHE] Error saving Excel to GCS: {e}")
            return False
    
    def load_excel_from_gcs(self, filename: str = "contract_extractions.xlsx") -> Optional[str]:
        """
        Load Excel file from GCS to a temporary local path.
        
        Args:
            filename: Name of the file in GCS
            
        Returns:
            Local file path if downloaded successfully, None otherwise
        """
        if not self.use_gcs:
            return None
        
        try:
            from urllib.parse import urlparse
            import tempfile
            
            gcs_path = self._get_gcs_excel_export_path(filename)
            
            # Parse GCS URI
            parsed = urlparse(gcs_path)
            bucket_name = parsed.netloc
            blob_name = parsed.path.lstrip('/')
            
            # Get GCS client and download
            client = get_gcs_client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            
            if not blob.exists():
                print(f"[CACHE] Excel file not found in GCS: {blob_name}")
                return None
            
            # Download to temp file
            local_path = self.cache_base_dir / filename
            blob.download_to_filename(str(local_path))
            
            print(f"[CACHE] Loaded Excel from GCS: {blob_name}")
            return str(local_path)
        except Exception as e:
            print(f"[CACHE] Error loading Excel from GCS: {e}")
            return None
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        Clear cache files.
        
        Args:
            cache_type: 'extraction', 'chatbot', or None for both
        """
        if cache_type is None or cache_type == "extraction":
            for cache_file in self.extraction_cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"[CACHE] Cleared local extraction cache")
        
        if cache_type is None or cache_type == "chatbot":
            for cache_file in self.chatbot_cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"[CACHE] Cleared local chatbot cache")
        
        # Note: GCS cache is not cleared automatically for safety


# Singleton instance
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the cache manager singleton instance."""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
    return _cache_manager_instance
