// Authentication Constants
const VALID_USERNAME = 'HtsAI-testuser';
const VALID_PASSWORD = 'HTStest@2025';
const SESSION_KEY = 'contractAppLoggedIn';

// Global variables
let currentExtractionId = null;
let extractionInterval = null;

// Expose to window for chatbot integration
window.currentExtractionId = null;

// Currency symbol mapping
const CURRENCY_SYMBOLS = {
    // Major currencies with symbols
    'USD': '$',
    'INR': '₹',
    'EUR': '€',
    'GBP': '£',
    'JPY': '¥',
    'CNY': '¥',
    'CHF': 'Fr.',
    'CAD': 'C$',
    'AUD': 'A$',
    'NZD': 'NZ$',
    'SGD': 'S$',
    'HKD': 'HK$',
    'TWD': 'NT$',
    'MYR': 'RM',
    'THB': '฿',
    'PHP': '₱',
    'IDR': 'Rp',
    'VND': '₫',
    'KRW': '₩',
    'TRY': '₺',
    'RUB': '₽',
    'BRL': 'R$',
    'ZAR': 'R',
    'PLN': 'zł',
    // Gulf currencies (no common symbols - use code)
    'QAR': 'QAR',
    'SAR': 'SAR',
    'AED': 'AED',
    'KWD': 'KWD',
    'BHD': 'BHD',
    'OMR': 'OMR',
    // Other currencies
    'EGP': 'E£',
    'PKR': 'Rs',
    'LKR': 'Rs',
    'BDT': '৳',
    'NPR': 'Rs',
    'MXN': '$',
    'SEK': 'kr',
    'NOK': 'kr',
    'DKK': 'kr'
};

/**
 * Format amount with appropriate currency symbol or code
 * @param {string|number} amount - The amount to format
 * @param {string} currency - The currency code (e.g., 'QAR', 'USD', 'INR')
 * @returns {string} Formatted amount with currency
 */
