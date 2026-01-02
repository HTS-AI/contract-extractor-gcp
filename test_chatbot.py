"""
Test script for Document Chatbot functionality
"""

import os
from document_chat import DocumentChatbot

def test_chatbot():
    """Test the chatbot with a sample document."""
    
    print("=" * 60)
    print("Testing Document Chatbot")
    print("=" * 60)
    
    # Initialize chatbot
    print("\n[1/4] Initializing chatbot...")
    chatbot = DocumentChatbot()
    print("✓ Chatbot initialized successfully")
    
    # Test with a sample document (if exists)
    test_file = "invoices/lease_invoice_LS-2025-203.pdf"
    
    if not os.path.exists(test_file):
        print(f"\n⚠️  Test file not found: {test_file}")
        print("Please provide a valid document path to test.")
        print("\nYou can test the chatbot through the web UI:")
        print("1. Start the server: python app.py")
        print("2. Open http://localhost:8000")
        print("3. Click the purple chat button in bottom-right corner")
        print("4. Upload a document and ask questions")
        return
    
    # Create session
    print(f"\n[2/4] Creating session with document: {test_file}")
    session_id = "test-session-001"
    result = chatbot.create_session(session_id, test_file)
    
    if result["success"]:
        print(f"✓ Session created: {session_id}")
        print(f"  - Filename: {result['filename']}")
        print(f"  - Chunks: {result['chunks']}")
        print(f"  - Document length: {result['document_length']} characters")
    else:
        print(f"✗ Failed to create session: {result.get('error')}")
        return
    
    # Ask a test question
    print("\n[3/4] Asking test question...")
    question = "What is the total amount?"
    print(f"  Question: {question}")
    
    answer_result = chatbot.simple_ask(session_id, question)
    
    if answer_result["success"]:
        print(f"✓ Answer received:")
        print(f"\n  {answer_result['answer']}\n")
        
        if answer_result.get("excerpts"):
            print("  Relevant excerpts:")
            for i, excerpt in enumerate(answer_result["excerpts"], 1):
                print(f"  {i}. \"{excerpt[:100]}...\"")
    else:
        print(f"✗ Failed to get answer: {answer_result.get('error')}")
    
    # Clean up
    print("\n[4/4] Cleaning up...")
    chatbot.delete_session(session_id)
    print("✓ Session deleted")
    
    print("\n" + "=" * 60)
    print("✓ Chatbot test completed successfully!")
    print("=" * 60)
    print("\nTo use the chatbot in the web application:")
    print("1. Start the server: python app.py")
    print("2. Open http://localhost:8000 in your browser")
    print("3. Click the purple chat button (💬) in the bottom-right corner")
    print("4. Upload any PDF, DOCX, or TXT document")
    print("5. Ask questions about the document!")


if __name__ == "__main__":
    try:
        test_chatbot()
    except Exception as e:
        print(f"\n✗ Error during test: {str(e)}")
        print("\nMake sure you have:")
        print("1. Installed all requirements: pip install -r requirements.txt")
        print("2. Set OPENAI_API_KEY in .env file")
        print("3. A valid test document in the project directory")

