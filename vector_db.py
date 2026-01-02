"""
FAISS Vector Database for Contract Documents
Handles semantic chunking, embedding, and vector storage for efficient semantic search.
"""

import os
import json
import pickle
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import numpy as np
from openai import OpenAI

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    print("Warning: FAISS not available. Install with: pip install faiss-cpu")


class VectorDB:
    """FAISS-based vector database for contract document chunks."""
    
    def __init__(self, api_key: Optional[str] = None, db_path: str = "vector_db"):
        """
        Initialize the vector database.
        
        Args:
            api_key: OpenAI API key for embeddings
            db_path: Path to store the vector database files
        """
        if not FAISS_AVAILABLE:
            raise ImportError("FAISS is required. Install with: pip install faiss-cpu")
        
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = "text-embedding-3-small"
        # text-embedding-3-small has 1536 dimensions by default
        self.embedding_dim = 1536
        self.db_path = Path(db_path)
        self.db_path.mkdir(exist_ok=True)
        
        # FAISS index
        self.index = None
        self.metadata = []  # Store chunk metadata (text, page, start_index, etc.)
        self.document_id = None
        
    def create_index(self, dimension: Optional[int] = None):
        """Create a new FAISS index."""
        dim = dimension or self.embedding_dim
        # Use L2 (Euclidean) distance index
        self.index = faiss.IndexFlatL2(dim)
        self.metadata = []
    
    def chunk_document(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[Dict[str, any]]:
        """
        Split document into semantic chunks with metadata.
        
        Args:
            text: Document text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        chunks = []
        start = 0
        chunk_id = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            
            if chunk_text:  # Only add non-empty chunks
                chunks.append({
                    'id': chunk_id,
                    'text': chunk_text,
                    'start_index': start,
                    'end_index': end,
                    'length': len(chunk_text)
                })
                chunk_id += 1
            
            start += chunk_size - overlap
        
        return chunks
    
    def get_embeddings(self, texts: List[str], batch_size: int = 100) -> np.ndarray:
        """
        Get embeddings for a list of texts in batches.
        
        Args:
            texts: List of text strings to embed
            batch_size: Number of texts to process per batch
            
        Returns:
            NumPy array of embeddings
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                response = self.client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                raise ValueError(f"Error getting embeddings for batch {i}: {str(e)}")
        
        return np.array(all_embeddings, dtype=np.float32)
    
    def add_document(self, document_text: str, document_id: str, page_map: Optional[Dict[int, str]] = None, 
                     chunk_size: int = 500, overlap: int = 100):
        """
        Add a document to the vector database.
        
        Args:
            document_text: Full document text
            document_id: Unique identifier for the document
            page_map: Optional mapping of page numbers to text
            chunk_size: Size of chunks in characters
            overlap: Overlap between chunks
        """
        # Create new index for this document
        self.create_index()
        self.document_id = document_id
        
        # Chunk the document
        chunks = self.chunk_document(document_text, chunk_size=chunk_size, overlap=overlap)
        
        if not chunks:
            return
        
        # Get chunk texts
        chunk_texts = [chunk['text'] for chunk in chunks]
        
        # Get embeddings
        print(f"Creating embeddings for {len(chunks)} chunks...")
        embeddings = self.get_embeddings(chunk_texts)
        
        # Add to FAISS index
        self.index.add(embeddings)
        
        # Store metadata with page information
        for i, chunk in enumerate(chunks):
            # Find page number for this chunk
            page_num = None
            if page_map:
                page_num = self._find_page_for_chunk(chunk['start_index'], document_text, page_map)
            
            metadata = {
                'chunk_id': chunk['id'],
                'text': chunk['text'],
                'start_index': chunk['start_index'],
                'end_index': chunk['end_index'],
                'page': page_num,
                'document_id': document_id
            }
            self.metadata.append(metadata)
        
        print(f"Added {len(chunks)} chunks to vector database")
    
    def _find_page_for_chunk(self, char_index: int, document_text: str, page_map: Dict[int, str]) -> Optional[int]:
        """Find the page number for a character index."""
        cumulative_pos = 0
        for page_num in sorted(page_map.keys()):
            page_text = page_map[page_num]
            page_length = len(page_text)
            
            if cumulative_pos <= char_index < cumulative_pos + page_length:
                return page_num
            
            cumulative_pos += page_length + 1  # +1 for separator
        
        return None
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, any]]:
        """
        Search the vector database for similar chunks.
        
        Args:
            query: Search query text
            top_k: Number of results to return
            
        Returns:
            List of similar chunks with metadata and similarity scores
        """
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # Get query embedding
        query_embedding = self.get_embeddings([query])
        
        # Search in FAISS
        distances, indices = self.index.search(query_embedding, min(top_k, self.index.ntotal))
        
        # Get results with metadata
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                metadata = self.metadata[idx].copy()
                # Convert L2 distance to similarity score (lower distance = higher similarity)
                distance = float(distances[0][i])
                # Normalize to 0-1 range (inverse of normalized distance)
                similarity = 1.0 / (1.0 + distance)
                metadata['similarity'] = similarity
                metadata['distance'] = distance
                results.append(metadata)
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return results
    
    def save(self, filename: Optional[str] = None):
        """Save the vector database to disk."""
        if self.index is None:
            return
        
        filename = filename or f"{self.document_id}_vector_db" if self.document_id else "vector_db"
        index_path = self.db_path / f"{filename}.index"
        metadata_path = self.db_path / f"{filename}_metadata.pkl"
        
        # Save FAISS index
        faiss.write_index(self.index, str(index_path))
        
        # Save metadata
        with open(metadata_path, 'wb') as f:
            pickle.dump(self.metadata, f)
        
        # Save document info
        info = {
            'document_id': self.document_id,
            'embedding_model': self.embedding_model,
            'embedding_dim': self.embedding_dim,
            'num_chunks': len(self.metadata)
        }
        info_path = self.db_path / f"{filename}_info.json"
        with open(info_path, 'w') as f:
            json.dump(info, f, indent=2)
        
        print(f"Vector database saved to {self.db_path}")
    
    def load(self, filename: Optional[str] = None):
        """Load the vector database from disk."""
        filename = filename or f"{self.document_id}_vector_db" if self.document_id else "vector_db"
        index_path = self.db_path / f"{filename}.index"
        metadata_path = self.db_path / f"{filename}_metadata.pkl"
        
        if not index_path.exists() or not metadata_path.exists():
            raise FileNotFoundError(f"Vector database not found: {filename}")
        
        # Load FAISS index
        self.index = faiss.read_index(str(index_path))
        
        # Load metadata
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        
        # Load document info
        info_path = self.db_path / f"{filename}_info.json"
        if info_path.exists():
            with open(info_path, 'r') as f:
                info = json.load(f)
                self.document_id = info.get('document_id')
        
        print(f"Vector database loaded: {len(self.metadata)} chunks")
    
    def clear(self):
        """Clear the vector database."""
        self.create_index()
        self.metadata = []
        self.document_id = None

