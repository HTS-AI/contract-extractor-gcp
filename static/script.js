// Authentication Constants
const VALID_USERNAME = 'HtsAI-testuser';
const VALID_PASSWORD = 'HTStest@2025';
const SESSION_KEY = 'contractAppLoggedIn';

// Global variables
let currentExtractionId = null;
let extractionInterval = null;

// Expose to window for chatbot integration
window.currentExtractionId = null;

// Initialize
document.addEventListener('DOMContentLoaded', async function() {
    checkAuthentication();
    setupAuthListeners();
    setupEventListeners();
    loadDashboard();
    
    // Load list first, then restore last viewed
    await loadExtractionsList();
    
    // Auto-restore last viewed extraction after list is loaded
    setTimeout(() => {
        restoreLastViewedExtraction();
    }, 300);
});

// Authentication Functions
function checkAuthentication() {
    const isLoggedIn = sessionStorage.getItem(SESSION_KEY);
    const loginPage = document.getElementById('loginPage');
    const mainApp = document.getElementById('mainApp');
    
    if (isLoggedIn === 'true') {
        // User is logged in, show main app
        loginPage.style.display = 'none';
        mainApp.style.display = 'block';
    } else {
        // User not logged in, show login page
        loginPage.style.display = 'flex';
        mainApp.style.display = 'none';
    }
}

function setupAuthListeners() {
    const loginForm = document.getElementById('loginForm');
    const logoutBtn = document.getElementById('logoutBtn');
    
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

function handleLogin(event) {
    event.preventDefault();
    
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const loginError = document.getElementById('loginError');
    
    // Validate credentials
    if (username === VALID_USERNAME && password === VALID_PASSWORD) {
        // Login successful
        sessionStorage.setItem(SESSION_KEY, 'true');
        loginError.style.display = 'none';
        
        // Show main app, hide login
        document.getElementById('loginPage').style.display = 'none';
        document.getElementById('mainApp').style.display = 'block';
        
        // Clear form
        document.getElementById('loginForm').reset();
    } else {
        // Login failed
        loginError.textContent = 'Invalid username or password. Please try again.';
        loginError.style.display = 'block';
        
        // Shake animation
        const loginContainer = document.querySelector('.login-container');
        loginContainer.style.animation = 'shake 0.5s';
        setTimeout(() => {
            loginContainer.style.animation = '';
        }, 500);
    }
}

function handleLogout() {
    // Clear session
    sessionStorage.removeItem(SESSION_KEY);
    
    // Show login page, hide main app
    document.getElementById('loginPage').style.display = 'flex';
    document.getElementById('mainApp').style.display = 'none';
    
    // Clear any sensitive data
    currentExtractionId = null;
    
    // Clear form
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.reset();
    }
}

// Setup event listeners
function setupEventListeners() {
    const fileInput = document.getElementById('fileInput');
    const extractBtn = document.getElementById('extractBtn');
    const documentSelector = document.getElementById('documentSelector');
    
    fileInput.addEventListener('change', handleFileSelect);
    extractBtn.addEventListener('click', handleExtract);
    if (documentSelector) {
        documentSelector.addEventListener('change', handleDocumentSelection);
    }
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (file) {
        const fileNameEl = document.getElementById('fileName');
        const fileInfoEl = document.getElementById('fileInfo');
        
        // Truncate long file names
        const displayName = file.name.length > 30 ? file.name.substring(0, 30) + '...' : file.name;
        fileNameEl.textContent = displayName;
        fileInfoEl.textContent = `${(file.size / 1024).toFixed(1)} KB • ${file.name.split('.').pop().toUpperCase()}`;
        
        // Hide previous extraction when new file is selected
        const extractedContent = document.getElementById('extractedContent');
        if (extractedContent) {
            extractedContent.style.display = 'none';
        }
        
        // Reset document selector
        const documentSelector = document.getElementById('documentSelector');
        if (documentSelector) {
            documentSelector.value = '';
        }
        
        // Clear last viewed extraction (will be replaced with new extraction)
        try {
            localStorage.removeItem('lastViewedExtractionId');
        } catch (e) {
            console.error('Failed to clear last viewed extraction:', e);
        }
        
        // Reset chatbot session when new file is selected
        if (window.chatbot) {
            console.log('[MAIN] New file selected, resetting chatbot session...');
            window.chatbot.resetChat();
            // Clear any pending extraction ID
            window.currentExtractionId = null;
        }
        
        document.getElementById('extractBtn').disabled = false;
        showStatus('New file selected: ' + file.name + '. Click Extract to process.', 'info');
    }
}

