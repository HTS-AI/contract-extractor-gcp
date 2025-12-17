/**
 * Document Chatbot - Frontend Logic
 * Handles document upload and Q&A interaction
 */

class DocumentChatbot {
    constructor() {
        this.sessionId = null;
        this.filename = null;
        this.isScanned = false;
        this.usedOCR = false;
        this.isOpen = false;
        this.isUploading = false;
        this.isAsking = false;
        this.lastExtractionId = null; // Track last loaded extraction ID
        
        this.initializeElements();
        this.attachEventListeners();
    }
    
    initializeElements() {
        // Main elements
        this.chatbotButton = document.getElementById('chatbot-button');
        this.chatbotPopup = document.getElementById('chatbot-popup');
        this.closeButton = document.getElementById('chatbot-close');
        
        // Sections
        this.uploadSection = document.getElementById('upload-section');
        this.chatSection = document.getElementById('chat-section');
        this.loadingSection = document.getElementById('loading-section');
        
        // Upload elements
        this.fileInput = document.getElementById('chat-file-input');
        this.uploadButton = document.getElementById('upload-doc-button');
        
        // Chat elements
        this.documentInfo = document.getElementById('document-info');
        this.documentFilename = document.getElementById('document-filename');
        this.changeDocButton = document.getElementById('change-document');
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-button');
    }
    
    attachEventListeners() {
        // Toggle popup
        this.chatbotButton.addEventListener('click', () => this.togglePopup());
        this.closeButton.addEventListener('click', () => this.closePopup());
        
        // Upload
        this.uploadButton.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileUpload(e));
        
        // Change document
        this.changeDocButton.addEventListener('click', () => this.resetChat());
        
