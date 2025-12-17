"""
Document Chat Module - Q&A functionality for uploaded documents.
Uses LangChain with OpenAI for intelligent question answering.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from document_parser import DocumentParser
from cache_manager import get_cache_manager


class DocumentChatbot:
    """
    Chatbot for answering questions about uploaded documents.
    Uses RAG (Retrieval Augmented Generation) approach.
    """
    
    def __init__(self, api_key: Optional[str] = None, use_gcs_vision: bool = True):
        """
        Initialize the chatbot with OpenAI API key.
        
        Args:
            api_key: OpenAI API key (optional, will use env var if not provided)
            use_gcs_vision: Enable Google Cloud Vision API for scanned PDFs
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.2,
            api_key=self.api_key
        )
        
        self.embeddings = OpenAIEmbeddings(api_key=self.api_key)
        
        # Initialize parser with Vision API support for scanned PDFs
        self.parser = DocumentParser(use_gcs_vision=use_gcs_vision)
        self.use_gcs_vision = use_gcs_vision
        
        # Store active sessions: {session_id: {"vectorstore": FAISS, "chat_history": [], "filename": str}}
        self.sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, session_id: str, file_path: str, file_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new chat session for a document.
        
        Args:
            session_id: Unique session identifier
            file_path: Path to the document file
            file_hash: Optional file hash (if not provided, will compute from file)
            
        Returns:
            Session creation status and info
        """
        try:
            # Check if it's a PDF and if it's scanned
            file_ext = os.path.splitext(file_path)[1].lower()
            is_scanned = False
            
            if file_ext == '.pdf':
                # Check if PDF is scanned (image-based)
                is_scanned = self.parser._is_scanned_pdf(file_path)
                
                if is_scanned:
                    print(f"[CHATBOT] Detected SCANNED PDF: {os.path.basename(file_path)}")
                    if self.use_gcs_vision:
                        print(f"[CHATBOT] Using Google Cloud Vision API for OCR...")
                    else:
                        print(f"[CHATBOT] Warning: Scanned PDF detected but Vision API is disabled")
                else:
                    print(f"[CHATBOT] Detected NORMAL PDF with extractable text")
            
            # Parse the document (will automatically use Vision API if scanned)
            print(f"[CHATBOT] Parsing document: {file_path}")
            document_text, page_map = self.parser.parse_with_pages(file_path)
            
            if not document_text or len(document_text.strip()) == 0:
                error_msg = "Could not extract text from document."
                if is_scanned and not self.use_gcs_vision:
                    error_msg += " This appears to be a scanned PDF. Please enable Google Cloud Vision API for OCR."
                else:
                    error_msg += " The file might be empty or corrupted."
                
                return {
                    "success": False,
                    "error": error_msg
                }
            
            # Split text into chunks for better retrieval
            # Increased chunk size for better context retention, especially for structured data like invoices
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,  # Increased from 1000 to capture more context per chunk
                chunk_overlap=300,  # Increased overlap to prevent splitting related information
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            chunks = text_splitter.split_text(document_text)
            print(f"[CHATBOT] Created {len(chunks)} text chunks")
            
            # Extract tables from document
            print(f"[CHATBOT] Extracting tables from document...")
            tables = self.parser.extract_tables(file_path)
            print(f"[CHATBOT] Extracted {len(tables)} tables")
            
            # Create vector store for semantic search
            vectorstore = FAISS.from_texts(chunks, self.embeddings)
            
            # Store session with original chunks, tables, and full content
            self.sessions[session_id] = {
                "vectorstore": vectorstore,
                "chat_history": [],  # Store conversation history
                "filename": os.path.basename(file_path),
                "chunks": len(chunks),
                "chunk_texts": chunks,  # Store original chunks for term matching
                "document_text": document_text,  # Store full document text
                "page_map": page_map,  # Store page map
                "tables": tables,  # Store extracted tables
                "document_length": len(document_text),
                "is_scanned": is_scanned,
                "used_ocr": is_scanned and self.use_gcs_vision,
                "file_path": file_path  # Store file path for JSON saving
            }
            
            # Save all content to JSON file for validation
            self._save_content_to_json(session_id, file_path, document_text, page_map, chunks, tables, is_scanned, is_scanned and self.use_gcs_vision)
            
            # Save to cache for future use
            # Compute hash if not provided
            if not file_hash:
                cache_manager = get_cache_manager()
                file_hash = cache_manager.compute_file_hash(file_path)
            
            if file_hash:
                cache_manager = get_cache_manager()
                cache_manager.save_chatbot_cache(
                    file_hash=file_hash,
                    document_text=document_text,
                    page_map=page_map,
                    chunks=chunks,
                    tables=tables,
                    is_scanned=is_scanned,
                    used_ocr=is_scanned and self.use_gcs_vision,
                    filename=os.path.basename(file_path)
                )
                print(f"[CHATBOT] Saved to cache for future use (hash: {file_hash[:16]}...)")
            
            print(f"[CHATBOT] Session created: {session_id}")
            
            # Create success message
            message = f"Document loaded successfully! Ask me anything about '{os.path.basename(file_path)}'."
            if is_scanned and self.use_gcs_vision:
                message += " (Processed with OCR for scanned PDF)"
            
            return {
                "success": True,
                "session_id": session_id,
                "filename": os.path.basename(file_path),
                "chunks": len(chunks),
                "document_length": len(document_text),
                "is_scanned": is_scanned,
                "used_ocr": is_scanned and self.use_gcs_vision,
                "message": message
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error creating session: {str(e)}")
            return {
                "success": False,
                "error": f"Error processing document: {str(e)}"
            }
    
    def create_session_from_text(self, session_id: str, document_text: str, filename: str = "document.pdf", extracted_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new chat session from already-parsed document text.
        This reuses the text from extraction, avoiding re-parsing and saving time.
        
        Args:
            session_id: Unique session identifier
            document_text: Already parsed document text
            filename: Original filename for display
            extracted_data: Optional extracted structured data to enhance context
            
        Returns:
            Session creation status and info
        """
        try:
            print(f"[CHATBOT] Creating session from extracted text: {filename}")
            print(f"[CHATBOT] Text length: {len(document_text)} characters")
            
            if not document_text or len(document_text.strip()) == 0:
                return {
                    "success": False,
                    "error": "Document text is empty"
                }
            
            # Split text into chunks for better retrieval
            # Increased chunk size for better context retention, especially for structured data like invoices
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,  # Increased from 1000 to capture more context per chunk
                chunk_overlap=300,  # Increased overlap to prevent splitting related information
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            chunks = text_splitter.split_text(document_text)
            print(f"[CHATBOT] Created {len(chunks)} text chunks from extracted text")
            
            # Create vector store for semantic search (REUSING extracted text - no re-parsing!)
            vectorstore = FAISS.from_texts(chunks, self.embeddings)
            print(f"[CHATBOT] Vector store created from extraction results")
            
            # Extract tables from extracted_data if available (for invoices/structured docs)
            tables = []
            if extracted_data:
                # Try to extract table-like structures from extracted_data
                if "line_items" in extracted_data:
                    # Convert line items to table format
                    line_items = extracted_data.get("line_items", [])
                    if line_items:
                        headers = list(line_items[0].keys()) if line_items and isinstance(line_items[0], dict) else []
                        rows = [[str(item.get(k, "")) for k in headers] for item in line_items] if headers else []
                        if headers and rows:
                            tables.append({
                                "page": 1,
                                "headers": headers,
                                "rows": rows,
                                "row_count": len(rows),
                                "column_count": len(headers),
                                "extraction_method": "from_extracted_data",
                                "table_type": "line_items"
                            })
            
            # Store session with extracted_data for enhanced context
            # Store original chunks for term-based matching
            self.sessions[session_id] = {
                "vectorstore": vectorstore,
                "chat_history": [],  # Store conversation history
                "filename": filename,
                "chunks": len(chunks),
                "chunk_texts": chunks,  # Store original chunks for term matching
                "document_text": document_text,  # Store full document text
                "page_map": {},  # No page map for text-only
                "tables": tables,  # Store extracted tables
                "document_length": len(document_text),
                "is_scanned": False,  # Unknown from text only
                "used_ocr": False,     # Unknown from text only
                "from_extraction": True,  # Flag to indicate this came from extraction
                "extracted_data": extracted_data  # Store structured data for reference
            }
            
            # Save to JSON (with empty page_map since we don't have pages)
            self._save_content_to_json(session_id, filename, document_text, {}, chunks, tables, False, False)
            
            # Note: For create_session_from_text, we don't have file_hash, so we can't cache it
            # This is fine since it's already coming from extraction which is cached
            
            print(f"[CHATBOT] Session created from extraction: {session_id}")
            
            message = f"Document loaded successfully! Ask me anything about '{filename}'. (Loaded from extraction - no re-parsing needed!)"
            
            return {
                "success": True,
                "session_id": session_id,
                "filename": filename,
                "chunks": len(chunks),
                "document_length": len(document_text),
                "is_scanned": False,
                "used_ocr": False,
                "from_extraction": True,
                "message": message
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error creating session from text: {str(e)}")
            return {
                "success": False,
                "error": f"Error processing document text: {str(e)}"
            }
    
    def ask_question(self, session_id: str, question: str) -> Dict[str, Any]:
        """
        Ask a question about the document with conversation history.
        
        Args:
            session_id: Session identifier
            question: User's question
            
        Returns:
            Answer and relevant context
        """
        try:
            # Check if session exists
            if session_id not in self.sessions:
                return {
                    "success": False,
                    "error": "Session not found. Please upload a document first."
                }
            
            session = self.sessions[session_id]
            vectorstore = session["vectorstore"]
            chat_history = session.get("chat_history", [])
            extracted_data = session.get("extracted_data")
            
            # Use hybrid retrieval: semantic search + term matching for comprehensive coverage
            # Retrieve more chunks (increased to 10) to ensure we capture all relevant information
            relevant_docs = vectorstore.similarity_search(question, k=10)
            
            # Also try to find chunks containing key terms from the question for better exact matches
            question_lower = question.lower()
            question_terms = [term.strip('.,!?;:()[]{}') for term in question_lower.split() if len(term.strip('.,!?;:()[]{}')) > 2]
            
            # Get additional chunks and score them by term matching
            try:
                # Try to get more chunks using a broader search
                all_chunks = vectorstore.similarity_search(question, k=min(30, len(session.get("chunks", 0)) or 30))
                term_matched_docs = []
                for doc in all_chunks:
                    content_lower = doc.page_content.lower()
                    matches = sum(1 for term in question_terms if term in content_lower)
                    if matches > 0:
                        term_matched_docs.append((doc, matches))
                
                # Sort by match count and add top matches that aren't already in relevant_docs
                term_matched_docs.sort(key=lambda x: x[1], reverse=True)
                existing_contents = {doc.page_content[:100] for doc in relevant_docs}
                
                for doc, score in term_matched_docs[:5]:  # Add top 5 term-matched chunks
                    if doc.page_content[:100] not in existing_contents:
                        relevant_docs.append(doc)
                        existing_contents.add(doc.page_content[:100])
            except:
                pass  # If term matching fails, just use semantic search results
            
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
            
            # Add extracted structured data to context if available
            extracted_data_context = ""
            if extracted_data:
                import json
                try:
                    # Format extracted data as JSON for context
                    extracted_data_str = json.dumps(extracted_data, indent=2, default=str)
                    extracted_data_context = f"\n\nEXTRACTED STRUCTURED DATA (for reference - use this along with document text):\n{extracted_data_str}"
                except:
                    pass
            
            # Add tables to context if available
            tables = session.get("tables", [])
            tables_context = ""
            if tables:
                try:
                    tables_text = "\n\n".join([
                        f"TABLE {i+1} (Page {table.get('page', '?')}):\n"
                        f"Headers: {', '.join(table.get('headers', []))}\n"
                        f"Rows ({table.get('row_count', 0)} rows):\n" +
                        "\n".join([f"  Row {j+1}: {', '.join([str(cell) for cell in row])}" 
                                  for j, row in enumerate(table.get('rows', [])[:20])])  # Limit to first 20 rows
                        for i, table in enumerate(tables)
                    ])
                    tables_context = f"\n\nEXTRACTED TABLES:\n{tables_text}"
                except Exception as e:
                    print(f"[CHATBOT] Error formatting tables: {e}")
            
            # Build conversation history context
            history_context = ""
            if chat_history:
                history_context = "\n\nPREVIOUS CONVERSATION:\n"
                for i, (q, a) in enumerate(chat_history[-3:], 1):  # Last 3 exchanges
                    history_context += f"Q{i}: {q}\nA{i}: {a}\n"
            
            # Create prompt with history - improved to extract all relevant information
            system_prompt = """You are a helpful assistant that answers questions about documents.
Your goal is to extract and provide ALL relevant information from the document that answers the question.

IMPORTANT INSTRUCTIONS:
- Carefully read through ALL the provided context chunks - information may be in any of them
- Pay special attention to EXTRACTED TABLES - they contain structured data like line items, quantities, prices, dates, etc.
- For questions about specific items, tasks, dates, or fields, search through ALL chunks AND tables for exact matches
- For questions about "end date", "start date", "due date", look for date fields in tables and text associated with the mentioned item/task
- For questions about tasks, items, or line items, extract ALL details from tables including descriptions, quantities, hours, rates, amounts, dates
- If the question asks for a list (like "all items", "all line items", "all taxes"), provide the complete list from tables
- Include specific details like quantities, unit prices, totals, tax rates, tax amounts, dates, etc. from tables
- Be thorough and comprehensive - don't just provide a summary, provide the actual data from tables
- If information is spread across multiple chunks or tables, combine it to give a complete answer
- Use the extracted structured data and tables as a reference, but also search the full document text for complete details
- Consider the conversation history for context
- If you find partial information, provide what you found and indicate if there might be more
- Only say "I cannot find that information in the document" if you've thoroughly searched ALL chunks, tables, and found nothing

Be accurate, detailed, and comprehensive. Double-check your answer before responding."""
            
            user_prompt = f"""CONTEXT FROM DOCUMENT:
{context}{extracted_data_context}{tables_context}{history_context}

CURRENT QUESTION: {question}

ANSWER:"""
            
            # Get answer
            print(f"[CHATBOT] Processing question: {question[:50]}...")
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            answer = response.content
            
            # Store in conversation history
            chat_history.append((question, answer))
            session["chat_history"] = chat_history
            
            # Extract excerpts
            excerpts = []
            for doc in relevant_docs[:2]:
                content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                excerpts.append(content)
            
            return {
                "success": True,
                "answer": answer,
                "excerpts": excerpts,
                "filename": session["filename"]
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error answering question: {str(e)}")
            return {
                "success": False,
                "error": f"Error processing question: {str(e)}"
            }
    
    def simple_ask(self, session_id: str, question: str) -> Dict[str, Any]:
        """
        Simple question answering without conversational memory (faster).
        
        Args:
            session_id: Session identifier
            question: User's question
            
        Returns:
            Answer with context
        """
        try:
            if session_id not in self.sessions:
                return {
                    "success": False,
                    "error": "Session not found. Please upload a document first."
                }
            
            session = self.sessions[session_id]
            vectorstore = session["vectorstore"]
            extracted_data = session.get("extracted_data")
            
            # Use hybrid retrieval: semantic search + term matching for comprehensive coverage
            # Retrieve more chunks (increased to 10) to ensure we capture all relevant information
            relevant_docs = vectorstore.similarity_search(question, k=10)
            
            # Also try to find chunks containing key terms from the question for better exact matches
            question_lower = question.lower()
            # Extract meaningful terms (remove common words and keep important ones)
            stop_words = {'the', 'is', 'are', 'what', 'which', 'when', 'where', 'who', 'how', 'does', 'do', 'did', 'has', 'have', 'had', 'was', 'were', 'will', 'would', 'can', 'could', 'should', 'may', 'might', 'must', 'about', 'with', 'from', 'for', 'and', 'or', 'but', 'not', 'this', 'that', 'these', 'those', 'a', 'an', 'of', 'to', 'in', 'on', 'at', 'by', 'as'}
            question_terms = [term.strip('.,!?;:()[]{}') for term in question_lower.split() 
                            if len(term.strip('.,!?;:()[]{}')) > 2 and term.strip('.,!?;:()[]{}') not in stop_words]
            
            # Get additional chunks using term matching on stored chunk texts
            try:
                chunk_texts = session.get("chunk_texts", [])
                if chunk_texts and question_terms:
                    from langchain_core.documents import Document
                    term_matched_chunks = []
                    for i, chunk_text in enumerate(chunk_texts):
                        content_lower = chunk_text.lower()
                        # Count matches and also check for phrase matches
                        matches = sum(1 for term in question_terms if term in content_lower)
                        # Also check for multi-word phrases from the question
                        phrase_matches = sum(1 for phrase in [question_lower] if phrase in content_lower)
                        total_score = matches + (phrase_matches * 2)  # Weight phrase matches higher
                        
                        if total_score > 0:
                            term_matched_chunks.append((Document(page_content=chunk_text), total_score))
                    
                    # Sort by match score and add top matches that aren't already in relevant_docs
                    term_matched_chunks.sort(key=lambda x: x[1], reverse=True)
                    existing_contents = {doc.page_content[:100] for doc in relevant_docs}
                    
                    for doc, score in term_matched_chunks[:5]:  # Add top 5 term-matched chunks
                        if doc.page_content[:100] not in existing_contents:
                            relevant_docs.append(doc)
                            existing_contents.add(doc.page_content[:100])
            except Exception as e:
                print(f"[CHATBOT] Term matching error: {e}")
                pass  # If term matching fails, just use semantic search results
            
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
            
            # Add extracted structured data to context if available
            extracted_data_context = ""
            if extracted_data:
                import json
                try:
                    # Format extracted data as JSON for context
                    extracted_data_str = json.dumps(extracted_data, indent=2, default=str)
                    extracted_data_context = f"\n\nEXTRACTED STRUCTURED DATA (for reference - use this along with document text):\n{extracted_data_str}"
                except:
                    pass
            
            # Add tables to context if available
            tables = session.get("tables", [])
            tables_context = ""
            if tables:
                try:
                    tables_text = "\n\n".join([
                        f"TABLE {i+1} (Page {table.get('page', '?')}):\n"
                        f"Headers: {', '.join(table.get('headers', []))}\n"
                        f"Rows ({table.get('row_count', 0)} rows):\n" +
                        "\n".join([f"  Row {j+1}: {', '.join([str(cell) for cell in row])}" 
                                  for j, row in enumerate(table.get('rows', [])[:20])])  # Limit to first 20 rows
                        for i, table in enumerate(tables)
                    ])
                    tables_context = f"\n\nEXTRACTED TABLES:\n{tables_text}"
                except Exception as e:
                    print(f"[CHATBOT] Error formatting tables: {e}")
            
            # Create prompt - improved to extract all relevant information
            system_prompt = """You are a helpful assistant that answers questions about documents.
Your goal is to extract and provide ALL relevant information from the document that answers the question.

IMPORTANT INSTRUCTIONS:
- Carefully read through ALL the provided context chunks - information may be in any of them
- Pay special attention to EXTRACTED TABLES - they contain structured data like line items, quantities, prices, dates, etc.
- For questions about specific items, tasks, dates, or fields, search through ALL chunks AND tables for exact matches
- For questions about "end date", "start date", "due date", look for date fields in tables and text associated with the mentioned item/task
- For questions about tasks, items, or line items, extract ALL details from tables including descriptions, quantities, hours, rates, amounts, dates
- If the question asks for a list (like "all items", "all line items", "all taxes"), provide the complete list from tables
- Include specific details like quantities, unit prices, totals, tax rates, tax amounts, dates, etc. from tables
- Be thorough and comprehensive - don't just provide a summary, provide the actual data from tables
- If information is spread across multiple chunks or tables, combine it to give a complete answer
- Use the extracted structured data and tables as a reference, but also search the full document text for complete details
- If you find partial information, provide what you found and indicate if there might be more
- Only say "I cannot find that information in the document" if you've thoroughly searched ALL chunks, tables, and found nothing

Be accurate, detailed, and comprehensive. Double-check your answer before responding."""
            
            user_prompt = f"""CONTEXT FROM DOCUMENT:
{context}{extracted_data_context}{tables_context}

QUESTION: {question}

ANSWER:"""
            
            # Get answer
            response = self.llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])
            
            answer = response.content
            
            # Extract excerpts
            excerpts = []
            for doc in relevant_docs[:2]:
                content = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
                excerpts.append(content)
            
            return {
                "success": True,
                "answer": answer,
                "excerpts": excerpts,
                "filename": session["filename"]
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error in simple_ask: {str(e)}")
            return {
                "success": False,
                "error": f"Error processing question: {str(e)}"
            }
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        return {
            "session_id": session_id,
            "filename": session["filename"],
            "chunks": session["chunks"],
            "document_length": session["document_length"]
        }
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a chat session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"[CHATBOT] Session deleted: {session_id}")
            return True
        return False

    def clear_all_sessions(self):
        """Clear all chat sessions."""
        self.sessions.clear()
        print("[CHATBOT] All sessions cleared")
    
    def create_session_from_cache(self, session_id: str, document_text: str, page_map: Dict[int, str],
                                  chunks: List[str], tables: List[Dict[str, Any]], filename: str,
                                  is_scanned: bool, used_ocr: bool) -> Dict[str, Any]:
        """
        Create a chat session from cached data (no re-parsing needed!).
        
        Args:
            session_id: Unique session identifier
            document_text: Cached document text
            page_map: Cached page map
            chunks: Cached text chunks
            tables: Cached extracted tables
            filename: Original filename
            is_scanned: Whether document was scanned
            used_ocr: Whether OCR was used
            
        Returns:
            Session creation status and info
        """
        try:
            print(f"[CHATBOT] Creating session from cache: {filename}")
            print(f"[CHATBOT] Text length: {len(document_text)} characters")
            print(f"[CHATBOT] Chunks: {len(chunks)}, Tables: {len(tables)}")
            
            # Recreate vector store from cached chunks (fast - no re-embedding needed if we had stored embeddings)
            # For now, we'll recreate embeddings (still faster than parsing)
            print(f"[CHATBOT] Recreating vector store from cached chunks...")
            vectorstore = FAISS.from_texts(chunks, self.embeddings)
            print(f"[CHATBOT] Vector store recreated")
            
            # Store session
            self.sessions[session_id] = {
                "vectorstore": vectorstore,
                "chat_history": [],
                "filename": filename,
                "chunks": len(chunks),
                "chunk_texts": chunks,
                "document_text": document_text,
                "page_map": page_map,
                "tables": tables,
                "document_length": len(document_text),
                "is_scanned": is_scanned,
                "used_ocr": used_ocr,
                "from_cache": True  # Flag to indicate loaded from cache
            }
            
            print(f"[CHATBOT] Session created from cache: {session_id}")
            
            message = f"Document loaded successfully from cache! Ask me anything about '{filename}'. (No re-processing needed!)"
            if is_scanned and used_ocr:
                message += " (Previously processed with OCR)"
            
            return {
                "success": True,
                "session_id": session_id,
                "filename": filename,
                "chunks": len(chunks),
                "document_length": len(document_text),
                "is_scanned": is_scanned,
                "used_ocr": used_ocr,
                "from_cache": True,
                "message": message
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error creating session from cache: {str(e)}")
            return {
                "success": False,
                "error": f"Error loading from cache: {str(e)}"
            }
    
    def create_session_from_extraction_cache(self, session_id: str, document_text: str, 
                                             page_map: Dict[int, str], filename: str,
                                             file_path: Optional[str] = None,
                                             file_hash: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a chat session from extraction cache (reuses parsed text, but creates chunks/vectorstore).
        This is faster than full parsing but still needs to chunk and embed.
        
        Args:
            session_id: Unique session identifier
            document_text: Document text from extraction cache
            page_map: Page map from extraction cache
            filename: Original filename
            file_path: Optional file path (if available, can extract tables)
            
        Returns:
            Session creation status and info
        """
        try:
            print(f"[CHATBOT] Creating session from extraction cache: {filename}")
            print(f"[CHATBOT] Text length: {len(document_text)} characters")
            
            # Split text into chunks (we still need to do this)
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=300,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""]
            )
            
            chunks = text_splitter.split_text(document_text)
            print(f"[CHATBOT] Created {len(chunks)} text chunks from cached text")
            
            # Try to extract tables if file_path is available
            tables = []
            if file_path and os.path.exists(file_path):
                try:
                    print(f"[CHATBOT] Extracting tables from file...")
                    tables = self.parser.extract_tables(file_path)
                    print(f"[CHATBOT] Extracted {len(tables)} tables")
                except Exception as e:
                    print(f"[CHATBOT] Could not extract tables: {e}")
            
            # Create vector store (we need to embed chunks)
            print(f"[CHATBOT] Creating vector store from chunks...")
            vectorstore = FAISS.from_texts(chunks, self.embeddings)
            print(f"[CHATBOT] Vector store created")
            
            # Store session
            self.sessions[session_id] = {
                "vectorstore": vectorstore,
                "chat_history": [],
                "filename": filename,
                "chunks": len(chunks),
                "chunk_texts": chunks,
                "document_text": document_text,
                "page_map": page_map,
                "tables": tables,
                "document_length": len(document_text),
                "is_scanned": False,  # Unknown from extraction cache
                "used_ocr": False,     # Unknown from extraction cache
                "from_extraction_cache": True  # Flag to indicate loaded from extraction cache
            }
            
            print(f"[CHATBOT] Session created from extraction cache: {session_id}")
            
            # Save to chatbot cache for future instant loads
            if file_hash:
                cache_manager = get_cache_manager()
                cache_manager.save_chatbot_cache(
                    file_hash=file_hash,
                    document_text=document_text,
                    page_map=page_map,
                    chunks=chunks,
                    tables=tables,
                    is_scanned=False,  # Unknown from extraction cache
                    used_ocr=False,     # Unknown from extraction cache
                    filename=filename
                )
                print(f"[CHATBOT] Saved to chatbot cache for future instant loads (hash: {file_hash[:16]}...)")
            
            message = f"Document loaded from extraction cache! Ask me anything about '{filename}'. (Reused parsed text - faster processing!)"
            
            return {
                "success": True,
                "session_id": session_id,
                "filename": filename,
                "chunks": len(chunks),
                "document_length": len(document_text),
                "is_scanned": False,
                "used_ocr": False,
                "from_extraction_cache": True,
                "message": message
            }
            
        except Exception as e:
            print(f"[CHATBOT] Error creating session from extraction cache: {str(e)}")
            return {
                "success": False,
                "error": f"Error loading from extraction cache: {str(e)}"
            }
    
    def _save_content_to_json(self, session_id: str, file_path: str, document_text: str, 
                              page_map: Dict[int, str], chunks: List[str], tables: List[Dict[str, Any]],
                              is_scanned: bool, used_ocr: bool):
        """
        Save all document content to JSON file for validation.
        
        Args:
            session_id: Session identifier
            file_path: Path to original file
            document_text: Full document text
            page_map: Page number to text mapping
            chunks: List of text chunks
            tables: List of extracted tables
            is_scanned: Whether document is scanned
            used_ocr: Whether OCR was used
        """
        try:
            # Get validation folder from app.py (or use relative path)
            validation_folder = Path(__file__).parent / "chatbot_validation"
            validation_folder.mkdir(exist_ok=True)
            
            # Create comprehensive JSON structure
            content_data = {
                "session_id": session_id,
                "file_name": os.path.basename(file_path),
                "file_path": str(file_path),
                "created_at": datetime.now().isoformat(),
                "metadata": {
                    "is_scanned": is_scanned,
                    "used_ocr": used_ocr,
                    "document_length": len(document_text),
                    "total_pages": len(page_map),
                    "total_chunks": len(chunks),
                    "total_tables": len(tables)
                },
                "document_text": document_text,
                "page_map": {str(k): v for k, v in page_map.items()},  # Convert keys to strings for JSON
                "chunks": chunks,
                "tables": tables
            }
            
            # Save to JSON file
            json_filename = f"{session_id}_content.json"
            json_path = validation_folder / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(content_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"[CHATBOT] Saved document content to JSON: {json_path}")
            
        except Exception as e:
            print(f"[CHATBOT] Warning: Could not save content to JSON: {e}")


# Singleton instance for the application
_chatbot_instance: Optional[DocumentChatbot] = None


def get_chatbot(use_gcs_vision: bool = True) -> DocumentChatbot:
    """
    Get or create the chatbot singleton instance.
    
    Args:
        use_gcs_vision: Enable Google Cloud Vision API for scanned PDFs (default: True)
        
    Returns:
        DocumentChatbot instance
    """
    global _chatbot_instance
    if _chatbot_instance is None:
        _chatbot_instance = DocumentChatbot(use_gcs_vision=use_gcs_vision)
    return _chatbot_instance