function formatAmountWithCurrency(amount, currency) {
    if (!amount) return '-';
    
    const currencyCode = (currency || '').toUpperCase().trim();
    const symbol = CURRENCY_SYMBOLS[currencyCode] || currencyCode || '$';
    
    // Format number with commas
    const numAmount = parseFloat(String(amount).replace(/,/g, ''));
    const formattedAmount = isNaN(numAmount) ? amount : numAmount.toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    
    // For currencies without symbols (like QAR), put code before amount with space
    // For currencies with symbols (like $, ₹), put symbol directly before amount
    if (symbol.length > 1) {
        return `${symbol} ${formattedAmount}`;
    } else {
        return `${symbol}${formattedAmount}`;
    }
}

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
        
        // Check if it's a duplicate invoice warning
        if (extractData.status === 'duplicate_invoice' && extractData.warning === true) {
            console.log('Duplicate invoice detected:', extractData);
            
            // Show custom warning modal (replaces browser alert)
            showDuplicateInvoiceModal(extractData);
            
            // Show status error
            const invoiceId = extractData.details?.invoice_id || 'Unknown';
            showStatus(`Duplicate invoice: ${invoiceId} already exists`, 'error');
            
            // Reset button and hide extracted content
            btn.disabled = false;
            btn.innerHTML = '<span class="icon">🔍</span> Extract Information';
            
            const extractedContent = document.getElementById('extractedContent');
            if (extractedContent) {
                extractedContent.style.display = 'none';
            }
            
            // Clear extraction ID since it wasn't saved
            currentExtractionId = null;
            window.currentExtractionId = null;
            
            return; // Stop here - don't display results
        }
        
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
    
    // Risk Score - Show label instead of number
    const riskScoreValue = parseInt(results.risk_score) || 0;
    
    // Determine risk level from score
    let riskLevel = 'Low';
    let riskClass = 'low';
    if (riskScoreValue >= 80) {
        riskLevel = 'Critical';
        riskClass = 'critical';
    } else if (riskScoreValue >= 60) {
        riskLevel = 'High';
        riskClass = 'high';
    } else if (riskScoreValue >= 30) {
        riskLevel = 'Medium';
        riskClass = 'medium';
    }
    
    document.getElementById('riskScore').textContent = riskLevel;
    document.getElementById('riskScore').className = 'risk-badge ' + riskClass;
    
    // Parties
    document.getElementById('party1Name').textContent = results.parties?.party_1_name || '-';
    document.getElementById('party1Address').textContent = results.parties?.party_1_address || '-';
    document.getElementById('party2Name').textContent = results.parties?.party_2_name || '-';
    document.getElementById('party2Address').textContent = results.parties?.party_2_address || '-';
    
    // Set party labels (Vendor/Customer) - use types from backend, default to Vendor/Customer if not provided
    const party1Type = results.parties?.party_1_type || 'Vendor';
    const party2Type = results.parties?.party_2_type || 'Customer';
    
    document.getElementById('party1Label').textContent = party1Type;
    document.getElementById('party2Label').textContent = party2Type;
    
    // Payment Terms
    const payment = results.payment_terms || {};
    document.getElementById('paymentAmount').textContent = payment.amount ? 
        formatAmountWithCurrency(payment.amount, payment.currency) : '-';
    document.getElementById('paymentCurrency').textContent = payment.currency || '-';
    document.getElementById('paymentFrequency').textContent = payment.frequency || '1';  // Default to "1" if empty
    
    // Amount Explanation (shows how total was calculated based on document)
    const amountExplanationEl = document.getElementById('amountExplanation');
    if (amountExplanationEl) {
        const explanation = payment.amount_explanation || results.amount_explanation || '';
        if (explanation) {
            amountExplanationEl.textContent = explanation;
            amountExplanationEl.style.display = 'block';
        } else {
            amountExplanationEl.style.display = 'none';
        }
    }
    
    // Account Details
    const paymentDetails = results.payment_details || {};
    const accountDetailsSection = document.getElementById('accountDetailsSection');
    const indianAccountDetails = document.getElementById('indianAccountDetails');
    const internationalAccountDetails = document.getElementById('internationalAccountDetails');
    const bankAddressSection = document.getElementById('bankAddressSection');
    
    // Check if we have any account details
    const hasAccountDetails = paymentDetails.account_holder_name || 
                             paymentDetails.account_number || 
                             paymentDetails.account_number_iban || 
                             paymentDetails.ifsc_code || 
                             paymentDetails.swift_code || 
                             paymentDetails.branch || 
                             paymentDetails.bank_address;
    
    if (hasAccountDetails) {
        accountDetailsSection.style.display = 'block';
        
        // Determine if it's Indian account (has IFSC) or international (has SWIFT/IBAN)
        const hasIFSC = paymentDetails.ifsc_code && paymentDetails.ifsc_code.trim() !== '';
        const hasSWIFT = paymentDetails.swift_code && paymentDetails.swift_code.trim() !== '';
        const hasIBAN = paymentDetails.account_number_iban && paymentDetails.account_number_iban.trim() !== '';
        
        if (hasIFSC || (paymentDetails.account_number && !hasSWIFT && !hasIBAN)) {
            // Indian account format
            indianAccountDetails.style.display = 'block';
            internationalAccountDetails.style.display = 'none';
            
            document.getElementById('accountHolderName').textContent = paymentDetails.account_holder_name || '-';
            document.getElementById('accountNumber').textContent = paymentDetails.account_number || '-';
            document.getElementById('ifscCode').textContent = paymentDetails.ifsc_code || '-';
            document.getElementById('branch').textContent = paymentDetails.branch || '-';
        } else if (hasSWIFT || hasIBAN) {
            // International account format
            indianAccountDetails.style.display = 'none';
            internationalAccountDetails.style.display = 'block';
            
            document.getElementById('accountNumberIban').textContent = paymentDetails.account_number_iban || paymentDetails.account_number || '-';
            document.getElementById('swiftCode').textContent = paymentDetails.swift_code || '-';
        } else {
            // Fallback: show Indian format if account_number exists
            if (paymentDetails.account_number) {
                indianAccountDetails.style.display = 'block';
                internationalAccountDetails.style.display = 'none';
                
                document.getElementById('accountHolderName').textContent = paymentDetails.account_holder_name || '-';
                document.getElementById('accountNumber').textContent = paymentDetails.account_number || '-';
                document.getElementById('ifscCode').textContent = paymentDetails.ifsc_code || '-';
                document.getElementById('branch').textContent = paymentDetails.branch || '-';
            } else {
                indianAccountDetails.style.display = 'none';
                internationalAccountDetails.style.display = 'none';
            }
        }
        
        // Bank Address (common for both)
        if (paymentDetails.bank_address && paymentDetails.bank_address.trim() !== '') {
            bankAddressSection.style.display = 'block';
            document.getElementById('bankAddress').textContent = paymentDetails.bank_address;
        } else {
            bankAddressSection.style.display = 'none';
        }
    } else {
        accountDetailsSection.style.display = 'none';
    }
    
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

