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
    const accountDetailsSection = document.getElementById('accountDetailsCard');
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
    
    // Invoice Details Section (only for invoices)
    const invoiceDetailsCard = document.getElementById('invoiceDetailsCard');
    const invoiceDetails = results.invoice_details || {};
    
    if (results.contract_type === 'INVOICE' && Object.keys(invoiceDetails).length > 0) {
        invoiceDetailsCard.style.display = 'block';
        
        // Invoice ID and Type
        document.getElementById('invoiceId').textContent = invoiceDetails.invoice_id || '-';
        document.getElementById('invoiceType').textContent = invoiceDetails.invoice_type || '-';
        
        // Vendor Tax IDs - Dynamic rendering
        const vendorTaxIdsSection = document.getElementById('vendorTaxIdsCard');
        const vendorTaxIdsGrid = document.getElementById('vendorTaxIdsGrid');
        const vendorTaxIds = invoiceDetails.vendor_tax_ids || {};
        
        // Define all possible tax ID fields with their display labels
        const taxIdFields = [
            { key: 'gstin', label: 'GSTIN' },
            { key: 'pan', label: 'PAN' },
            { key: 'vat', label: 'VAT Number' },
            { key: 'eori', label: 'EORI Number' },
            { key: 'tax_id', label: 'Tax ID' },
            { key: 'ein', label: 'EIN' },
            { key: 'tin', label: 'TIN' },
            { key: 'trn', label: 'TRN' },
            { key: 'cr_number', label: 'CR Number' },
            { key: 'other_id', label: 'other_id_label' } // special handling for custom label
        ];
        
        vendorTaxIdsGrid.innerHTML = '';
        let hasVendorTaxIds = false;
        
        taxIdFields.forEach(field => {
            const value = vendorTaxIds[field.key] || '';
            if (value && value.toString().trim() !== '') {
                hasVendorTaxIds = true;
                const infoItem = document.createElement('div');
                infoItem.className = 'info-item';
                
                // For other_id, use the custom label if available
                let displayLabel = field.label;
                if (field.key === 'other_id' && vendorTaxIds.other_id_label) {
                    displayLabel = vendorTaxIds.other_id_label;
                }
                
                infoItem.innerHTML = `
                    <label>${displayLabel}</label>
                    <span class="info-value" style="font-family: monospace; background: #f0fdf4; padding: 4px 8px; border-radius: 4px;">${value}</span>
                `;
                vendorTaxIdsGrid.appendChild(infoItem);
            }
        });
        
        // Fallback to old format for backward compatibility
        if (!hasVendorTaxIds) {
            if (invoiceDetails.vendor_gstin) {
                hasVendorTaxIds = true;
                vendorTaxIdsGrid.innerHTML += `
                    <div class="info-item">
                        <label>GSTIN</label>
                        <span class="info-value" style="font-family: monospace; background: #f0fdf4; padding: 4px 8px; border-radius: 4px;">${invoiceDetails.vendor_gstin}</span>
                    </div>
                `;
            }
            if (invoiceDetails.vendor_pan) {
                hasVendorTaxIds = true;
                vendorTaxIdsGrid.innerHTML += `
                    <div class="info-item">
                        <label>PAN</label>
                        <span class="info-value" style="font-family: monospace; background: #f0fdf4; padding: 4px 8px; border-radius: 4px;">${invoiceDetails.vendor_pan}</span>
                    </div>
                `;
            }
        }
        
        vendorTaxIdsSection.style.display = hasVendorTaxIds ? 'block' : 'none';
        
        // Customer Tax IDs - Dynamic rendering
        const customerTaxIdsSection = document.getElementById('customerTaxIdsCard');
        const customerTaxIdsGrid = document.getElementById('customerTaxIdsGrid');
        const customerTaxIds = invoiceDetails.customer_tax_ids || {};
        
        customerTaxIdsGrid.innerHTML = '';
        let hasCustomerTaxIds = false;
        
        taxIdFields.forEach(field => {
            const value = customerTaxIds[field.key] || '';
            if (value && value.toString().trim() !== '') {
                hasCustomerTaxIds = true;
                const infoItem = document.createElement('div');
                infoItem.className = 'info-item';
                
                // For other_id, use the custom label if available
                let displayLabel = field.label;
                if (field.key === 'other_id' && customerTaxIds.other_id_label) {
                    displayLabel = customerTaxIds.other_id_label;
                }
                
                infoItem.innerHTML = `
                    <label>${displayLabel}</label>
                    <span class="info-value" style="font-family: monospace; background: #eff6ff; padding: 4px 8px; border-radius: 4px;">${value}</span>
                `;
                customerTaxIdsGrid.appendChild(infoItem);
            }
        });
        
        // Fallback to old format for backward compatibility
        if (!hasCustomerTaxIds && invoiceDetails.customer_gstin) {
            hasCustomerTaxIds = true;
            customerTaxIdsGrid.innerHTML = `
                <div class="info-item">
                    <label>GSTIN</label>
                    <span class="info-value" style="font-family: monospace; background: #eff6ff; padding: 4px 8px; border-radius: 4px;">${invoiceDetails.customer_gstin}</span>
                </div>
            `;
        }
        
        customerTaxIdsSection.style.display = hasCustomerTaxIds ? 'block' : 'none';
        
        // Payment Terms Section
        const paymentTermsSection = document.getElementById('paymentTermsCard');
        const paymentTermsItem = document.getElementById('paymentTermsItem');
        const paymentMethodItem = document.getElementById('paymentMethodItem');
        const paymentTerms = invoiceDetails.payment_terms || invoiceDetails.payment_details?.payment_terms || '';
        const paymentMethod = invoiceDetails.payment_method || invoiceDetails.payment_details?.payment_method || '';
        
        let hasPaymentInfo = false;
        
        if (paymentTerms && paymentTerms.trim() !== '') {
            paymentTermsItem.style.display = 'block';
            document.getElementById('invoicePaymentTerms').textContent = paymentTerms;
            hasPaymentInfo = true;
        } else {
            paymentTermsItem.style.display = 'none';
        }
        
        if (paymentMethod && paymentMethod.trim() !== '') {
            paymentMethodItem.style.display = 'block';
            document.getElementById('invoicePaymentMethod').textContent = paymentMethod;
            hasPaymentInfo = true;
        } else {
            paymentMethodItem.style.display = 'none';
        }
        
        paymentTermsSection.style.display = hasPaymentInfo ? 'block' : 'none';
        
        // Bank Details
        const bankDetailsSection = document.getElementById('bankDetailsCard');
        const bankName = invoiceDetails.bank_name || '';
        const invoiceBankAddr = invoiceDetails.bank_address || '';
        
        if (bankName || invoiceBankAddr) {
            bankDetailsSection.style.display = 'block';
            document.getElementById('bankName').textContent = bankName || '-';
            document.getElementById('invoiceBankAddress').textContent = invoiceBankAddr || '-';
        } else {
            bankDetailsSection.style.display = 'none';
        }
        
        // Additional Text Section (Notes, Declaration, Terms, Remarks, etc.) - Dynamic
        const additionalTextSection = document.getElementById('additionalInfoCard');
        const additionalTextContent = document.getElementById('additionalTextContent');
        
        // Define all possible text fields with their labels and icons
        const textFields = [
            { key: 'notes', label: 'Notes', icon: '📝' },
            { key: 'declaration', label: 'Declaration', icon: '📜' },
            { key: 'terms_and_conditions', label: 'Terms & Conditions', icon: '📋' },
            { key: 'remarks', label: 'Remarks', icon: '💬' },
            { key: 'additional_info', label: 'Additional Information', icon: 'ℹ️' }
        ];
        
        // Clear previous content
        additionalTextContent.innerHTML = '';
        
        // Only add fields that have actual values
        let hasAnyTextField = false;
        textFields.forEach(field => {
            const value = invoiceDetails[field.key] || '';
            if (value && value.toString().trim() !== '') {
                hasAnyTextField = true;
                const textItem = document.createElement('div');
                textItem.className = 'info-item';
                textItem.style.marginBottom = '16px';
                textItem.innerHTML = `
                    <label style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                        <span>${field.icon}</span>
                        <span>${field.label}</span>
                    </label>
                    <span class="info-value" style="word-break: break-word; white-space: pre-wrap; display: block; background: #f8fafc; padding: 10px; border-radius: 6px; border-left: 3px solid #d97706;">${value}</span>
                `;
                additionalTextContent.appendChild(textItem);
            }
        });
        
        if (hasAnyTextField) {
            additionalTextSection.style.display = 'block';
        } else {
            additionalTextSection.style.display = 'none';
        }
        
        // Invoice Dates Section - Dynamic, only show dates that are present
        const invoiceDatesSection = document.getElementById('invoiceDatesSection');
        const invoiceDatesGrid = document.getElementById('invoiceDatesGrid');
        const dates = invoiceDetails.dates || {};
        
        // Define all possible date fields
        const dateFields = [
            { key: 'invoice_date', label: 'Invoice Date' },
            { key: 'due_date', label: 'Due Date' },
            { key: 'supply_date', label: 'Supply Date' },
            { key: 'delivery_date', label: 'Delivery Date' },
            { key: 'order_date', label: 'Order Date' },
            { key: 'ship_date', label: 'Ship Date' }
        ];
        
        // Clear previous content
        invoiceDatesGrid.innerHTML = '';
        let hasAnyDate = false;
        
        dateFields.forEach(field => {
            const value = dates[field.key] || '';
            if (value && value.toString().trim() !== '' && value !== '-') {
                hasAnyDate = true;
                const infoItem = document.createElement('div');
                infoItem.className = 'info-item';
                infoItem.innerHTML = `
                    <label>${field.label}</label>
                    <span class="info-value">${value}</span>
                `;
                invoiceDatesGrid.appendChild(infoItem);
            }
        });
        
        invoiceDatesSection.style.display = hasAnyDate ? 'block' : 'none';
        
        // Amount Breakdown Section - Completely dynamic, extracts exactly what's in invoice
        const taxDetailsSection = document.getElementById('amountBreakdownCard');
        const taxBreakdownGrid = document.getElementById('taxBreakdownGrid');
        const taxDetails = invoiceDetails.tax_details || {};
        const amounts = invoiceDetails.amounts || {};
        
        // Clear previous content
        taxBreakdownGrid.innerHTML = '';
        let hasAnyBreakdownField = false;
        
        // Helper function to add an item to the breakdown grid
        const addBreakdownItem = (label, value, isTotal = false) => {
            if (value && value.toString().trim() !== '' && value !== '0' && value !== '0.00') {
                hasAnyBreakdownField = true;
                const infoItem = document.createElement('div');
                infoItem.className = 'info-item';
                const style = isTotal ? 'font-weight: 600; color: #059669;' : '';
                infoItem.innerHTML = `
                    <label>${label}</label>
                    <span class="info-value" style="${style}">${value}</span>
                `;
                taxBreakdownGrid.appendChild(infoItem);
            }
        };
        
        // 1. Subtotal
        addBreakdownItem('Subtotal', amounts.subtotal || taxDetails.subtotal);
        
        // 2. Additional Charges (dynamic array)
        const additionalCharges = amounts.additional_charges || taxDetails.additional_charges || [];
        if (Array.isArray(additionalCharges)) {
            additionalCharges.forEach(charge => {
                if (charge && charge.label && charge.amount) {
                    addBreakdownItem(charge.label, charge.amount);
                }
            });
        }
        
        // 3. Fallback for old fixed-field format (backward compatibility)
        const oldChargeFields = ['fob_value', 'insurance', 'freight', 'freight_and_insurance', 
                                 'handling_charges', 'packaging', 'shipping', 'shipping_handling',
                                 'taxable_amount', 'other_charges'];
        const oldChargeLabels = {
            'fob_value': 'FOB Value', 'insurance': 'Insurance', 'freight': 'Freight',
            'freight_and_insurance': 'Freight & Insurance', 'handling_charges': 'Handling Charges',
            'packaging': 'Packaging', 'shipping': 'Shipping', 'shipping_handling': 'Shipping & Handling',
            'taxable_amount': 'Taxable Amount', 'other_charges': 'Other Charges'
        };
        oldChargeFields.forEach(key => {
            const value = amounts[key] || taxDetails[key];
            if (value && value.toString().trim() !== '') {
                // Check for custom description
                let label = oldChargeLabels[key];
                if (key === 'other_charges') {
                    const desc = amounts.other_charges_description || taxDetails.other_charges_description;
                    if (desc) label = desc;
                }
                addBreakdownItem(label, value);
            }
        });
        
        // 4. Discount (with percentage if available)
        const discount = amounts.discount || taxDetails.discount;
        const discountPercent = amounts.discount_percent || taxDetails.discount_percent;
        if (discount && discount.toString().trim() !== '') {
            let discountLabel = 'Discount';
            if (discountPercent) {
                const pct = discountPercent.toString().includes('%') ? discountPercent : `${discountPercent}%`;
                discountLabel = `Discount (${pct})`;
            }
            addBreakdownItem(discountLabel, discount);
        }
        
        // 5. Taxes (dynamic array)
        const taxes = amounts.taxes || taxDetails.taxes || [];
        if (Array.isArray(taxes)) {
            taxes.forEach(tax => {
                if (tax && tax.label && tax.amount) {
                    let taxLabel = tax.label;
                    if (tax.percent) {
                        const pct = tax.percent.toString().includes('%') ? tax.percent : `${tax.percent}%`;
                        taxLabel = `${tax.label} (${pct})`;
                    }
                    addBreakdownItem(taxLabel, tax.amount);
                }
            });
        }
        
        // 6. Fallback for old tax format (backward compatibility)
        const oldTaxFields = [
            { key: 'cgst', percentKey: 'cgst_percent', label: 'CGST' },
            { key: 'sgst', percentKey: 'sgst_percent', label: 'SGST' },
            { key: 'igst', percentKey: 'igst_percent', label: 'IGST' },
            { key: 'gst', percentKey: 'gst_percent', label: 'GST' },
            { key: 'vat', percentKey: 'vat_percent', label: 'VAT' },
            { key: 'tax_amount', label: 'Total Tax' }
        ];
        oldTaxFields.forEach(field => {
            const value = amounts[field.key] || taxDetails[field.key];
            if (value && value.toString().trim() !== '' && value !== '0') {
                let label = field.label;
                if (field.percentKey) {
                    const pct = amounts[field.percentKey] || taxDetails[field.percentKey];
                    if (pct) {
                        const pctStr = pct.toString().includes('%') ? pct : `${pct}%`;
                        label = `${field.label} (${pctStr})`;
                    }
                }
                addBreakdownItem(label, value);
            }
        });
        
        // 7. Totals
        addBreakdownItem('Total', amounts.total || taxDetails.total, true);
        addBreakdownItem('Amount Due', amounts.amount_due || taxDetails.amount_due, true);
        addBreakdownItem('Amount Paid', amounts.amount_paid || taxDetails.amount_paid);
        addBreakdownItem('Balance Due', amounts.balance_due || taxDetails.balance_due, true);
        
        if (hasAnyBreakdownField) {
            taxDetailsSection.style.display = 'block';
        } else {
            taxDetailsSection.style.display = 'none';
        }
    } else {
        invoiceDetailsCard.style.display = 'none';
    }
    
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

