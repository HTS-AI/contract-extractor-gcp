"""
Cache Manager for Document Processing
Handles content-based caching to avoid re-processing the same files.
Uses SHA256 hash of file content as cache key.
"""

import os
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime


class CacheManager:
    """Manages caching of document processing results."""
    
    def __init__(self, cache_base_dir: Optional[Path] = None):
        """
        Initialize cache manager.
        
        Args:
            cache_base_dir: Base directory for cache (defaults to project root)
        """
        if cache_base_dir is None:
            cache_base_dir = Path(__file__).parent
        
        self.cache_base_dir = cache_base_dir
        self.extraction_cache_dir = cache_base_dir / "extraction_cache"
        self.chatbot_cache_dir = cache_base_dir / "chatbot_cache"
        
        # Create cache directories
        self.extraction_cache_dir.mkdir(exist_ok=True)
        self.chatbot_cache_dir.mkdir(exist_ok=True)
        
        print(f"[CACHE] Extraction cache: {self.extraction_cache_dir.absolute()}")
        print(f"[CACHE] Chatbot cache: {self.chatbot_cache_dir.absolute()}")
    
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
        """Get cache file path for extraction results."""
        return self.extraction_cache_dir / f"{file_hash}_extraction.json"
    
    def get_chatbot_cache_path(self, file_hash: str) -> Path:
        """Get cache file path for chatbot data."""
        return self.chatbot_cache_dir / f"{file_hash}_chatbot.json"
    
    def load_extraction_cache(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Load extraction results from cache.
        
        Args:
            file_hash: SHA256 hash of file content
            
        Returns:
            Cached extraction data or None if not found
        """
        cache_path = self.get_extraction_cache_path(file_hash)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"[CACHE] Loaded extraction cache for hash: {file_hash[:16]}...")
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
        cache_path = self.get_chatbot_cache_path(file_hash)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            print(f"[CACHE] Loaded chatbot cache for hash: {file_hash[:16]}...")
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
            
            cache_path = self.get_chatbot_cache_path(file_hash)
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CACHE] Saved chatbot cache for hash: {file_hash[:16]}...")
        except Exception as e:
            print(f"[CACHE] Error saving chatbot cache: {e}")
    
    def clear_cache(self, cache_type: Optional[str] = None):
        """
        Clear cache files.
        
        Args:
            cache_type: 'extraction', 'chatbot', or None for both
        """
        if cache_type is None or cache_type == "extraction":
            for cache_file in self.extraction_cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"[CACHE] Cleared extraction cache")
        
        if cache_type is None or cache_type == "chatbot":
            for cache_file in self.chatbot_cache_dir.glob("*.json"):
                cache_file.unlink()
            print(f"[CACHE] Cleared chatbot cache")


# Singleton instance
_cache_manager_instance: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the cache manager singleton instance."""
    global _cache_manager_instance
    if _cache_manager_instance is None:
        _cache_manager_instance = CacheManager()
    return _cache_manager_instance