// Handle extract button click
async function handleExtract() {
    const fileInput = document.getElementById('fileInput');
    const file = fileInput.files[0];
    
    if (!file) {
        showStatus('Please select a file first', 'error');
        return;
    }
    
    const btn = document.getElementById('extractBtn');
    
    try {
        // Disable button and show loading
        btn.disabled = true;
        btn.innerHTML = '<span class="loading"></span> Processing...';
        showStatus('Uploading file...', 'info');
        
        // Step 1: Upload file
        const formData = new FormData();
        formData.append('file', file);
        
        console.log('Uploading file:', file.name);
        const uploadResponse = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        if (!uploadResponse.ok) {
            const errorData = await uploadResponse.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(errorData.detail || 'Upload failed');
        }
        
        const uploadData = await uploadResponse.json();
        currentExtractionId = uploadData.extraction_id;
        console.log('File uploaded. Extraction ID:', currentExtractionId);
        
        // Store extraction ID for chatbot integration (reuses parsed data - no re-parsing!)
        window.currentExtractionId = currentExtractionId;
        console.log('[MAIN] Stored extraction ID for chatbot:', currentExtractionId);
        
        // Add visual indicator to chatbot button
        const chatbotButton = document.getElementById('chatbot-button');
        if (chatbotButton) {
            chatbotButton.classList.add('has-document');
            chatbotButton.title = 'Chat about your uploaded document';
            console.log('[MAIN] Added has-document indicator to chatbot button');
        }
        
        showStatus('File uploaded. Extracting information... (This may take 10-30 seconds)', 'info');
        
        // Step 2: Extract information with timeout
        console.log('Starting extraction...');
        const extractPromise = fetch(`/api/extract/${currentExtractionId}`, {
            method: 'POST'
        });
        
        // Add timeout (5 minutes for large documents with ML processing)
        const timeoutPromise = new Promise((_, reject) => 
            setTimeout(() => reject(new Error('Extraction timeout. The document may be too large or complex.')), 300000)
        );
        
        const extractResponse = await Promise.race([extractPromise, timeoutPromise]);
        
        if (!extractResponse.ok) {
            const errorData = await extractResponse.json().catch(() => ({ detail: 'Extraction failed' }));
            throw new Error(errorData.detail || `Extraction failed: ${extractResponse.status}`);
        }
        
        const extractData = await extractResponse.json();
        console.log('Extraction completed. Results:', extractData);
        
        if (!extractData.results) {
            throw new Error('No results returned from extraction');
        }
        
        // Step 3: Display results
        displayResults(extractData.results, currentExtractionId);
        showStatus('Extraction completed successfully!', 'success');
        
        // Update document selector to show the newly extracted document as selected
        setTimeout(() => {
            const documentSelector = document.getElementById('documentSelector');
            if (documentSelector) {
                documentSelector.value = currentExtractionId;
            }
        }, 100);
        
        // Automatically restart chatbot session with the new file
        if (window.chatbot) {
            console.log('[MAIN] Extraction completed, automatically restarting chatbot session for new file...');
            // Auto-load from extraction (reuses parsed data - no re-parsing!)
            // The autoLoadFromExtraction method will handle resetting if needed
            setTimeout(() => {
                window.chatbot.autoLoadFromExtraction(currentExtractionId);
                // If chatbot popup is already open, show a notification
                if (window.chatbot.isOpen) {
                    console.log('[MAIN] Chatbot is open, session automatically reloaded for new file');
                }
            }, 500); // Small delay to ensure extraction is fully saved
        }
        
        // Reload dashboard and extractions list
        loadDashboard();
        reloadExtractionsList();
        
    } catch (error) {
        console.error('Error details:', error);
        const errorMessage = error.message || 'An unknown error occurred';
        showStatus('Error: ' + errorMessage, 'error');
        
        // Show error in console for debugging
        if (error.stack) {
            console.error('Error stack:', error.stack);
        }
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span class="btn-icon">⚡</span><span>Extract</span>';
    }
}