// ============================================================================
// FILE MANAGER FUNCTIONALITY
// ============================================================================

// File Manager State
let fileManagerData = {
    extraction_cache: [],
    chatbot_cache: [],
    extractions_data: [],
    exports: [],
    gcs_enabled: false,
    currentTab: 'extractions',
    isLoaded: false,
    isLoading: false,
    lastLoadTime: null
};
let selectedFiles = new Set();
let pendingDeleteAction = null;

// Preload file manager data in background when app starts
async function preloadFileManagerData() {
    if (fileManagerData.isLoading) return;
    
    fileManagerData.isLoading = true;
    console.log('[FileManager] Preloading data in background...');
    
    try {
        const response = await fetch('/api/files/list');
        const data = await response.json();
        
        if (data.success) {
            fileManagerData.extraction_cache = data.extraction_cache || [];
            fileManagerData.chatbot_cache = data.chatbot_cache || [];
            fileManagerData.extractions_data = data.extractions_data || [];
            fileManagerData.exports = data.exports || [];
            fileManagerData.gcs_enabled = data.gcs_enabled || false;
            fileManagerData.isLoaded = true;
            fileManagerData.lastLoadTime = Date.now();
            console.log('[FileManager] Data preloaded successfully');
        }
    } catch (error) {
        console.error('[FileManager] Preload error:', error);
    } finally {
        fileManagerData.isLoading = false;
    }
}

