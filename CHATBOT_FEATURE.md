# 🤖 Document Q&A Chatbot Feature

## Overview
The Document Q&A Chatbot allows users to upload any document (PDF, DOCX, TXT) and ask questions about its content using natural language. The system uses advanced AI (RAG - Retrieval Augmented Generation) to provide accurate answers based on the document content.

## Features

### ✨ Key Capabilities
- **Multi-format Support**: Upload PDF, DOCX, or TXT files
- **Scanned PDF Detection**: Automatically detects image-based PDFs
- **OCR Integration**: Uses Google Cloud Vision API for scanned PDFs (automatic)
- **Intelligent Q&A**: Ask any question about the document content
- **Context-Aware**: Provides relevant excerpts from the document with each answer
- **Real-time Chat**: Interactive chat interface with typing indicators
- **Session Management**: Each uploaded document creates a separate chat session
- **Beautiful UI**: Modern, responsive popup interface with animations

### 🎯 Use Cases
- **Quick Document Review**: Get instant answers without reading the entire document
- **Contract Analysis**: Ask about specific clauses, dates, amounts, or parties
- **Invoice Verification**: Query payment terms, amounts, or vendor details
- **Legal Review**: Understand complex legal language and terms
- **Due Diligence**: Extract specific information for compliance checks

## How to Use

### 1. Access the Chatbot
- Click the **purple chat button** (💬) in the bottom-right corner of the screen
- The chatbot popup will appear

### 2. Upload a Document
- Click **"Choose File"** button
- Select a PDF, DOCX, or TXT document from your computer
- Wait for the document to be processed:
  - **Normal PDFs**: 5-10 seconds
  - **Scanned PDFs**: 15-30 seconds (OCR processing with Google Vision API)
- If it's a scanned PDF, you'll see a **📷 (OCR Processed)** indicator

### 3. Ask Questions
- Once the document is loaded, you'll see a welcome message
- Type your question in the input field at the bottom
- Press **Enter** or click the **send button** (✈️)
- The AI will analyze the document and provide an answer

### 4. View Answers
- Each answer includes:
  - **Main Answer**: Direct response to your question
  - **Relevant Excerpts**: Actual text from the document supporting the answer
  - **Timestamp**: When the message was sent

### 5. Change Document
- Click **"Change Document"** button to upload a different file
- Your current chat session will be cleared

## Example Questions

### For Contracts
- "What is the contract duration?"
- "Who are the parties involved in this agreement?"
- "What are the payment terms?"
- "Are there any termination clauses?"
- "What is the renewal policy?"

### For Invoices
- "What is the total amount due?"
- "When is the payment due date?"
- "What items are included in this invoice?"
- "What is the vendor's contact information?"
- "Are there any discounts applied?"

### For Leases
- "What is the monthly rent amount?"
- "When does the lease start and end?"
- "What are the tenant's responsibilities?"
- "Is there a security deposit required?"
- "What are the renewal terms?"

### For NDAs
- "What information is considered confidential?"
- "How long does the confidentiality obligation last?"
- "What are the exceptions to confidentiality?"
- "What happens if confidentiality is breached?"
- "Can the information be shared with third parties?"

## OCR Support for Scanned PDFs

### Automatic Detection
The chatbot automatically detects whether a PDF is:
- **Normal PDF**: Contains extractable text (fast processing)
- **Scanned PDF**: Image-based document (requires OCR)

### How It Works
1. **Upload**: User uploads a PDF document
2. **Detection**: System checks if PDF contains extractable text
3. **OCR Processing**: If scanned, automatically uses Google Cloud Vision API
4. **Text Extraction**: High-accuracy OCR extracts text from images
5. **Ready for Q&A**: Document is processed and ready for questions

### Visual Indicators
- Normal PDF: Shows filename only
- Scanned PDF: Shows **📷 (OCR Processed)** next to filename
- Welcome message includes: "Processed with OCR for scanned PDF"

### Requirements for OCR
1. Google Cloud Vision API enabled (already configured in your project)
2. Service account credentials in project root: `gcp-creds.json`
3. Document parser initialized with `use_gcs_vision=True` (default)

### Supported Formats
- ✅ **Scanned PDFs**: Images embedded in PDF
- ✅ **Photo PDFs**: Photos converted to PDF
- ✅ **Document Scans**: Scanned contracts, invoices, etc.
- ✅ **Mixed PDFs**: Combination of text and images

## Technical Architecture

### Backend Components

#### 1. **document_chat.py**
- `DocumentChatbot` class: Core chatbot logic
- Document parsing and text extraction
- Vector store creation using FAISS for semantic search
- Question answering using OpenAI GPT-4o-mini
- Session management for multiple users

#### 2. **API Endpoints** (in app.py)
- `POST /api/chat/upload`: Upload document and create session
- `POST /api/chat/ask`: Ask a question about the document
- `GET /api/chat/session/{session_id}`: Get session information
- `DELETE /api/chat/session/{session_id}`: Delete a chat session