// Display extraction results
function displayResults(results, extractionId = null) {
    // Save the current extraction ID to localStorage for restoration
    if (extractionId) {
        try {
            localStorage.setItem('lastViewedExtractionId', extractionId);
            console.log('Saved extraction ID to localStorage:', extractionId);
        } catch (e) {
            console.error('Failed to save extraction ID:', e);
        }
    }
    
    // Show extracted content
    const extractedContent = document.getElementById('extractedContent');
    
    if (extractedContent) {
        extractedContent.style.display = 'block';
        console.log('Extracted content displayed');
    }
    
    // Display extraction method metadata
    displayExtractionMetadata(results._extraction_metadata);
    
    // Basic Information
    document.getElementById('contractTitle').textContent = results.contract_title || '-';
    document.getElementById('contractType').textContent = results.contract_type || '-';
    document.getElementById('contractType').className = 'badge ' + (results.contract_type || '').toLowerCase();
    document.getElementById('executionDate').textContent = results.execution_date || '-';
    
    // Risk Score
    const riskScore = parseInt(results.risk_score) || 0;
    document.getElementById('riskScore').textContent = riskScore;
    document.getElementById('riskScore').className = 'risk-badge ' + 
        (riskScore < 30 ? 'low' : riskScore < 60 ? 'medium' : 'high');
    
    // Parties
    document.getElementById('party1Name').textContent = results.parties?.party_1_name || '-';
    document.getElementById('party1Address').textContent = results.parties?.party_1_address || '-';
    document.getElementById('party2Name').textContent = results.parties?.party_2_name || '-';
    document.getElementById('party2Address').textContent = results.parties?.party_2_address || '-';
    
    // Payment Terms
    const payment = results.payment_terms || {};
    document.getElementById('paymentAmount').textContent = payment.amount ? 
        (payment.currency === 'INR' ? '₹' : '$') + payment.amount : '-';
    document.getElementById('paymentCurrency').textContent = payment.currency || '-';
    document.getElementById('paymentFrequency').textContent = payment.frequency || '-';
    
    // Clauses
    document.getElementById('terminationClause').textContent = 
        results.termination_clause ? results.termination_clause.substring(0, 200) + '...' : '-';
    document.getElementById('confidentialityClause').textContent = 
        results.confidentiality_clause ? results.confidentiality_clause.substring(0, 200) + '...' : '-';
    document.getElementById('liabilityClause').textContent = 
        results.liability_clause ? results.liability_clause.substring(0, 200) + '...' : '-';
    document.getElementById('governingLaw').textContent = results.governing_law || '-';
    
    // Deliverables
    const deliverablesList = document.getElementById('deliverablesList');
    deliverablesList.innerHTML = '';
    if (results.deliverables && results.deliverables.length > 0) {
        results.deliverables.forEach(item => {
            const li = document.createElement('li');
            li.textContent = item;
            deliverablesList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = 'No deliverables specified';
        deliverablesList.appendChild(li);
    }
    
    // Missing Clauses
    const missingClauses = results.missing_clauses || [];
    const missingClausesCard = document.getElementById('missingClausesCard');
    const missingClausesList = document.getElementById('missingClausesList');
    
    if (missingClauses.length > 0) {
        missingClausesCard.style.display = 'block';
        missingClausesList.innerHTML = '';
        missingClauses.forEach(clause => {
            const li = document.createElement('li');
            li.textContent = clause;
            missingClausesList.appendChild(li);
        });
    } else {
        missingClausesCard.style.display = 'none';
    }
}

// Load dashboard data
async function loadDashboard() {
    try {
        const response = await fetch('/api/dashboard');
        const data = await response.json();
        
        // Update statistics
        document.getElementById('totalDocuments').textContent = data.total_documents || 0;
        document.getElementById('avgRiskScore').textContent = data.average_risk_score || 0;
        document.getElementById('missingClauses').textContent = data.total_missing_clauses || 0;
        document.getElementById('contractTypes').textContent = Object.keys(data.contract_types || {}).length;
        
        // Update contract types chart
        updateContractTypesChart(data.contract_types || {});
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
    }
}

// Update contract types chart
function updateContractTypesChart(contractTypes) {
    const chartContainer = document.getElementById('contractTypesChart');
    chartContainer.innerHTML = '';
    
    if (Object.keys(contractTypes).length === 0) {
        chartContainer.innerHTML = '<p style="text-align: center; color: #666;">No data available</p>';
        return;
    }
    
    Object.entries(contractTypes).forEach(([type, count]) => {
        const bar = document.createElement('div');
        bar.className = 'chart-bar';
        bar.innerHTML = `
            <div class="chart-bar-label">${type}</div>
            <div class="chart-bar-value">${count}</div>
        `;
        chartContainer.appendChild(bar);
    });
}

// Display extraction metadata
function displayExtractionMetadata(metadata) {
    // Extraction Method section removed from UI as per user request
    // This function is kept for backward compatibility but does nothing
    return;
}

// Show status message
function showStatus(message, type) {
    const statusDiv = document.getElementById('uploadStatus');
    statusDiv.textContent = message;
    statusDiv.className = 'status-message ' + type;
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        statusDiv.textContent = '';
        statusDiv.className = 'status-message';
    }, 5000);
}