// Check if cache is stale (older than 30 seconds)
function isFileManagerCacheStale() {
    if (!fileManagerData.isLoaded || !fileManagerData.lastLoadTime) return true;
    return (Date.now() - fileManagerData.lastLoadTime) > 30000; // 30 seconds
}

// Invalidate cache to force refresh on next load
function invalidateFileManagerCache() {
    fileManagerData.lastLoadTime = null;
    console.log('[FileManager] Cache invalidated');
}

// Initialize File Manager
function initFileManager() {
    const fileManagerBtn = document.getElementById('fileManagerBtn');
    const closeFileManagerBtn = document.getElementById('closeFileManagerBtn');
    const fileManagerModal = document.getElementById('fileManagerModal');
    const refreshFilesBtn = document.getElementById('refreshFilesBtn');
    const selectAllFilesBtn = document.getElementById('selectAllFilesBtn');
    const deselectAllFilesBtn = document.getElementById('deselectAllFilesBtn');
    const deleteSelectedBtn = document.getElementById('deleteSelectedBtn');
    const clearAllCacheBtn = document.getElementById('clearAllCacheBtn');
    const clearEverythingBtn = document.getElementById('clearEverythingBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
    
    if (fileManagerBtn) {
        fileManagerBtn.addEventListener('click', openFileManager);
    }
    
    if (closeFileManagerBtn) {
        closeFileManagerBtn.addEventListener('click', closeFileManager);
    }
    
    if (fileManagerModal) {
        fileManagerModal.addEventListener('click', (e) => {
            if (e.target === fileManagerModal) closeFileManager();
        });
    }
    
    if (refreshFilesBtn) {
        refreshFilesBtn.addEventListener('click', () => loadFileList(true)); // Force refresh
    }
    
    if (selectAllFilesBtn) {
        selectAllFilesBtn.addEventListener('click', selectAllFiles);
    }
    
    if (deselectAllFilesBtn) {
        deselectAllFilesBtn.addEventListener('click', deselectAllFiles);
    }
    
    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', deleteSelectedFiles);
    }
    
    if (clearAllCacheBtn) {
        clearAllCacheBtn.addEventListener('click', () => showConfirmDelete('cache'));
    }
    
    if (clearEverythingBtn) {
        clearEverythingBtn.addEventListener('click', () => showConfirmDelete('everything'));
    }
    
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', executeConfirmedDelete);
    }
    
    if (cancelDeleteBtn) {
        cancelDeleteBtn.addEventListener('click', closeConfirmDeleteModal);
    }
    
    // Tab switching
    document.querySelectorAll('.file-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.file-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            fileManagerData.currentTab = tab.dataset.tab;
            renderFilesTable();
        });
    });
    
    // Select all checkbox
    const selectAllCheckbox = document.getElementById('selectAllCheckbox');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                selectAllFiles();
            } else {
                deselectAllFiles();
            }
        });
    }
}

