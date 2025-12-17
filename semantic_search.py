"""
Semantic Search Module for Contract Extraction
Uses FAISS vector database for efficient semantic search.
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
from openai import OpenAI

try:
    from vector_db import VectorDB
    VECTOR_DB_AVAILABLE = True
except ImportError:
    VECTOR_DB_AVAILABLE = False
    VectorDB = None


class SemanticSearcher:
    """Performs semantic search on contract documents using FAISS vector database."""
    
    def __init__(self, api_key: Optional[str] = None, use_faiss: bool = True):
        """
        Initialize the semantic searcher.
        
        Args:
            api_key: OpenAI API key. If None, will use OPENAI_API_KEY env var.
            use_faiss: Whether to use FAISS vector database (recommended)
        """
        self.client = OpenAI(api_key=api_key)
        self.embedding_model = "text-embedding-3-small"
        self.use_faiss = use_faiss and VECTOR_DB_AVAILABLE
        self.vector_db = None
        
        if self.use_faiss and VectorDB:
            self.vector_db = VectorDB(api_key=api_key)
    
    def initialize_vector_db(self, document_text: str, document_id: str, page_map: Optional[Dict[int, str]] = None):
        """
        Initialize vector database with document chunks and embeddings.
        
        Args:
            document_text: Full document text
            document_id: Unique identifier for the document
            page_map: Optional mapping of page numbers to text
        """
        if self.use_faiss and self.vector_db:
            self.vector_db.add_document(document_text, document_id, page_map=page_map)
            self.vector_db.save(document_id)
        else:
            raise ValueError("FAISS vector database not available. Install faiss-cpu or set use_faiss=False")
    
    def load_vector_db(self, document_id: str):
        """Load existing vector database for a document."""
        if self.use_faiss and self.vector_db:
            self.vector_db.load(document_id)
        else:
            raise ValueError("FAISS vector database not available")
    
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Get embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=texts
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            raise ValueError(f"Error getting embeddings: {str(e)}")
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        vec1 = np.array(vec1)
        vec2 = np.array(vec2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def search(self, document_text: str, query: str, top_k: int = 3, chunk_size: int = 500) -> List[Dict[str, any]]:
        """
        Perform semantic search on document text using FAISS vector database.
        
        Args:
            document_text: Full document text to search (used if FAISS not available)
            query: Search query (what we're looking for)
            top_k: Number of top results to return
            chunk_size: Size of text chunks for search (fallback only)
            
        Returns:
            List of relevant text chunks with similarity scores
        """
        # Use FAISS if available
        if self.use_faiss and self.vector_db and self.vector_db.index and self.vector_db.index.ntotal > 0:
            results = self.vector_db.search(query, top_k=top_k)
            # Format results to match expected structure
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'text': result['text'],
                    'similarity': result['similarity'],
                    'start_index': result.get('start_index', 0),
                    'end_index': result.get('end_index', 0),
                    'page': result.get('page')
                })
            return formatted_results
        
        # Fallback to original method if FAISS not available
        return self._search_fallback(document_text, query, top_k, chunk_size)
    
    def _search_fallback(self, document_text: str, query: str, top_k: int = 3, chunk_size: int = 500) -> List[Dict[str, any]]:
        """Fallback search method when FAISS is not available."""
        # Chunk the document
        chunks = self.chunk_text(document_text, chunk_size=chunk_size)
        
        if not chunks:
            return []
        
        # Get embeddings for query and chunks
        chunk_texts = [chunk['text'] for chunk in chunks]
        all_texts = [query] + chunk_texts
        
        try:
            embeddings = self.get_embeddings(all_texts)
            query_embedding = embeddings[0]
            chunk_embeddings = embeddings[1:]
        except Exception as e:
            print(f"Warning: Could not get embeddings: {str(e)}")
            return []
        
        # Calculate similarities
        results = []
        for i, chunk in enumerate(chunks):
            similarity = self.cosine_similarity(query_embedding, chunk_embeddings[i])
            results.append({
                'text': chunk['text'],
                'similarity': similarity,
                'start_index': chunk['start_index'],
                'end_index': chunk['end_index']
            })
        
        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity'], reverse=True)
        return results[:top_k]
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[Dict[str, any]]:
        """
        Split text into overlapping chunks for semantic search.
        
        Args:
            text: Input text to chunk
            chunk_size: Size of each chunk in characters
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of dictionaries with 'text' and 'start_index' keys
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end]
            
            chunks.append({
                'text': chunk_text,
                'start_index': start,
                'end_index': end
            })
            
            start += chunk_size - overlap
        
        return chunks
    
    def search_multiple(self, document_text: str, queries: List[str], top_k: int = 2) -> Dict[str, List[Dict[str, any]]]:
        """
        Perform semantic search for multiple queries.
        
        Args:
            document_text: Full document text to search
            queries: List of search queries
            top_k: Number of top results per query
            
        Returns:
            Dictionary mapping queries to their search results
        """
        results = {}
        for query in queries:
            results[query] = self.search(document_text, query, top_k=top_k)
        return results
    
    def find_related_info(self, document_text: str, field_name: str, field_description: str, top_k: int = 3) -> List[str]:
        """
        Find information related to a specific field using semantic search.
        
        Args:
            document_text: Full document text (used as fallback if FAISS not available)
            field_name: Name of the field (e.g., "payment_amount")
            field_description: Description of what we're looking for (e.g., "payment amount, price, cost, fee")
            top_k: Number of results to return
            
        Returns:
            List of relevant text snippets
        """
        # Create a comprehensive search query
        query = f"{field_name} {field_description}"
        
        search_results = self.search(document_text, query, top_k=top_k)
        
        # Extract text snippets (filter by similarity threshold)
        snippets = [result['text'] for result in search_results if result.get('similarity', 0) > 0.3]
        
        return snippets