// ============================================================
// DUPLICATE INVOICE WARNING MODAL FUNCTIONS
// ============================================================

/**
 * Show the duplicate invoice warning modal with details
 * @param {Object} data - The duplicate invoice response data
 */
function showDuplicateInvoiceModal(data) {
    const modal = document.getElementById('duplicateWarningModal');
    if (!modal) {
        console.error('Duplicate warning modal not found in DOM');
        return;
    }
    
    const details = data.details || {};
    
    // Populate modal data
    const invoiceId = details.invoice_id || 'Unknown';
    const existingDoc = details.existing_document || 'Unknown';
    const processedDate = details.processed_date || '';
    const vendor = details.vendor || '';
    const amount = details.amount || '';
    const currency = details.currency || '';
    
    // Set invoice ID
    const invoiceIdEl = document.getElementById('duplicateInvoiceId');
    if (invoiceIdEl) {
        invoiceIdEl.textContent = invoiceId;
    }
    
    // Set existing file name
    const existingFileEl = document.getElementById('duplicateExistingFile');
    if (existingFileEl) {
        existingFileEl.textContent = existingDoc;
    }
    
    // Set vendor (show/hide based on availability)
    const vendorItem = document.getElementById('duplicateVendorItem');
    const vendorEl = document.getElementById('duplicateVendor');
    if (vendor && vendor.trim()) {
        if (vendorItem) vendorItem.style.display = 'flex';
        if (vendorEl) vendorEl.textContent = vendor;
    } else {
        if (vendorItem) vendorItem.style.display = 'none';
    }
    
    // Set amount (show/hide based on availability)
    const amountItem = document.getElementById('duplicateAmountItem');
    const amountEl = document.getElementById('duplicateAmount');
    if (amount && amount.toString().trim()) {
        if (amountItem) amountItem.style.display = 'flex';
        if (amountEl) {
            amountEl.textContent = formatAmountWithCurrency(amount, currency);
        }
    } else {
        if (amountItem) amountItem.style.display = 'none';
    }
    
    // Set processed date
    const processedDateEl = document.getElementById('duplicateProcessedDate');
    if (processedDateEl) {
        if (processedDate) {
            try {
                const dateObj = new Date(processedDate);
                processedDateEl.textContent = dateObj.toLocaleString('en-US', {
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: true
                });
            } catch (e) {
                processedDateEl.textContent = processedDate;
            }
        } else {
            processedDateEl.textContent = 'Unknown';
        }
    }
    
    // Show modal
    modal.style.display = 'flex';
    
    // Add event listeners for closing modal
    setupDuplicateModalCloseListeners();
    
    // Log for debugging
    console.log('[DUPLICATE MODAL] Showing duplicate invoice warning:', {
        invoiceId,
        existingDoc,
        vendor,
        amount,
        currency,
        processedDate
    });
}

/**
 * Close the duplicate invoice warning modal
 */
function closeDuplicateInvoiceModal() {
    const modal = document.getElementById('duplicateWarningModal');
    if (modal) {
        modal.style.display = 'none';
        console.log('[DUPLICATE MODAL] Modal closed');
    }
}

/**
 * Setup event listeners for closing the duplicate modal
 */
function setupDuplicateModalCloseListeners() {
    // Close button (X)
    const closeBtn = document.getElementById('closeDuplicateModal');
    if (closeBtn) {
        closeBtn.onclick = closeDuplicateInvoiceModal;
    }
    
    // OK button
    const okBtn = document.getElementById('duplicateModalOkBtn');
    if (okBtn) {
        okBtn.onclick = closeDuplicateInvoiceModal;
    }
    
    // Click outside modal to close
    const modal = document.getElementById('duplicateWarningModal');
    if (modal) {
        modal.onclick = function(event) {
            if (event.target === modal) {
                closeDuplicateInvoiceModal();
            }
        };
    }
    
    // ESC key to close
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const modal = document.getElementById('duplicateWarningModal');
            if (modal && modal.style.display === 'flex') {
                closeDuplicateInvoiceModal();
            }
        }
    });
}