function openFileManager() {
    const modal = document.getElementById('fileManagerModal');
    if (modal) {
        modal.style.display = 'flex';
        
        // If data is already loaded, show immediately without waiting
        if (fileManagerData.isLoaded) {
            const loading = document.getElementById('fileManagerLoading');
            const tableContainer = document.getElementById('filesTableContainer');
            if (loading) loading.style.display = 'none';
            if (tableContainer) tableContainer.style.display = 'block';
            updateFileCounts();
            renderFilesTable();
            updateGCSStatus();
            
            // Refresh in background if data is stale
            if (isFileManagerCacheStale()) {
                refreshFileListInBackground();
            }
        } else {
            // First time opening - load data
            loadFileList();
        }
    }
}

function closeFileManager() {
    const modal = document.getElementById('fileManagerModal');
    if (modal) {
        modal.style.display = 'none';
    }
    selectedFiles.clear();
    updateSelectedCount();
}

async function loadFileList(forceRefresh = false) {
    const loading = document.getElementById('fileManagerLoading');
    const tableContainer = document.getElementById('filesTableContainer');
    
    // If we have cached data and it's not stale, show it immediately
    if (!forceRefresh && fileManagerData.isLoaded && !isFileManagerCacheStale()) {
        console.log('[FileManager] Using cached data');
        if (loading) loading.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
        updateFileCounts();
        renderFilesTable();
        updateGCSStatus();
        
        // Refresh in background silently
        refreshFileListInBackground();
        return;
    }
    
    // Show loading only if we don't have any data yet
    if (!fileManagerData.isLoaded) {
        if (loading) loading.style.display = 'block';
        if (tableContainer) tableContainer.style.display = 'none';
    } else {
        // We have stale data, show it but indicate refreshing
        updateFileCounts();
        renderFilesTable();
        updateGCSStatus();
        if (loading) loading.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
    }
    
    await fetchFileListFromServer();
}