        // Send message
        this.sendButton.addEventListener('click', () => this.sendMessage());
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }
    
    togglePopup() {
        if (this.isOpen) {
            this.closePopup();
        } else {
            this.openPopup();
        }
    }
    
    async openPopup() {
        console.log('[CHATBOT] Opening popup...');
        console.log('[CHATBOT] Current session:', this.sessionId);
        console.log('[CHATBOT] Window.currentExtractionId:', window.currentExtractionId);
        
        this.chatbotPopup.classList.add('active');
        this.isOpen = true;
        
        // Check if there's an extraction from main upload that hasn't been loaded yet
        // Always check for new extraction, even if session exists (file might have changed)
        if (window.currentExtractionId) {
            // If we have a session but it's from a different extraction, reset and reload
            if (this.sessionId && window.currentExtractionId !== this.lastExtractionId) {
                console.log('[CHATBOT] New extraction detected, resetting and reloading...');
                this.resetChat();
            }
            
            if (!this.sessionId) {
                console.log('[CHATBOT] Found extraction from main upload, loading from extraction:', window.currentExtractionId);
                await this.autoLoadFromExtraction(window.currentExtractionId);
            } else {
                console.log('[CHATBOT] Session already exists for current extraction');
            }
        } else {
            if (!this.sessionId) {
                console.log('[CHATBOT] No extraction from main upload, showing upload section');
            } else {
                console.log('[CHATBOT] Session exists, ready for Q&A');
            }
        }
        
        // Focus input if in chat mode
        if (this.sessionId) {
            this.chatInput.focus();
        }
    }
    
    closePopup() {
        this.chatbotPopup.classList.remove('active');
        this.isOpen = false;
    }
    
    showSection(section) {
        this.uploadSection.style.display = 'none';
        this.chatSection.style.display = 'none';
        this.loadingSection.style.display = 'none';
        
        if (section === 'upload') {
            this.uploadSection.style.display = 'block';
        } else if (section === 'chat') {
            this.chatSection.style.display = 'flex';
        } else if (section === 'loading') {
            this.loadingSection.style.display = 'block';
        }
    }
    
    async autoLoadDocument(file) {
        /**
         * Automatically load a document that was uploaded in the main extraction section
         */
        if (!file) {
            console.log('[CHATBOT] autoLoadDocument called with no file');
            return;
        }
        
        console.log('[CHATBOT] Auto-loading document:', file.name, 'Size:', file.size, 'Type:', file.type);
        
        // Show loading
        this.showSection('loading');
        this.isUploading = true;
        
        try {
            // Create form data
            const formData = new FormData();
            formData.append('file', file);
            
            console.log('[CHATBOT] Sending upload request to /api/chat/upload');
            
            // Upload to chatbot server
            const response = await fetch('/api/chat/upload', {
                method: 'POST',
                body: formData
            });
            
            console.log('[CHATBOT] Upload response status:', response.status);
            
            const result = await response.json();
            console.log('[CHATBOT] Upload result:', result);
            
            if (result.success) {
                this.sessionId = result.session_id;
                this.filename = result.filename;
                this.isScanned = result.is_scanned || false;
                this.usedOCR = result.used_ocr || false;
                
                // Custom message for auto-loaded documents
                const autoMessage = result.message + ' (Auto-loaded from your uploaded document)';
                this.initializeChat(autoMessage, true); // true = isAutoLoaded
                console.log('[CHATBOT] Document auto-loaded successfully, session:', this.sessionId);
                
                // Clear the global extraction ID so it doesn't auto-load again
                if (window.currentExtractionId) {
                    window.currentExtractionId = null;
                    console.log('[CHATBOT] Cleared window.currentExtractionId');
                    
                    // Remove visual indicator from chatbot button
                    const chatbotButton = document.getElementById('chatbot-button');
                    if (chatbotButton) {
                        chatbotButton.classList.remove('has-document');
                        chatbotButton.title = 'Ask questions about your documents';
                        console.log('[CHATBOT] Removed has-document indicator');
                    }
                }
            } else {
                console.error('[CHATBOT] Auto-load failed:', result.error);
                this.showSection('upload');
                alert('Failed to load document automatically. Please upload manually.\n\nError: ' + result.error);
            }
        } catch (error) {
            console.error('[CHATBOT] Auto-load error:', error);
            this.showSection('upload');
            alert('Error loading document automatically. Please upload manually.\n\nError: ' + error.message);
        } finally {
            this.isUploading = false;
        }
    }
    
    async autoLoadFromExtraction(extractionId) {
        /**
         * Load from existing extraction (reuses parsed text - NO re-parsing or vector creation!)
         * Automatically resets existing session if loading a different extraction.
         */
        if (!extractionId) {
            console.log('[CHATBOT] autoLoadFromExtraction called with no extraction ID');
            return;
        }
        
        // If we have a session for a different extraction, reset it first
        if (this.sessionId && this.lastExtractionId && this.lastExtractionId !== extractionId) {
            console.log('[CHATBOT] Different extraction detected, resetting current session...');
            this.resetChat();
        }
        
        // If we already have a session for this extraction, don't reload
        if (this.sessionId && this.lastExtractionId === extractionId) {
            console.log('[CHATBOT] Session already exists for this extraction, skipping reload');
            return;
        }
        
        console.log('[CHATBOT] Loading from extraction (reusing parsed text):', extractionId);
        
        // Show loading
        this.showSection('loading');
        this.isUploading = true;
        
        try {
            console.log('[CHATBOT] Sending request to /api/chat/load-from-extraction/' + extractionId);
            
            // Load from extraction (reuses already-parsed text!)
            const response = await fetch(`/api/chat/load-from-extraction/${extractionId}`, {
                method: 'POST'
            });
            
            console.log('[CHATBOT] Load response status:', response.status);
            
            const result = await response.json();
            console.log('[CHATBOT] Load result:', result);
            
            if (result.success) {
                this.sessionId = result.session_id;
                this.filename = result.filename;
                this.isScanned = result.is_scanned || false;
                this.usedOCR = result.used_ocr || false;
                this.lastExtractionId = extractionId; // Track which extraction this session is for
                
                // Custom message
                const autoMessage = result.message || `Document loaded! Ask me anything about "${result.filename}".`;
                this.initializeChat(autoMessage, true); // true = isAutoLoaded
                console.log('[CHATBOT] ✓ Loaded from extraction - NO re-parsing needed!');
                
                // Keep the extraction ID for tracking, but mark it as loaded
                // Don't clear it immediately - let it persist so we can detect file changes
                console.log('[CHATBOT] Session loaded for extraction:', extractionId);
                
                // Update visual indicator
                const chatbotButton = document.getElementById('chatbot-button');
                if (chatbotButton) {
                    chatbotButton.classList.add('has-document');
                    chatbotButton.title = `Chat about ${result.filename}`;
                }
            } else {
                console.error('[CHATBOT] Load from extraction failed:', result.error);
                this.showSection('upload');
                alert('Failed to load. Please upload manually.\n\n' + result.error);
            }
        } catch (error) {
            console.error('[CHATBOT] Load error:', error);
            this.showSection('upload');
            alert('Error loading. Please upload manually.\n\n' + error.message);
        } finally {
            this.isUploading = false;
        }
    }
    
    async handleFileUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file type
        const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
        if (!validTypes.includes(file.type) && !file.name.match(/\.(pdf|docx|txt)$/i)) {
            this.showError('Please upload a PDF, DOCX, or TXT file.');
            return;
        }
        
        // Show loading
        this.showSection('loading');
        this.isUploading = true;
        
        try {
            // Create form data
            const formData = new FormData();
            formData.append('file', file);
            
            // Upload to server
            const response = await fetch('/api/chat/upload', {
                method: 'POST',
                body: formData
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.sessionId = result.session_id;
                this.filename = result.filename;
                this.isScanned = result.is_scanned || false;
                this.usedOCR = result.used_ocr || false;
                
                // Show cache status if available
                let welcomeMessage = result.message;
                if (result.from_cache) {
                    const cacheType = result.from_cache;
                    const cacheMessage = result.cache_message || '';
                    
                    if (cacheType === 'chatbot') {
                        welcomeMessage = `⚡ ${welcomeMessage}\n\n💾 Loaded from chatbot cache - instant response!`;
                    } else if (cacheType === 'extraction') {
                        welcomeMessage = `⚡ ${welcomeMessage}\n\n💾 Loaded from extraction cache - reused parsed text!`;
                    }
                    
                    console.log('[CHATBOT] Cache status:', cacheMessage);
                }
                
                this.initializeChat(welcomeMessage, false); // false = not auto-loaded
            } else {
                this.showError(result.error || 'Failed to upload document.');
                this.showSection('upload');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showError('Network error. Please try again.');
            this.showSection('upload');
        } finally {
            this.isUploading = false;
            // Reset file input
            this.fileInput.value = '';
        }
    }
    
    initializeChat(welcomeMessage = null, isAutoLoaded = false) {
        // Show chat section
        this.showSection('chat');
        
        // Set filename with indicators
        let displayName = this.filename;
        if (this.usedOCR) {
            displayName += ' 📷 (OCR Processed)';
        }
        if (isAutoLoaded) {
            displayName = '✨ ' + displayName; // Star to indicate auto-loaded from main extraction
        }
        this.documentFilename.innerHTML = displayName;
        
        // Clear previous messages
        this.chatMessages.innerHTML = '';
        
        // Add welcome message
        const message = welcomeMessage || `Document loaded successfully! I can answer questions about "${this.filename}". What would you like to know?`;
        this.addBotMessage(message, null);
        
        // Enable input and send button
        this.chatInput.disabled = false;
        this.sendButton.disabled = false;
        
        // Focus input
        this.chatInput.focus();
    }
    
    async sendMessage() {
        const question = this.chatInput.value.trim();
        if (!question || this.isAsking) return;
        
        // Add user message
        this.addUserMessage(question);
        
        // Clear input
        this.chatInput.value = '';
        
        // Show typing indicator
        const typingId = this.addTypingIndicator();
        
        this.isAsking = true;
        this.chatInput.disabled = true;
        this.sendButton.disabled = true;
        
        try {
            const response = await fetch('/api/chat/ask', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    question: question
                })
            });
            
            const result = await response.json();
            
            // Remove typing indicator
            this.removeTypingIndicator(typingId);
            
            if (result.success) {
                this.addBotMessage(result.answer, result.excerpts);
            } else {
                this.addBotMessage(`Sorry, I encountered an error: ${result.error}`, null);
            }
        } catch (error) {
            console.error('Ask error:', error);
            this.removeTypingIndicator(typingId);
            this.addBotMessage('Network error. Please try again.', null);
        } finally {
            this.isAsking = false;
            this.chatInput.disabled = false;
            this.sendButton.disabled = false;
            this.chatInput.focus();
        }
    }
    
    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user';
        messageDiv.innerHTML = `
            <div class="message-avatar">👤</div>
            <div class="message-content">
                <div class="message-bubble">${this.escapeHtml(text)}</div>
                <div class="message-time">${this.getCurrentTime()}</div>
            </div>
        `;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addBotMessage(text, excerpts) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot';
        
        // Excerpts are not displayed in UI (removed as per user request)
        
        messageDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-bubble">${this.escapeHtml(text)}</div>
                <div class="message-time">${this.getCurrentTime()}</div>
            </div>
        `;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addTypingIndicator() {
        const id = 'typing-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.id = id;
        messageDiv.className = 'message bot';
        messageDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-bubble">
                    <div class="typing-indicator">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                </div>
            </div>
        `;
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
        return id;
    }
    
    removeTypingIndicator(id) {
        const element = document.getElementById(id);
        if (element) {
            element.remove();
        }
    }
    
    showError(message) {
        // You can enhance this to show in UI
        alert(message);
    }
    
    resetChat() {
        // Delete session if exists
        if (this.sessionId) {
            fetch(`/api/chat/session/${this.sessionId}`, {
                method: 'DELETE'
            }).catch(err => console.error('Error deleting session:', err));
        }
        
        // Reset state
        this.sessionId = null;
        this.filename = null;
        this.isScanned = false;
        this.usedOCR = false;
        this.lastExtractionId = null; // Clear last extraction ID
        this.chatMessages.innerHTML = '';
        
        // Disable input and button
        this.chatInput.disabled = true;
        this.sendButton.disabled = true;
        this.chatInput.value = '';
        
        // Show upload section
        this.showSection('upload');
        
        // Remove visual indicator
        const chatbotButton = document.getElementById('chatbot-button');
        if (chatbotButton) {
            chatbotButton.classList.remove('has-document');
            chatbotButton.title = 'Ask questions about your documents';
        }
    }
    
    scrollToBottom() {
        const chatBody = document.querySelector('.chatbot-body');
        if (chatBody) {
            setTimeout(() => {
                chatBody.scrollTop = chatBody.scrollHeight;
            }, 100);
        }
    }
    
    getCurrentTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize chatbot when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatbot = new DocumentChatbot();
});