### Frontend Components

#### 1. **chatbot.css**
- Modern, responsive styling
- Smooth animations and transitions
- Mobile-friendly design
- Custom scrollbars and loading indicators

#### 2. **chatbot.js**
- `DocumentChatbot` class: Frontend logic
- File upload handling
- Message rendering (user/bot)
- Real-time typing indicators
- Error handling and validation

#### 3. **index.html**
- Chatbot button (floating)
- Popup container with sections:
  - Upload section
  - Loading section
  - Chat section (with messages and input)

### AI/ML Stack
- **LangChain**: Framework for LLM applications
- **OpenAI GPT-4o-mini**: Language model for answering questions
- **FAISS**: Vector database for semantic search
- **OpenAI Embeddings**: Text embeddings for similarity search
- **RecursiveCharacterTextSplitter**: Document chunking for better retrieval

### How RAG Works
1. **Document Upload**: User uploads a document
2. **Text Extraction**: Document is parsed and text is extracted
3. **Chunking**: Text is split into smaller chunks (1000 chars with 200 overlap)
4. **Embeddings**: Each chunk is converted to a vector embedding
5. **Vector Store**: Embeddings are stored in FAISS for fast retrieval
6. **Question**: User asks a question
7. **Retrieval**: Top 3 most relevant chunks are retrieved using semantic search
8. **Generation**: LLM generates an answer using only the retrieved context
9. **Response**: Answer is sent back with relevant excerpts

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `langchain>=0.3.0`
- `langchain-openai>=0.2.0`
- `langchain-community>=0.3.0`
- `langchain-text-splitters>=0.3.0`
- `faiss-cpu>=1.7.4`
- `openai>=1.12.0`

### 2. Configure OpenAI API Key
Create a `.env` file in the project root:
```
OPENAI_API_KEY=your-api-key-here
```

### 3. Start the Server
```bash
python app.py
```

### 4. Access the Application
Open your browser and go to:
```
http://localhost:8000
```

## API Usage

### Upload a Document
```bash
curl -X POST "http://localhost:8000/api/chat/upload" \
  -F "file=@/path/to/document.pdf"
```

Response:
```json
{
  "success": true,
  "session_id": "uuid-here",
  "filename": "document.pdf",
  "chunks": 15,
  "document_length": 12500,
  "message": "Document loaded successfully!"
}
```

### Ask a Question
```bash
curl -X POST "http://localhost:8000/api/chat/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "uuid-here",
    "question": "What is the contract duration?"
  }'
```

Response:
```json
{
  "success": true,
  "answer": "The contract duration is 12 months...",
  "excerpts": [
    "This agreement shall commence on...",
    "The term of this contract is..."
  ],
  "filename": "document.pdf"
}
```

## Performance & Optimization

### Speed
- Document processing: 5-10 seconds (depending on size)
- Question answering: 2-4 seconds per question
- Optimized chunking and retrieval for fast responses

### Cost
- Uses GPT-4o-mini (most cost-effective OpenAI model)
- Embeddings: ~$0.0001 per 1K tokens
- LLM calls: ~$0.001 per 1K tokens
- Average cost per document: $0.05-0.10
- Average cost per question: $0.01-0.02

### Scalability
- Session-based architecture supports multiple users
- In-memory storage for fast access
- Can be extended to use Redis or database for persistence

## Troubleshooting

### Issue: "Session not found"
- **Cause**: Session expired or was deleted
- **Solution**: Upload the document again

### Issue: "Could not extract text from document"
- **Cause**: Document is image-based PDF or corrupted
- **Solution**: Ensure document has extractable text, or use OCR-enabled PDFs

### Issue: "Network error"
- **Cause**: Server not running or connection issues
- **Solution**: Check if server is running on port 8000

### Issue: Answers are not accurate
- **Cause**: Question is ambiguous or information not in document
- **Solution**: Ask more specific questions or verify the document contains the information

## Future Enhancements

### Planned Features
- [ ] Multi-document chat (compare across multiple documents)
- [ ] Chat history persistence
- [ ] Export chat conversations
- [ ] Support for images and tables in PDFs
- [ ] Advanced filters (date ranges, amounts, parties)
- [ ] Voice input for questions
- [ ] Suggested questions based on document type
- [ ] Integration with document extraction results
- [ ] Collaboration features (shared sessions)
- [ ] Custom knowledge base training

## Security & Privacy

### Data Handling
- Documents are processed temporarily and not stored permanently
- Sessions are in-memory and cleared on server restart
- No document content is sent to third parties (except OpenAI for processing)

### Best Practices
- Use secure connections (HTTPS in production)
- Implement authentication for sensitive documents
- Add rate limiting to prevent abuse
- Encrypt documents at rest and in transit

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the console logs for error details
3. Ensure all dependencies are installed correctly
4. Verify OpenAI API key is configured

---

**Built with ❤️ using LangChain, OpenAI, and FastAPI**