async function fetchFileListFromServer() {
    const loading = document.getElementById('fileManagerLoading');
    const tableContainer = document.getElementById('filesTableContainer');
    
    fileManagerData.isLoading = true;
    
    try {
        // Load files from API
        const response = await fetch('/api/files/list');
        const result = await response.json();
        
        if (result.success) {
            const oldData = { ...fileManagerData };
            
            // Update with new data while preserving state properties
            fileManagerData.extraction_cache = result.data.extraction_cache || [];
            fileManagerData.chatbot_cache = result.data.chatbot_cache || [];
            fileManagerData.extractions_data = result.data.extractions_data || [];
            fileManagerData.exports = result.data.exports || [];
            fileManagerData.gcs_enabled = result.data.gcs_enabled || false;
            fileManagerData.extractions = result.data.extraction_records || [];
            fileManagerData.isLoaded = true;
            fileManagerData.lastLoadTime = Date.now();
            
            updateFileCounts();
            renderFilesTable();
            updateGCSStatus();
            
            console.log('[FileManager] Data loaded from server');
        } else {
            console.error('Failed to load files:', result.error);
            if (!fileManagerData.isLoaded) {
                alert('Failed to load files: ' + result.error);
            }
        }
    } catch (error) {
        console.error('Error loading files:', error);
        if (!fileManagerData.isLoaded) {
            alert('Error loading files: ' + error.message);
        }
    } finally {
        fileManagerData.isLoading = false;
        if (loading) loading.style.display = 'none';
        if (tableContainer) tableContainer.style.display = 'block';
    }
}

async function refreshFileListInBackground() {
    if (fileManagerData.isLoading) return;
    
    console.log('[FileManager] Background refresh started');
    await fetchFileListFromServer();
}

function updateFileCounts() {
    document.getElementById('extractionsCount').textContent = (fileManagerData.extractions || []).length;
    document.getElementById('extractionCacheCount').textContent = (fileManagerData.extraction_cache || []).length;
    document.getElementById('chatbotCacheCount').textContent = (fileManagerData.chatbot_cache || []).length;
    document.getElementById('exportsCount').textContent = (fileManagerData.exports || []).length;
}

function updateGCSStatus() {
    const badge = document.getElementById('gcsStatusBadge');
    if (badge) {
        if (fileManagerData.gcs_enabled) {
            badge.textContent = '☁️ GCS Connected';
            badge.style.background = '#dcfce7';
            badge.style.color = '#166534';
        } else {
            badge.textContent = '💾 Local Storage Only';
            badge.style.background = '#dbeafe';
            badge.style.color = '#1e40af';
        }
    }
}