// Restore last viewed extraction from localStorage
async function restoreLastViewedExtraction() {
    try {
        const lastExtractionId = localStorage.getItem('lastViewedExtractionId');
        
        if (lastExtractionId) {
            console.log('Restoring last viewed extraction ID:', lastExtractionId);
            
            // Try to load the extraction data
            const response = await fetch(`/api/extraction/${lastExtractionId}`);
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success && data.results) {
                    console.log('Successfully restored extraction:', data.file_name);
                    
                    // Set the dropdown to this document
                    const documentSelector = document.getElementById('documentSelector');
                    if (documentSelector) {
                        documentSelector.value = lastExtractionId;
                    }
                    
                    // Display the results
                    displayResults(data.results, lastExtractionId);
                    
                    // Show subtle notification
                    setTimeout(() => {
                        const statusDiv = document.getElementById('uploadStatus');
                        if (statusDiv) {
                            statusDiv.textContent = `✓ Restored: ${data.file_name}`;
                            statusDiv.className = 'status-message success';
                            setTimeout(() => {
                                statusDiv.textContent = '';
                                statusDiv.className = 'status-message';
                            }, 3000);
                        }
                    }, 600);
                } else {
                    console.log('No results found for extraction ID:', lastExtractionId);
                    // Clear invalid extraction ID
                    localStorage.removeItem('lastViewedExtractionId');
                }
            } else {
                console.log('Extraction not found on server, clearing from localStorage');
                // Clear invalid extraction ID
                localStorage.removeItem('lastViewedExtractionId');
            }
        } else {
            console.log('No last viewed extraction ID found in localStorage');
        }
    } catch (e) {
        console.error('Failed to restore last viewed extraction:', e);
        console.error('Error details:', e.message);
        // Clear invalid extraction ID
        localStorage.removeItem('lastViewedExtractionId');
    }
}

// Debug function to check localStorage (can be called from browser console)
function checkLocalStorage() {
    const extractionId = localStorage.getItem('lastViewedExtractionId');
    console.log('=== localStorage Debug Info ===');
    console.log('Last Viewed Extraction ID:', extractionId);
    console.log('Has Saved ID:', !!extractionId);
    console.log('==============================');
    return extractionId;
}

// Make debug function available globally
window.checkLocalStorage = checkLocalStorage;

// Load list of previously extracted documents
async function loadExtractionsList() {
    try {
        const response = await fetch('/api/extractions-list');
        const data = await response.json();
        
        if (data.success && data.extractions && data.extractions.length > 0) {
            const selectorContainer = document.getElementById('documentSelectorContainer');
            const documentSelector = document.getElementById('documentSelector');
            
            // Show the selector container
            if (selectorContainer) {
                selectorContainer.style.display = 'block';
            }
            
            // Clear existing options except the first one
            if (documentSelector) {
                while (documentSelector.options.length > 1) {
                    documentSelector.remove(1);
                }
                
                // Add options for each extraction
                data.extractions.forEach(extraction => {
                    const option = document.createElement('option');
                    option.value = extraction.extraction_id;
                    
                    // Format the display text
                    const date = extraction.extracted_at ? new Date(extraction.extracted_at).toLocaleString() : 'Unknown date';
                    const fileName = extraction.file_name || 'Unknown file';
                    const docType = extraction.document_type || '';
                    
                    option.textContent = `${fileName} - ${docType} (${date})`;
                    documentSelector.appendChild(option);
                });
                
                console.log(`Loaded ${data.extractions.length} previous extractions`);
            }
        } else {
            console.log('No previous extractions found');
        }
    } catch (error) {
        console.error('Error loading extractions list:', error);
    }
}

// Handle document selection from dropdown
async function handleDocumentSelection(event) {
    const extractionId = event.target.value;
    
    if (!extractionId) {
        // User selected the placeholder option
        // Clear last viewed extraction
        try {
            localStorage.removeItem('lastViewedExtractionId');
        } catch (e) {
            console.error('Failed to clear last viewed extraction:', e);
        }
        
        // Hide extracted content
        const extractedContent = document.getElementById('extractedContent');
        if (extractedContent) {
            extractedContent.style.display = 'none';
        }
        return;
    }
    
    try {
        showStatus('Loading selected document...', 'info');
        
        const response = await fetch(`/api/extraction/${extractionId}`);
        
        if (!response.ok) {
            throw new Error('Failed to load extraction data');
        }
        
        const data = await response.json();
        
        if (data.success && data.results) {
            console.log('Loaded extraction:', data.file_name);
            // Display the extraction results and save the extraction ID
            displayResults(data.results, extractionId);
            showStatus(`✓ Loaded: ${data.file_name}`, 'success');
            setTimeout(() => {
                const statusDiv = document.getElementById('uploadStatus');
                if (statusDiv) {
                    statusDiv.textContent = '';
                    statusDiv.className = 'status-message';
                }
            }, 3000);
        } else {
            throw new Error('No results found for this extraction');
        }
    } catch (error) {
        console.error('Error loading extraction:', error);
        showStatus('Failed to load extraction: ' + error.message, 'error');
    }
}

// Reload extractions list after new extraction
async function reloadExtractionsList() {
    await loadExtractionsList();
}
