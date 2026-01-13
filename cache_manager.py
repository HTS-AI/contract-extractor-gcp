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
    
    # ========================================================================
    # INDIVIDUAL EXTRACTION FILE MANAGEMENT (New approach)
    # ========================================================================
    
    def _get_extractions_dir(self) -> Path:
        """Get local extractions directory."""
        extractions_dir = self.cache_base_dir / "extractions"
        extractions_dir.mkdir(exist_ok=True)
        return extractions_dir
    
    def _get_gcs_extraction_record_path(self, extraction_id: str) -> str:
        """Get GCS path for individual extraction record."""
        return f"{self.gcs_cache_bucket}extractions/{extraction_id}.json"
    
    def save_extraction_record(self, extraction_id: str, data: Dict[str, Any]) -> bool:
        """
        Save individual extraction record to both local and GCS.
        
        Args:
            extraction_id: Unique extraction ID
            data: Extraction data dictionary
            
        Returns:
            True if saved successfully
        """
        try:
            # Ensure extraction_id is in the data
            data["extraction_id"] = extraction_id
            
            # Save to GCS if enabled
            if self.use_gcs:
                gcs_path = self._get_gcs_extraction_record_path(extraction_id)
                self._save_to_gcs(gcs_path, data)
            
            # Also save locally
            local_path = self._get_extractions_dir() / f"{extraction_id}.json"
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CACHE] Saved extraction record: {extraction_id}")
            return True
        except Exception as e:
            print(f"[CACHE] Error saving extraction record {extraction_id}: {e}")
            return False
    
    def load_extraction_record(self, extraction_id: str) -> Optional[Dict[str, Any]]:
        """
        Load individual extraction record from GCS or local.
        
        Args:
            extraction_id: Unique extraction ID
            
        Returns:
            Extraction data or None if not found
        """
        # Try GCS first if enabled
        if self.use_gcs:
            gcs_path = self._get_gcs_extraction_record_path(extraction_id)
            gcs_data = self._load_from_gcs(gcs_path)
            if gcs_data:
                return gcs_data
        
        # Fall back to local
        local_path = self._get_extractions_dir() / f"{extraction_id}.json"
        if local_path.exists():
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[CACHE] Error loading extraction record {extraction_id}: {e}")
        
        return None
    
    def delete_extraction_record_file(self, extraction_id: str, delete_local: bool = True, delete_gcs: bool = True) -> Tuple[bool, str]:
        """
        Delete individual extraction record file from local and/or GCS.
        
        Args:
            extraction_id: Unique extraction ID
            delete_local: Whether to delete from local storage
            delete_gcs: Whether to delete from GCS
            
        Returns:
            Tuple of (success, message)
        """
        deleted = []
        failed = []
        
        # Delete from local
        if delete_local:
            local_path = self._get_extractions_dir() / f"{extraction_id}.json"
            if local_path.exists():
                try:
                    local_path.unlink()
                    deleted.append("local")
                except Exception as e:
                    failed.append(f"local: {e}")
        
        # Delete from GCS
        if delete_gcs and self.use_gcs:
            gcs_path = self._get_gcs_extraction_record_path(extraction_id)
            success, msg = self.delete_file(gcs_path, "gcs")
            if success:
                deleted.append("gcs")
            else:
                failed.append(f"gcs: {msg}")
        
        if deleted:
            return True, f"Deleted from: {', '.join(deleted)}"
        elif failed:
            return False, f"Failed: {', '.join(failed)}"
        else:
            return False, "No files found to delete"
    
    def list_extraction_records(self) -> list:
        """
        List all individual extraction records from both local and GCS.
        
        Returns:
            List of extraction records with metadata
        """
        records = []
        seen_ids = set()
        
        # List from GCS first if enabled
        if self.use_gcs:
            try:
                from urllib.parse import urlparse
                
                parsed = urlparse(self.gcs_cache_bucket)
                bucket_name = parsed.netloc
                prefix = parsed.path.lstrip('/') + "extractions/"
                
                client = get_gcs_client()
                bucket = client.bucket(bucket_name)
                
                blobs = bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    if blob.name.endswith('.json') and not blob.name.endswith('/.json'):
                        extraction_id = blob.name.split('/')[-1].replace('.json', '')
                        if extraction_id and extraction_id not in seen_ids:
                            seen_ids.add(extraction_id)
                            
                            # Try to load the record to get metadata
                            try:
                                json_content = blob.download_as_text()
                                data = json.loads(json_content)
                                records.append({
                                    "extraction_id": extraction_id,
                                    "file_name": data.get("file_name", "Unknown"),
                                    "file_hash": data.get("file_hash", ""),
                                    "extracted_at": data.get("extracted_at", ""),
                                    "uploaded_at": data.get("uploaded_at", ""),
                                    "status": data.get("status", ""),
                                    "location": "gcs",
                                    "size": blob.size or 0,
                                    "modified": blob.updated.isoformat() if blob.updated else ""
                                })
                            except:
                                records.append({
                                    "extraction_id": extraction_id,
                                    "file_name": "Unknown",
                                    "location": "gcs",
                                    "size": blob.size or 0
                                })
            except Exception as e:
                print(f"[CACHE] Error listing GCS extraction records: {e}")
        
        # List from local
        extractions_dir = self._get_extractions_dir()
        for json_file in extractions_dir.glob("*.json"):
            extraction_id = json_file.stem
            if extraction_id not in seen_ids:
                seen_ids.add(extraction_id)
                try:
                    stat = json_file.stat()
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    records.append({
                        "extraction_id": extraction_id,
                        "file_name": data.get("file_name", "Unknown"),
                        "file_hash": data.get("file_hash", ""),
                        "extracted_at": data.get("extracted_at", ""),
                        "uploaded_at": data.get("uploaded_at", ""),
                        "status": data.get("status", ""),
                        "location": "local",
                        "size": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                except Exception as e:
                    records.append({
                        "extraction_id": extraction_id,
                        "file_name": "Unknown",
                        "location": "local"
                    })
        
        # Sort by extracted_at (most recent first)
        records.sort(key=lambda x: x.get("extracted_at", "") or x.get("uploaded_at", ""), reverse=True)
        
        print(f"[CACHE] Listed {len(records)} extraction records")
        return records
    
    def clear_all_extraction_records(self, clear_local: bool = True, clear_gcs: bool = True) -> Dict[str, Any]:
        """
        Clear all individual extraction record files.
        
        Returns:
            Dictionary with deletion results
        """
        results = {
            "local_deleted": 0,
            "gcs_deleted": 0,
            "errors": []
        }
        
        # Clear local
        if clear_local:
            extractions_dir = self._get_extractions_dir()
            for json_file in extractions_dir.glob("*.json"):
                try:
                    json_file.unlink()
                    results["local_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"local:{json_file.name}: {e}")
        
        # Clear GCS
        if clear_gcs and self.use_gcs:
            try:
                from urllib.parse import urlparse
                
                parsed = urlparse(self.gcs_cache_bucket)
                bucket_name = parsed.netloc
                prefix = parsed.path.lstrip('/') + "extractions/"
                
                client = get_gcs_client()
                bucket = client.bucket(bucket_name)
                
                blobs = bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    if blob.name.endswith('.json'):
                        try:
                            blob.delete()
                            results["gcs_deleted"] += 1
                        except Exception as e:
                            results["errors"].append(f"gcs:{blob.name}: {e}")
            except Exception as e:
                results["errors"].append(f"gcs list: {e}")
        
        return results
    
    # ========================================================================
    # LEGACY: Keep for backward compatibility during migration
    # ========================================================================
    
    def load_extractions_data(self) -> list:
        """
        Load full extractions from individual files (new) or extractions_data.json (legacy).
        
        Returns:
            List of full extraction records with all data
        """
        # First, try loading full data from individual files (new approach)
        full_records = self._load_all_extraction_records()
        if full_records:
            print(f"[CACHE] Loaded {len(full_records)} full extractions from individual files")
            return full_records
        
        # Fall back to legacy extractions_data.json
        # Try GCS first if enabled
        if self.use_gcs:
            gcs_path = self._get_gcs_extractions_data_path()
            gcs_data = self._load_from_gcs(gcs_path)
            if gcs_data and isinstance(gcs_data, list):
                print(f"[CACHE] Loaded extractions_data from GCS (legacy) ({len(gcs_data)} records)")
                # Migrate to individual files
                self._migrate_to_individual_files(gcs_data)
                return gcs_data
        
        # Fall back to local file
        local_path = self.cache_base_dir / "extractions_data.json"
        if local_path.exists():
            try:
                with open(local_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"[CACHE] Loaded extractions_data from local (legacy) ({len(data)} records)")
                    # Migrate to individual files
                    self._migrate_to_individual_files(data)
                    return data
            except Exception as e:
                print(f"[CACHE] Error loading local extractions_data: {e}")
        
        return []
    
    def _load_all_extraction_records(self) -> list:
        """
        Load full content of all individual extraction record files.
        
        Returns:
            List of full extraction records with all data (results, status, etc.)
        """
        records = []
        seen_ids = set()
        
        # Load from GCS first if enabled
        if self.use_gcs:
            try:
                from urllib.parse import urlparse
                
                parsed = urlparse(self.gcs_cache_bucket)
                bucket_name = parsed.netloc
                prefix = parsed.path.lstrip('/') + "extractions/"
                
                client = get_gcs_client()
                bucket = client.bucket(bucket_name)
                
                blobs = bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    if blob.name.endswith('.json') and not blob.name.endswith('/.json'):
                        extraction_id = blob.name.split('/')[-1].replace('.json', '')
                        if extraction_id and extraction_id not in seen_ids:
                            seen_ids.add(extraction_id)
                            try:
                                json_content = blob.download_as_text()
                                data = json.loads(json_content)
                                # Ensure extraction_id is in the data
                                data["extraction_id"] = extraction_id
                                records.append(data)
                            except Exception as e:
                                print(f"[CACHE] Error loading GCS extraction {extraction_id}: {e}")
            except Exception as e:
                print(f"[CACHE] Error listing GCS extraction records: {e}")
        
        # Load from local extractions folder
        extractions_dir = self._get_extractions_dir()
        for json_file in extractions_dir.glob("*.json"):
            extraction_id = json_file.stem
            if extraction_id not in seen_ids:
                seen_ids.add(extraction_id)
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    # Ensure extraction_id is in the data
                    data["extraction_id"] = extraction_id
                    records.append(data)
                except Exception as e:
                    print(f"[CACHE] Error loading local extraction {extraction_id}: {e}")
        
        # Sort by extracted_at (most recent first)
        records.sort(key=lambda x: x.get("extracted_at", "") or x.get("uploaded_at", ""), reverse=True)
        
        return records
    
    def _migrate_to_individual_files(self, data: list):
        """Migrate legacy extractions_data.json to individual files."""
        print(f"[CACHE] Migrating {len(data)} extractions to individual files...")
        for item in data:
            extraction_id = item.get("extraction_id")
            if extraction_id:
                self.save_extraction_record(extraction_id, item)
        print(f"[CACHE] Migration complete")
    
    def save_extractions_data(self, data: list):
        """
        Save extractions as individual files (new approach).
        Also maintains legacy extractions_data.json for backward compatibility.
        
        Args:
            data: List of extraction records
        """
        try:
            # Save each record as individual file
            for item in data:
                extraction_id = item.get("extraction_id")
                if extraction_id:
                    self.save_extraction_record(extraction_id, item)
            
            # Also save legacy format for backward compatibility
            if self.use_gcs:
                gcs_path = self._get_gcs_extractions_data_path()
                self._save_to_gcs(gcs_path, data)
            
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
    
    def list_all_cached_files(self) -> Dict[str, Any]:
        """
        List all cached files from both local storage and GCS.
        
        Returns:
            Dictionary with categorized file lists
        """
        result = {
            "extraction_cache": [],
            "chatbot_cache": [],
            "extractions_data": [],
            "exports": [],
            "gcs_enabled": self.use_gcs,
            "gcs_bucket": self.gcs_cache_bucket if self.use_gcs else ""
        }
        
        # List local extraction cache files
        for cache_file in self.extraction_cache_dir.glob("*.json"):
            try:
                stat = cache_file.stat()
                # Try to read file to get filename
                filename = "Unknown"
                file_hash = cache_file.stem.replace("_extraction", "")
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        filename = data.get("metadata", {}).get("file_name", 
                                   data.get("metadata", {}).get("filename", "Unknown"))
                except:
                    pass
                
                result["extraction_cache"].append({
                    "name": cache_file.name,
                    "path": str(cache_file),
                    "file_hash": file_hash,
                    "original_filename": filename,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "location": "local"
                })
            except Exception as e:
                print(f"[CACHE] Error reading file info: {e}")
        
        # List local chatbot cache files
        for cache_file in self.chatbot_cache_dir.glob("*.json"):
            try:
                stat = cache_file.stat()
                filename = "Unknown"
                file_hash = cache_file.stem.replace("_chatbot", "")
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        filename = data.get("filename", "Unknown")
                except:
                    pass
                
                result["chatbot_cache"].append({
                    "name": cache_file.name,
                    "path": str(cache_file),
                    "file_hash": file_hash,
                    "original_filename": filename,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "location": "local"
                })
            except Exception as e:
                print(f"[CACHE] Error reading file info: {e}")
        
        # List individual extraction record files (new approach)
        result["extraction_records"] = self.list_extraction_records()
        
        # Also list legacy extractions_data.json for cleanup purposes
        local_extractions = self.cache_base_dir / "extractions_data.json"
        if local_extractions.exists():
            stat = local_extractions.stat()
            try:
                with open(local_extractions, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    record_count = len(data) if isinstance(data, list) else 0
            except:
                record_count = 0
            
            result["extractions_data"].append({
                "name": "extractions_data.json (legacy)",
                "path": str(local_extractions),
                "size": stat.st_size,
                "record_count": record_count,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "location": "local",
                "is_legacy": True
            })
        
        # List local Excel exports
        local_excel = self.cache_base_dir / "contract_extractions.xlsx"
        if local_excel.exists():
            stat = local_excel.stat()
            result["exports"].append({
                "name": "contract_extractions.xlsx",
                "path": str(local_excel),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "location": "local"
            })
        
        # List GCS files if enabled
        if self.use_gcs:
            try:
                self._list_gcs_files(result)
            except Exception as e:
                print(f"[CACHE] Error listing GCS files: {e}")
        
        return result
    
    def _list_gcs_files(self, result: Dict[str, Any]):
        """List files from GCS bucket."""
        from urllib.parse import urlparse
        
        try:
            parsed = urlparse(self.gcs_cache_bucket)
            bucket_name = parsed.netloc
            prefix = parsed.path.lstrip('/')
            
            client = get_gcs_client()
            bucket = client.bucket(bucket_name)
            
            # List all blobs with the cache prefix
            blobs = bucket.list_blobs(prefix=prefix)
            
            for blob in blobs:
                blob_name = blob.name
                
                # Categorize by folder
                if "extraction_cache/" in blob_name and blob_name.endswith(".json"):
                    file_hash = blob_name.split("/")[-1].replace("_extraction.json", "")
                    result["extraction_cache"].append({
                        "name": blob_name.split("/")[-1],
                        "path": f"gs://{bucket_name}/{blob_name}",
                        "file_hash": file_hash,
                        "original_filename": "GCS file",
                        "size": blob.size or 0,
                        "modified": blob.updated.isoformat() if blob.updated else "",
                        "location": "gcs"
                    })
                elif "chatbot_cache/" in blob_name and blob_name.endswith(".json"):
                    file_hash = blob_name.split("/")[-1].replace("_chatbot.json", "")
                    result["chatbot_cache"].append({
                        "name": blob_name.split("/")[-1],
                        "path": f"gs://{bucket_name}/{blob_name}",
                        "file_hash": file_hash,
                        "original_filename": "GCS file",
                        "size": blob.size or 0,
                        "modified": blob.updated.isoformat() if blob.updated else "",
                        "location": "gcs"
                    })
                elif blob_name.endswith("extractions_data.json"):
                    result["extractions_data"].append({
                        "name": "extractions_data.json (legacy)",
                        "path": f"gs://{bucket_name}/{blob_name}",
                        "size": blob.size or 0,
                        "modified": blob.updated.isoformat() if blob.updated else "",
                        "location": "gcs",
                        "is_legacy": True
                    })
                elif "exports/" in blob_name and blob_name.endswith(".xlsx"):
                    result["exports"].append({
                        "name": blob_name.split("/")[-1],
                        "path": f"gs://{bucket_name}/{blob_name}",
                        "size": blob.size or 0,
                        "modified": blob.updated.isoformat() if blob.updated else "",
                        "location": "gcs"
                    })
                    
        except Exception as e:
            print(f"[CACHE] Error listing GCS files: {e}")
    
    def delete_file(self, file_path: str, location: str) -> Tuple[bool, str]:
        """
        Delete a specific file from local or GCS storage.
        
        Args:
            file_path: Path to the file (local path or GCS URI)
            location: 'local' or 'gcs'
            
        Returns:
            Tuple of (success, message)
        """
        try:
            if location == "local":
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    print(f"[CACHE] Deleted local file: {file_path}")
                    return True, f"Deleted: {path.name}"
                else:
                    return False, f"File not found: {file_path}"
            
            elif location == "gcs" and self.use_gcs:
                from urllib.parse import urlparse
                
                parsed = urlparse(file_path)
                bucket_name = parsed.netloc
                blob_name = parsed.path.lstrip('/')
                
                client = get_gcs_client()
                bucket = client.bucket(bucket_name)
                blob = bucket.blob(blob_name)
                
                if blob.exists():
                    blob.delete()
                    print(f"[CACHE] Deleted GCS file: {file_path}")
                    return True, f"Deleted: {blob_name.split('/')[-1]}"
                else:
                    return False, f"File not found in GCS: {file_path}"
            
            else:
                return False, f"Invalid location or GCS not enabled: {location}"
                
        except Exception as e:
            print(f"[CACHE] Error deleting file: {e}")
            return False, str(e)
    
    def delete_by_file_hash(self, file_hash: str, delete_local: bool = True, delete_gcs: bool = True) -> Dict[str, Any]:
        """
        Delete all cache files associated with a file hash.
        
        Args:
            file_hash: The SHA256 hash of the original file
            delete_local: Whether to delete local files
            delete_gcs: Whether to delete GCS files
            
        Returns:
            Dictionary with deletion results
        """
        results = {
            "file_hash": file_hash,
            "deleted": [],
            "failed": [],
            "extraction_deleted": False,
            "chatbot_deleted": False
        }
        
        # Delete local extraction cache
        if delete_local:
            extraction_path = self.get_extraction_cache_path(file_hash)
            if extraction_path.exists():
                try:
                    extraction_path.unlink()
                    results["deleted"].append(f"local:{extraction_path.name}")
                    results["extraction_deleted"] = True
                except Exception as e:
                    results["failed"].append(f"local:{extraction_path.name} - {e}")
            
            # Delete local chatbot cache
            chatbot_path = self.get_chatbot_cache_path(file_hash)
            if chatbot_path.exists():
                try:
                    chatbot_path.unlink()
                    results["deleted"].append(f"local:{chatbot_path.name}")
                    results["chatbot_deleted"] = True
                except Exception as e:
                    results["failed"].append(f"local:{chatbot_path.name} - {e}")
        
        # Delete GCS files
        if delete_gcs and self.use_gcs:
            try:
                from urllib.parse import urlparse
                
                # Delete extraction cache from GCS
                gcs_extraction_path = self._get_gcs_extraction_path(file_hash)
                success, msg = self.delete_file(gcs_extraction_path, "gcs")
                if success:
                    results["deleted"].append(f"gcs:extraction_cache/{file_hash}_extraction.json")
                    results["extraction_deleted"] = True
                
                # Delete chatbot cache from GCS
                gcs_chatbot_path = self._get_gcs_chatbot_path(file_hash)
                success, msg = self.delete_file(gcs_chatbot_path, "gcs")
                if success:
                    results["deleted"].append(f"gcs:chatbot_cache/{file_hash}_chatbot.json")
                    results["chatbot_deleted"] = True
                    
            except Exception as e:
                results["failed"].append(f"gcs: {e}")
        
        return results
    
    def delete_extraction_record(self, extraction_id: str) -> Tuple[bool, str]:
        """
        Delete an extraction record (individual file approach + legacy cleanup).
        
        Args:
            extraction_id: The extraction ID to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            deleted_items = []
            
            # Delete individual extraction file (new approach)
            success, msg = self.delete_extraction_record_file(extraction_id, delete_local=True, delete_gcs=True)
            if success:
                deleted_items.append("individual file")
            
            # Also clean up from legacy extractions_data.json if present
            try:
                # Local legacy file
                local_path = self.cache_base_dir / "extractions_data.json"
                if local_path.exists():
                    with open(local_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        original_count = len(data)
                        data = [item for item in data if item.get("extraction_id") != extraction_id]
                        if len(data) < original_count:
                            with open(local_path, 'w', encoding='utf-8') as f:
                                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
                            deleted_items.append("legacy local")
                
                # GCS legacy file
                if self.use_gcs:
                    gcs_path = self._get_gcs_extractions_data_path()
                    gcs_data = self._load_from_gcs(gcs_path)
                    if gcs_data and isinstance(gcs_data, list):
                        original_count = len(gcs_data)
                        gcs_data = [item for item in gcs_data if item.get("extraction_id") != extraction_id]
                        if len(gcs_data) < original_count:
                            self._save_to_gcs(gcs_path, gcs_data)
                            deleted_items.append("legacy gcs")
            except Exception as e:
                print(f"[CACHE] Legacy cleanup error: {e}")
            
            if deleted_items:
                return True, f"Deleted extraction record: {extraction_id} ({', '.join(deleted_items)})"
            else:
                return False, f"Extraction ID not found: {extraction_id}"
            
        except Exception as e:
            return False, str(e)
    
    def clear_all_cache(self, clear_local: bool = True, clear_gcs: bool = True, 
                        clear_extractions_data: bool = False) -> Dict[str, Any]:
        """
        Clear all cache files from both local and GCS storage.
        
        Args:
            clear_local: Whether to clear local cache
            clear_gcs: Whether to clear GCS cache
            clear_extractions_data: Whether to also clear extraction records
            
        Returns:
            Dictionary with deletion results
        """
        results = {
            "local_extraction_deleted": 0,
            "local_chatbot_deleted": 0,
            "local_extraction_records_deleted": 0,
            "gcs_extraction_deleted": 0,
            "gcs_chatbot_deleted": 0,
            "gcs_extraction_records_deleted": 0,
            "extractions_data_cleared": False,
            "errors": []
        }
        
        # Clear local cache
        if clear_local:
            try:
                for cache_file in self.extraction_cache_dir.glob("*.json"):
                    cache_file.unlink()
                    results["local_extraction_deleted"] += 1
            except Exception as e:
                results["errors"].append(f"Local extraction cache: {e}")
            
            try:
                for cache_file in self.chatbot_cache_dir.glob("*.json"):
                    cache_file.unlink()
                    results["local_chatbot_deleted"] += 1
            except Exception as e:
                results["errors"].append(f"Local chatbot cache: {e}")
            
            # Clear individual extraction record files if requested
            if clear_extractions_data:
                try:
                    extractions_dir = self._get_extractions_dir()
                    for json_file in extractions_dir.glob("*.json"):
                        json_file.unlink()
                        results["local_extraction_records_deleted"] += 1
                except Exception as e:
                    results["errors"].append(f"Local extraction records: {e}")
                
                # Also clear legacy extractions_data.json
                try:
                    local_legacy = self.cache_base_dir / "extractions_data.json"
                    if local_legacy.exists():
                        local_legacy.unlink()
                        results["extractions_data_cleared"] = True
                except Exception as e:
                    results["errors"].append(f"Local legacy file: {e}")
        
        # Clear GCS cache
        if clear_gcs and self.use_gcs:
            try:
                from urllib.parse import urlparse
                
                parsed = urlparse(self.gcs_cache_bucket)
                bucket_name = parsed.netloc
                prefix = parsed.path.lstrip('/')
                
                client = get_gcs_client()
                bucket = client.bucket(bucket_name)
                
                # List and delete all cache files
                blobs = bucket.list_blobs(prefix=prefix)
                for blob in blobs:
                    blob_name = blob.name
                    
                    # Skip extractions folder and extractions_data.json unless explicitly requested
                    if not clear_extractions_data:
                        if "extractions/" in blob_name or "extractions_data.json" in blob_name:
                            continue
                    
                    # Skip .gitkeep files
                    if ".gitkeep" in blob_name:
                        continue
                    
                    try:
                        blob.delete()
                        if "extraction_cache/" in blob_name:
                            results["gcs_extraction_deleted"] += 1
                        elif "chatbot_cache/" in blob_name:
                            results["gcs_chatbot_deleted"] += 1
                        elif "extractions/" in blob_name:
                            results["gcs_extraction_records_deleted"] += 1
                        elif "extractions_data.json" in blob_name:
                            results["extractions_data_cleared"] = True
                    except Exception as e:
                        results["errors"].append(f"GCS delete {blob_name}: {e}")
                        
            except Exception as e:
                results["errors"].append(f"GCS clear: {e}")
        
        # Clear extractions_data if requested
        if clear_extractions_data:
            try:
                self.save_extractions_data([])
                results["extractions_data_cleared"] = True
            except Exception as e:
                results["errors"].append(f"Clear extractions_data: {e}")
        
        return results


# Singleton instance
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the cache manager singleton instance."""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
    return _cache_manager_instance