function renderFilesTable() {
    const tbody = document.getElementById('filesTableBody');
    const noFilesMessage = document.getElementById('noFilesMessage');
    
    if (!tbody) return;
    
    tbody.innerHTML = '';
    selectedFiles.clear();
    updateSelectedCount();
    
    let files = [];
    const currentTab = fileManagerData.currentTab;
    
    if (currentTab === 'extractions') {
        files = (fileManagerData.extractions || []).map(ext => ({
            id: ext.extraction_id,
            name: `${ext.extraction_id}.json`,
            original: ext.file_name || 'Unknown',
            location: ext.location || 'local',
            size: formatFileSize(ext.size),
            modified: formatDate(ext.extracted_at || ext.uploaded_at || ext.modified),
            type: 'extraction',
            file_hash: ext.file_hash
        }));
        
        // Also add legacy extractions_data.json files for cleanup
        const legacyFiles = (fileManagerData.extractions_data || []).map(f => ({
            id: f.path,
            name: f.name,
            original: `${f.record_count || 0} records (legacy)`,
            location: f.location,
            size: formatFileSize(f.size),
            modified: formatDate(f.modified),
            type: 'legacy_extractions_data',
            file_hash: ''
        }));
        files = [...files, ...legacyFiles];
    } else if (currentTab === 'extraction_cache') {
        files = (fileManagerData.extraction_cache || []).map(f => ({
            id: f.path,
            name: f.name,
            original: f.original_filename,
            location: f.location,
            size: formatFileSize(f.size),
            modified: formatDate(f.modified),
            type: 'extraction_cache',
            file_hash: f.file_hash
        }));
    } else if (currentTab === 'chatbot_cache') {
        files = (fileManagerData.chatbot_cache || []).map(f => ({
            id: f.path,
            name: f.name,
            original: f.original_filename,
            location: f.location,
            size: formatFileSize(f.size),
            modified: formatDate(f.modified),
            type: 'chatbot_cache',
            file_hash: f.file_hash
        }));
    } else if (currentTab === 'exports') {
        files = (fileManagerData.exports || []).map(f => ({
            id: f.path,
            name: f.name,
            original: '-',
            location: f.location,
            size: formatFileSize(f.size),
            modified: formatDate(f.modified),
            type: 'export'
        }));
    }
    
    if (files.length === 0) {
        if (noFilesMessage) noFilesMessage.style.display = 'block';
        return;
    }
    
    if (noFilesMessage) noFilesMessage.style.display = 'none';
    
    files.forEach(file => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="text-align: center;">
                <input type="checkbox" class="file-checkbox" data-id="${file.id}" data-type="${file.type}" data-location="${file.location}" data-hash="${file.file_hash || ''}">
            </td>
            <td style="font-family: monospace; font-size: 0.85em; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.name}">
                ${file.name}
            </td>
            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${file.original}">
                ${file.original}
            </td>
            <td style="text-align: center;">
                <span class="location-badge location-${file.location === 'gcs' ? 'gcs' : 'local'}">
                    ${file.location === 'gcs' ? '☁️ GCS' : '💾 Local'}
                </span>
            </td>
            <td style="text-align: right; font-family: monospace; font-size: 0.85em;">${file.size}</td>
            <td style="text-align: center; font-size: 0.85em;">${file.modified}</td>
            <td style="text-align: center;">
                <button class="delete-single-btn" onclick="deleteSingleFile('${file.id}', '${file.type}', '${file.location}', '${file.file_hash || ''}')">
                    🗑️ Delete
                </button>
            </td>
        `;
        tbody.appendChild(tr);
        
        // Checkbox event
        const checkbox = tr.querySelector('.file-checkbox');
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                selectedFiles.add(JSON.stringify({
                    id: file.id,
                    type: file.type,
                    location: file.location,
                    file_hash: file.file_hash
                }));
            } else {
                selectedFiles.delete(JSON.stringify({
                    id: file.id,
                    type: file.type,
                    location: file.location,
                    file_hash: file.file_hash
                }));
            }
            updateSelectedCount();
        });
    });
}

function formatFileSize(bytes) {
    if (!bytes || bytes === '-') return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
}

function formatDate(dateStr) {
    if (!dateStr || dateStr === '-') return '-';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    } catch {
        return dateStr;
    }
}

// Delete Progress Functions
function showDeleteProgress(title = 'Deleting files...') {
    const section = document.getElementById('deleteProgressSection');
    const titleEl = document.getElementById('deleteProgressTitle');
    const progressBar = document.getElementById('deleteProgressBar');
    const progressText = document.getElementById('deleteProgressText');
    const progressPercent = document.getElementById('deleteProgressPercent');
    const progressDetails = document.getElementById('deleteProgressDetails');
    
    if (section) {
        section.style.display = 'block';
        titleEl.textContent = title;
        progressBar.style.width = '0%';
        progressText.textContent = '0 of 0 files';
        progressPercent.textContent = '0%';
        progressDetails.innerHTML = '';
    }
}

function updateDeleteProgress(current, total, currentFileName = '', status = 'deleting') {
    const progressBar = document.getElementById('deleteProgressBar');
    const progressText = document.getElementById('deleteProgressText');
    const progressPercent = document.getElementById('deleteProgressPercent');
    const progressDetails = document.getElementById('deleteProgressDetails');
    
    const percent = total > 0 ? Math.round((current / total) * 100) : 0;
    
    if (progressBar) progressBar.style.width = `${percent}%`;
    if (progressText) progressText.textContent = `${current} of ${total} files`;
    if (progressPercent) progressPercent.textContent = `${percent}%`;
    
    if (progressDetails && currentFileName) {
        const statusIcon = status === 'success' ? '✅' : status === 'error' ? '❌' : '⏳';
        const statusColor = status === 'success' ? '#059669' : status === 'error' ? '#dc2626' : '#d97706';
        progressDetails.innerHTML += `<div style="color: ${statusColor};">${statusIcon} ${currentFileName}</div>`;
        progressDetails.scrollTop = progressDetails.scrollHeight;
    }
}

function hideDeleteProgress() {
    const section = document.getElementById('deleteProgressSection');
    if (section) {
        section.style.display = 'none';
    }
}

function completeDeleteProgress(successCount, failCount) {
    const titleEl = document.getElementById('deleteProgressTitle');
    const progressBar = document.getElementById('deleteProgressBar');
    const section = document.getElementById('deleteProgressSection');
    
    if (titleEl) {
        if (failCount > 0) {
            titleEl.textContent = `⚠️ Completed with ${failCount} error(s)`;
            section.style.background = '#fef2f2';
            progressBar.style.background = '#ef4444';
        } else {
            titleEl.textContent = '✅ Delete completed!';
            section.style.background = '#dcfce7';
            progressBar.style.background = '#22c55e';
        }
    }
    
    // Auto-hide after 3 seconds
    setTimeout(() => {
        hideDeleteProgress();
        // Reset colors
        if (section) section.style.background = '#fef3c7';
        if (progressBar) progressBar.style.background = 'linear-gradient(90deg, #f59e0b, #d97706)';
    }, 3000);
}

function selectAllFiles() {
    document.querySelectorAll('.file-checkbox').forEach(cb => {
        cb.checked = true;
        const fileData = {
            id: cb.dataset.id,
            type: cb.dataset.type,
            location: cb.dataset.location,
            file_hash: cb.dataset.hash
        };
        selectedFiles.add(JSON.stringify(fileData));
    });
    updateSelectedCount();
}

function deselectAllFiles() {
    document.querySelectorAll('.file-checkbox').forEach(cb => {
        cb.checked = false;
    });
    selectedFiles.clear();
    updateSelectedCount();
}

function updateSelectedCount() {
    const countEl = document.getElementById('selectedCount');
    if (countEl) {
        countEl.textContent = selectedFiles.size;
    }
    
    const deleteBtn = document.getElementById('deleteSelectedBtn');
    if (deleteBtn) {
        deleteBtn.disabled = selectedFiles.size === 0;
    }
}

async function deleteSingleFile(id, type, location, fileHash) {
    if (!confirm('Are you sure you want to delete this file?')) return;
    
    const fileName = id.split('/').pop() || id;
    showDeleteProgress('Deleting file...');
    updateDeleteProgress(0, 1, fileName, 'deleting');
    
    try {
        let body = {};
        
        if (type === 'extraction') {
            // Delete individual extraction record and associated cache
            body.extraction_ids = [id];
            if (fileHash) {
                body.file_hashes = [fileHash];
            }
        } else if (type === 'legacy_extractions_data') {
            // Delete legacy extractions_data.json file
            body.files = [{
                path: id,
                location: location
            }];
        } else {
            body.files = [{
                path: id,
                location: location
            }];
        }
        
        const response = await fetch('/api/files/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const result = await response.json();
        
        if (result.success) {
            updateDeleteProgress(1, 1, fileName, 'success');
            completeDeleteProgress(1, 0);
            invalidateFileManagerCache();
            loadFileList(true);
        } else {
            updateDeleteProgress(1, 1, fileName, 'error');
            completeDeleteProgress(0, 1);
        }
    } catch (error) {
        console.error('Delete error:', error);
        updateDeleteProgress(1, 1, fileName, 'error');
        completeDeleteProgress(0, 1);
    }
}

async function deleteSelectedFiles() {
    if (selectedFiles.size === 0) {
        alert('No files selected');
        return;
    }
    
    if (!confirm(`Are you sure you want to delete ${selectedFiles.size} selected file(s)?`)) return;
    
    const total = selectedFiles.size;
    let current = 0;
    let successCount = 0;
    let failCount = 0;
    
    showDeleteProgress(`Deleting ${total} file(s)...`);
    
    // Convert to array for sequential processing with progress
    const filesArray = Array.from(selectedFiles).map(f => JSON.parse(f));
    
    for (const file of filesArray) {
        const fileName = file.id.split('/').pop() || file.id;
        updateDeleteProgress(current, total, fileName, 'deleting');
        
        try {
            const body = {
                files: [],
                extraction_ids: [],
                file_hashes: []
            };
            
            if (file.type === 'extraction') {
                body.extraction_ids.push(file.id);
                if (file.file_hash) {
                    body.file_hashes.push(file.file_hash);
                }
            } else {
                body.files.push({
                    path: file.id,
                    location: file.location
                });
            }
            
            const response = await fetch('/api/files/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            const result = await response.json();
            
            if (result.success) {
                successCount++;
                updateDeleteProgress(current + 1, total, fileName, 'success');
            } else {
                failCount++;
                updateDeleteProgress(current + 1, total, fileName, 'error');
            }
        } catch (error) {
            console.error('Delete error:', error);
            failCount++;
            updateDeleteProgress(current + 1, total, fileName, 'error');
        }
        
        current++;
    }
    
    completeDeleteProgress(successCount, failCount);
    selectedFiles.clear();
    invalidateFileManagerCache();
    loadFileList(true);
}

function showConfirmDelete(action) {
    pendingDeleteAction = action;
    const modal = document.getElementById('confirmDeleteModal');
    const title = document.getElementById('confirmDeleteTitle');
    const message = document.getElementById('confirmDeleteMessage');
    
    if (action === 'cache') {
        title.textContent = 'Clear All Cache?';
        message.innerHTML = 'This will delete all extraction cache and chatbot cache files from <strong>both local storage and GCS</strong>.<br><br>Extraction records will be preserved.';
    } else if (action === 'everything') {
        title.textContent = '⚠️ Clear Everything?';
        message.innerHTML = 'This will delete <strong>ALL</strong> files including:<br>• All extraction cache<br>• All chatbot cache<br>• All extraction records<br>• All exports<br><br><strong style="color: #dc2626;">This action cannot be undone!</strong>';
    }
    
    if (modal) modal.style.display = 'flex';
}

function closeConfirmDeleteModal() {
    const modal = document.getElementById('confirmDeleteModal');
    if (modal) modal.style.display = 'none';
    pendingDeleteAction = null;
}

async function executeConfirmedDelete() {
    if (!pendingDeleteAction) return;
    
    closeConfirmDeleteModal();
    
    const actionTitle = pendingDeleteAction === 'everything' ? 'Clearing all data...' : 'Clearing cache...';
    showDeleteProgress(actionTitle);
    
    // Show initial progress steps
    const steps = pendingDeleteAction === 'everything' 
        ? ['Local extraction cache', 'Local chatbot cache', 'Local extraction records', 'GCS extraction cache', 'GCS chatbot cache', 'GCS extraction records', 'Legacy data']
        : ['Local extraction cache', 'Local chatbot cache', 'GCS extraction cache', 'GCS chatbot cache'];
    
    let currentStep = 0;
    updateDeleteProgress(currentStep, steps.length, steps[0], 'deleting');
    
    try {
        const body = {
            clear_local: true,
            clear_gcs: true,
            clear_extractions_data: pendingDeleteAction === 'everything',
            clear_in_memory: pendingDeleteAction === 'everything'
        };
        
        const response = await fetch('/api/files/clear-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const result = await response.json();
        
        if (result.success) {
            const r = result.results;
            let totalDeleted = 0;
            
            // Update progress for each category
            updateDeleteProgress(1, steps.length, `Local extraction cache: ${r.local_extraction_deleted} files`, r.local_extraction_deleted > 0 ? 'success' : 'success');
            totalDeleted += r.local_extraction_deleted || 0;
            
            updateDeleteProgress(2, steps.length, `Local chatbot cache: ${r.local_chatbot_deleted} files`, r.local_chatbot_deleted > 0 ? 'success' : 'success');
            totalDeleted += r.local_chatbot_deleted || 0;
            
            if (pendingDeleteAction === 'everything') {
                updateDeleteProgress(3, steps.length, `Local extraction records: ${r.local_extraction_records_deleted || 0} files`, 'success');
                totalDeleted += r.local_extraction_records_deleted || 0;
            }
            
            if (fileManagerData.gcs_enabled) {
                const gcsStep = pendingDeleteAction === 'everything' ? 4 : 3;
                updateDeleteProgress(gcsStep, steps.length, `GCS extraction cache: ${r.gcs_extraction_deleted} files`, 'success');
                totalDeleted += r.gcs_extraction_deleted || 0;
                
                updateDeleteProgress(gcsStep + 1, steps.length, `GCS chatbot cache: ${r.gcs_chatbot_deleted} files`, 'success');
                totalDeleted += r.gcs_chatbot_deleted || 0;
                
                if (pendingDeleteAction === 'everything' && r.gcs_extraction_records_deleted > 0) {
                    updateDeleteProgress(gcsStep + 2, steps.length, `GCS extraction records: ${r.gcs_extraction_records_deleted} files`, 'success');
                    totalDeleted += r.gcs_extraction_records_deleted || 0;
                }
            }
            
            if (r.extractions_data_cleared) {
                updateDeleteProgress(steps.length, steps.length, 'Legacy extractions_data.json cleared', 'success');
            }
            
            completeDeleteProgress(totalDeleted, 0);
            invalidateFileManagerCache();
            loadFileList(true);
        } else {
            updateDeleteProgress(steps.length, steps.length, 'Operation failed', 'error');
            completeDeleteProgress(0, 1);
        }
    } catch (error) {
        console.error('Clear error:', error);
        updateDeleteProgress(steps.length, steps.length, error.message, 'error');
        completeDeleteProgress(0, 1);
    }
    
    pendingDeleteAction = null;
}

// Initialize file manager on page load
document.addEventListener('DOMContentLoaded', function() {
    initFileManager();
    
    // Preload file manager data in background after a short delay
    // This ensures the main UI loads first, then data is ready when user opens file manager
    setTimeout(() => {
        preloadFileManagerData();
    }, 1500);
});
