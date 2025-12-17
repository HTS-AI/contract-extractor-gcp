// Selected Factors JavaScript

let allDocuments = [];
let excelData = [];
let currentDocumentData = null;
let dataSource = 'json'; // 'json' or 'excel'

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadDocuments();
    loadExcelData();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    const documentSelect = document.getElementById('documentSelect');
    documentSelect.addEventListener('change', handleDocumentChange);
}

// Load all available documents
async function loadDocuments() {
    try {
        const response = await fetch('/api/json-data');
        if (!response.ok) {
            throw new Error('Failed to load documents');
        }
        
        const data = await response.json();
        allDocuments = data.extractions || [];
        
        // populateDocumentSelector will be called from mergeExcelAndJsonData after Excel loads
        // Or if Excel fails, we'll populate it here
        
        if (allDocuments.length === 0 && excelData.length === 0) {
            showEmptyState();
        }
        
    } catch (error) {
        console.error('Error loading documents:', error);
        // If JSON fails but Excel succeeds, that's okay
        if (excelData.length === 0) {
            document.getElementById('loadingIndicator').innerHTML = 
                '<p style="color: #dc3545;">Error loading documents. Please try again.</p>';
        }
    }
}

// Load Excel data
async function loadExcelData() {
    try {
        const response = await fetch('/api/excel-data');
        if (!response.ok) {
            throw new Error('Failed to load Excel data');
        }
        
        const data = await response.json();
        if (data.success && data.data) {
            excelData = data.data;
            console.log('Loaded Excel data:', excelData.length, 'rows');
            
            // Merge Excel data with JSON documents
            mergeExcelAndJsonData();
            
            // Auto-select first document if available
            if (allDocuments.length > 0 && document.getElementById('documentSelect').value === '') {
                document.getElementById('documentSelect').value = '0';
                handleDocumentChange();
            }
        } else {
            // No Excel data, just use JSON
            if (allDocuments.length > 0 && document.getElementById('documentSelect').value === '') {
                document.getElementById('documentSelect').value = '0';
                handleDocumentChange();
            }
        }
    } catch (error) {
        console.error('Error loading Excel data:', error);
        // Continue with JSON data only
        if (allDocuments.length > 0 && document.getElementById('documentSelect').value === '') {
            document.getElementById('documentSelect').value = '0';
            handleDocumentChange();
        }
    }
}

// Merge Excel data with JSON documents
function mergeExcelAndJsonData() {
    // Create a map of Excel data by document name (normalized)
    const excelMap = {};
    excelData.forEach(row => {
        const docName = (row['Document Name'] || '').trim();
        if (docName) {
            // Normalize filename for matching
            const normalizedName = docName.toLowerCase().replace(/[^a-z0-9]/g, '');
            excelMap[normalizedName] = row;
        }
    });
    
    // Merge with JSON documents
    allDocuments.forEach(doc => {
        const docName = (doc.file_name || '').trim();
        if (docName) {
            const normalizedName = docName.toLowerCase().replace(/[^a-z0-9]/g, '');
            if (excelMap[normalizedName]) {
                doc.excel_data = excelMap[normalizedName];
            }
        }
    });
    
    // Also add Excel-only entries (documents that might not have JSON)
    excelData.forEach(excelRow => {
        const docName = (excelRow['Document Name'] || '').trim();
        if (docName) {
            // Check if already in allDocuments (by normalized name)
            const normalizedName = docName.toLowerCase().replace(/[^a-z0-9]/g, '');
            const exists = allDocuments.some(doc => {
                const existingName = (doc.file_name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                return existingName === normalizedName;
            });
            
            if (!exists) {
                // Create document entry from Excel data
                allDocuments.push({
                    file_name: docName,
                    uploaded_at: '',
                    extracted_at: excelRow['Extracted At'] || '',
                    data: {},
                    excel_data: excelRow,
                    from_excel: true
                });
            }
        }
    });
    
    populateDocumentSelector();
}

// Populate document selector dropdown
function populateDocumentSelector() {
    const select = document.getElementById('documentSelect');
    select.innerHTML = '';
    
    if (allDocuments.length === 0) {
        select.innerHTML = '<option value="">No documents available</option>';
        return;
    }
    
    // Sort documents by extracted_at timestamp (newest first)
    // Documents without timestamp will be at the end
    allDocuments.sort((a, b) => {
        const dateA = a.extracted_at || a.uploaded_at || '';
        const dateB = b.extracted_at || b.uploaded_at || '';
        
        if (!dateA && !dateB) return 0;
        if (!dateA) return 1;
        if (!dateB) return -1;
        
        return dateB.localeCompare(dateA); // Descending order (newest first)
    });
    
    select.innerHTML = '<option value="">-- Select a document --</option>';
    
    allDocuments.forEach((doc, index) => {
        const option = document.createElement('option');
        option.value = index;
        const source = doc.from_excel ? ' (Excel)' : '';
        option.textContent = (doc.file_name || `Document ${index + 1}`) + source;
        select.appendChild(option);
    });
}

// Handle document selection change
function handleDocumentChange() {
    const select = document.getElementById('documentSelect');
    const selectedIndex = select.value;
    
    if (selectedIndex === '' || selectedIndex === null) {
        showEmptyState();
        return;
    }
    
    const selectedDoc = allDocuments[parseInt(selectedIndex)];
    if (!selectedDoc) {
        showEmptyState();
        return;
    }
    
    currentDocumentData = selectedDoc.data || {};
    
    // Prefer JSON data when it has references (page numbers), otherwise use Excel data
    const hasJsonReferences = currentDocumentData && currentDocumentData.references && 
                              Object.keys(currentDocumentData.references).some(key => 
                                  currentDocumentData.references[key] && 
                                  typeof currentDocumentData.references[key] === 'object' &&
                                  currentDocumentData.references[key].page
                              );
    
    if (hasJsonReferences || (!selectedDoc.excel_data && !selectedDoc.from_excel)) {
        // Use JSON data when it has page references or no Excel data is available
        dataSource = 'json';
        document.getElementById('dataSourceInfo').style.display = 'block';
        document.getElementById('dataSourceText').textContent = '📄 Data source: JSON file (with page references)';
        displayFactors(selectedDoc);
    } else if (selectedDoc.excel_data) {
        dataSource = 'excel';
        document.getElementById('dataSourceInfo').style.display = 'block';
        document.getElementById('dataSourceText').textContent = '📊 Data source: Excel file (contract_extractions.xlsx)';
        displayFactorsFromExcel(selectedDoc);
    } else {
        dataSource = 'json';
        document.getElementById('dataSourceInfo').style.display = 'block';
        document.getElementById('dataSourceText').textContent = '📄 Data source: JSON file';
        displayFactors(selectedDoc);
    }
}

// Display factors from Excel data
function displayFactorsFromExcel(doc) {
    const excelRow = doc.excel_data || {};
    const grid = document.getElementById('factorsGrid');
    grid.innerHTML = '';
    
    // Map Excel columns to factors
    const factors = [
        {
            label: 'Document Name',
            icon: '📄',
            value: excelRow['Document Name'] || doc.file_name || ''
        },
        {
            label: 'Document Type',
            icon: '📋',
            value: excelRow['Document Type'] || ''
        },
        {
            label: 'Document ID',
            icon: '🆔',
            value: excelRow['ID'] || excelRow['Document ID'] || ''
        },
        {
            label: 'Party Names',
            icon: '👥',
            value: excelRow['Party Names'] || ''
        },
        {
            label: 'Start Date',
            icon: '📅',
            value: excelRow['Start Date'] || ''
        },
        {
            label: 'Due Date',
            icon: '📅',
            value: excelRow['Due Date'] || ''
        },
        {
            label: 'Amount',
            icon: '💰',
            value: excelRow['Amount'] || ''
        },
        {
            label: 'Currency',
            icon: '💱',
            value: excelRow['Currency'] || ''
        },
        {
            label: 'Frequency',
            icon: '🔄',
            value: excelRow['Frequency'] || ''
        },
        {
            label: 'Account Type (Head)',
            icon: '📊',
            value: excelRow['Account Type (Head)'] || ''
        },
        {
            label: 'Risk Score',
            icon: '⚠️',
            value: formatRiskScoreFromExcel(excelRow['Risk Score'] || '')
        }
    ];
    
    // Create factor cards (Excel data doesn't have page references)
    factors.forEach(factor => {
        // For Excel data, we don't have page references
        factor.refKey = null; // Don't show "Source: Document" for Excel
        const card = createFactorCard(factor, null);
        grid.appendChild(card);
    });
    
    // Show content
    document.getElementById('loadingIndicator').style.display = 'none';
    document.getElementById('factorsContent').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
}

// Display factors for selected document (from JSON)
function displayFactors(doc) {
    const data = doc.data || {};
    const references = data.references || {};
    const grid = document.getElementById('factorsGrid');
    grid.innerHTML = '';
    
    // Debug: Log references
    console.log('[SELECTED FACTORS] References found:', references);
    console.log('[SELECTED FACTORS] Number of references:', Object.keys(references).length);
    
    // Define all factors with their extraction paths and reference keys
    const factors = [
        {
            label: 'Document Name',
            icon: '📄',
            value: doc.file_name || '',
            path: null, // Use document metadata
            refKey: null // No reference for file name
        },
        {
            label: 'Document Type',
            icon: '📋',
            value: getNestedValue(data, ['document_type', 'contract_type']) || '',
            path: ['document_type', 'contract_type'],
            refKey: 'document_type'
        },
        {
            label: 'Document ID',
            icon: '🆔',
            value: getDocumentId(data) || '',
            path: ['document_id', 'document_ids.invoice_id', 'document_ids.invoice_number', 'document_ids.contract_id'],
            refKey: ['document_ids_invoice_id', 'document_ids_invoice_number', 'document_ids_contract_id', 'document_ids_agreement_id', 'document_id']
        },
        {
            label: 'Party Names',
            icon: '👥',
            value: formatPartyNames(data),
            path: ['party_names', 'parties_to_agreement'],
            refKey: ['party_vendor', 'party_customer', 'party_party_1', 'party_party_2', 'party_1', 'party_2', 'party_names']
        },
        {
            label: 'Start Date',
            icon: '📅',
            value: getNestedValue(data, ['start_date', 'effective_date', 'execution_date']) || '',
            path: ['start_date', 'effective_date', 'execution_date'],
            refKey: ['start_date', 'effective_date', 'execution_date']
        },
        {
            label: 'Due Date',
            icon: '📅',
            value: getNestedValue(data, ['due_date', 'end_date']) || '',
            path: ['due_date', 'end_date'],
            refKey: ['due_date', 'end_date']
        },
        {
            label: 'Amount',
            icon: '💰',
            value: getNestedValue(data, ['amount', 'payment_terms.amount', 'contract_value']) || '',
            path: ['amount', 'payment_terms.amount', 'contract_value'],
            refKey: ['amount', 'contract_value']
        },
        {
            label: 'Currency',
            icon: '💱',
            value: getNestedValue(data, ['currency', 'payment_terms.currency']) || '',
            path: ['currency', 'payment_terms.currency'],
            refKey: 'currency'
        },
        {
            label: 'Frequency',
            icon: '🔄',
            value: getNestedValue(data, ['frequency', 'payment_terms.frequency']) || '',
            path: ['frequency', 'payment_terms.frequency'],
            refKey: 'frequency'
        },
        {
            label: 'Account Type (Head)',
            icon: '📊',
            value: getNestedValue(data, ['account_type']) || '',
            path: ['account_type'],
            refKey: null // AI-classified, not extracted from specific page
        },
        {
            label: 'Risk Score',
            icon: '⚠️',
            value: formatRiskScore(data),
            path: ['risk_score'],
            refKey: null, // Risk score is calculated, not from document
            isGenerated: true
        }
    ];
    
    // Create factor cards with page references
    factors.forEach(factor => {
        const pageInfo = getPageReference(references, factor.refKey);
        console.log(`[FACTOR] ${factor.label}: refKey=${JSON.stringify(factor.refKey)}, pageInfo=`, pageInfo);
        const card = createFactorCard(factor, pageInfo);
        grid.appendChild(card);
    });
    
    // Show content
    document.getElementById('loadingIndicator').style.display = 'none';
    document.getElementById('factorsContent').style.display = 'block';
    document.getElementById('emptyState').style.display = 'none';
}

// Get page reference from references object
function getPageReference(references, refKey) {
    if (!references || !refKey) return null;
    
    // Handle array of possible reference keys
    const keys = Array.isArray(refKey) ? refKey : [refKey];
    
    for (const key of keys) {
        const ref = references[key];
        if (ref) {
            // Handle both old string format and new object format
            if (typeof ref === 'object' && ref.page) {
                return { page: ref.page, text: ref.text || '' };
            } else if (typeof ref === 'string') {
                // Old format - just text, no page
                return { text: ref };
            }
        }
    }
    
    return null;
}

// Create a factor card with optional page reference
function createFactorCard(factor, pageInfo = null) {
    const card = document.createElement('div');
    card.className = 'factor-card';
    
    // Check if value is empty, null string, or undefined
    const isEmptyValue = !factor.value || factor.value === '' || factor.value === 'null' || factor.value === 'undefined' || factor.value === null;
    const valueClass = isEmptyValue ? 'factor-value empty' : 'factor-value';
    const displayValue = isEmptyValue ? '(Not available)' : factor.value;
    
    // Check if this is a risk score field that contains HTML
    const isRiskScore = factor.label && factor.label.toLowerCase().includes('risk score');
    const isHtmlValue = isRiskScore && typeof displayValue === 'string' && displayValue.includes('<span');
    
    // For risk score with HTML, render it; otherwise escape for security
    const valueContent = isHtmlValue ? displayValue : escapeHtml(String(displayValue));
    
    // Build page source indicator HTML - UNIVERSAL for all fields
    let sourceHtml = '';
    
    if (!isEmptyValue) {
        // Determine source type based on field
        const fieldLabel = factor.label ? factor.label.toLowerCase() : '';
        
        // Special cases that don't show page numbers
        if (fieldLabel.includes('document name')) {
            // Document Name: Source: Document (metadata, not from page)
            sourceHtml = `
                <div class="factor-source no-page">
                    <span class="source-icon">📄</span>
                    <span class="source-text">Source: Document</span>
                </div>
            `;
        } else if (fieldLabel.includes('document type')) {
            // Document Type: Source: AI generated
            sourceHtml = `
                <div class="factor-source generated">
                    <span class="source-icon">🤖</span>
                    <span class="source-text">Source: AI generated</span>
                </div>
            `;
        } else if (fieldLabel.includes('account type')) {
            // Account Type (Head): Source: AI Classified
            sourceHtml = `
                <div class="factor-source generated">
                    <span class="source-icon">🤖</span>
                    <span class="source-text">Source: AI Classified</span>
                </div>
            `;
        } else if (fieldLabel.includes('risk score')) {
            // Risk Score: Source: Calculated
            sourceHtml = `
                <div class="factor-source generated">
                    <span class="source-icon">📊</span>
                    <span class="source-text">Source: Calculated</span>
                </div>
            `;
        } else if (pageInfo && pageInfo.page) {
            // UNIVERSAL: Any field with page reference - show "Source: Page X"
            sourceHtml = `
                <div class="factor-source" title="${pageInfo.text ? escapeHtml(pageInfo.text.substring(0, 100)) + '...' : 'Source reference'}">
                    <span class="source-icon">📄</span>
                    <span class="source-text">Source: Page ${pageInfo.page}</span>
                </div>
            `;
        } else if (factor.refKey) {
            // Has refKey but no page found - show "Source: Document" as fallback
            sourceHtml = `
                <div class="factor-source no-page">
                    <span class="source-icon">📄</span>
                    <span class="source-text">Source: Document</span>
                </div>
            `;
        }
    }
    
    card.innerHTML = `
        <div class="factor-label">
            <span>${factor.icon}</span>
            <span>${factor.label}</span>
        </div>
        <div class="${valueClass}">${valueContent}</div>
        ${sourceHtml}
    `;
    
    return card;
}

// Get nested value from object using multiple possible paths
function getNestedValue(obj, paths) {
    if (!obj || typeof obj !== 'object') return '';
    
    for (const path of paths) {
        if (!path) continue;
        
        // Handle dot notation (e.g., 'payment_terms.amount')
        if (path.includes('.')) {
            const keys = path.split('.');
            let value = obj;
            for (const key of keys) {
                if (value && typeof value === 'object' && key in value) {
                    value = value[key];
                } else {
                    value = null;
                    break;
                }
            }
            if (value !== null && value !== undefined && value !== '') {
                return value;
            }
        } else {
            // Direct key access
            if (path in obj && obj[path] !== null && obj[path] !== undefined && obj[path] !== '') {
                return obj[path];
            }
        }
    }
    
    return '';
}

// Get document ID from various possible locations
function getDocumentId(data) {
    if (!data) return '';
    
    // Try direct document_id field first
    if (data.document_id) return data.document_id;
    
    // Try document_ids object
    const docIds = data.document_ids;
    if (docIds && typeof docIds === 'object') {
        return docIds.invoice_id || 
               docIds.invoice_number || 
               docIds.contract_id || 
               docIds.agreement_id || 
               docIds.lease_id || 
               docIds.nda_id || 
               docIds.bill_number || 
               docIds.document_number || 
               docIds.reference_id || 
               '';
    }
    
    // Fallback for old formats
    return data.nad_id || data.nda_id || '';
}

// Format party names from various possible structures
function formatPartyNames(data) {
    if (!data) return '';
    
    // Try party_names structure
    const partyNames = data.party_names;
    if (partyNames) {
        if (typeof partyNames === 'string') {
            return partyNames;
        }
        if (typeof partyNames === 'object') {
            const parties = [];
            if (partyNames.party_1) parties.push(partyNames.party_1);
            if (partyNames.party_2) parties.push(partyNames.party_2);
            if (partyNames.additional_parties && Array.isArray(partyNames.additional_parties)) {
                partyNames.additional_parties.forEach(p => {
                    if (typeof p === 'string') {
                        parties.push(p);
                    } else if (p && p.name) {
                        parties.push(p.name);
                    }
                });
            }
            if (parties.length > 0) {
                return parties.join(', ');
            }
        }
    }
    
    // Try parties_to_agreement structure (NDA format)
    const partiesToAgreement = data.parties_to_agreement;
    if (partiesToAgreement) {
        const parties = [];
        if (partiesToAgreement.disclosing_party_name) {
            parties.push(partiesToAgreement.disclosing_party_name);
        }
        if (partiesToAgreement.receiving_party_name) {
            parties.push(partiesToAgreement.receiving_party_name);
        }
        if (parties.length > 0) {
            return parties.join(', ');
        }
    }
    
    // Try parties structure
    const parties = data.parties;
    if (parties) {
        if (typeof parties === 'string') {
            return parties;
        }
        if (typeof parties === 'object') {
            const partyList = [];
            if (parties.party_1_name) partyList.push(parties.party_1_name);
            if (parties.party_2_name) partyList.push(parties.party_2_name);
            if (partyList.length > 0) {
                return partyList.join(', ');
            }
        }
    }
    
    return '';
}

// Format risk score from Excel (already formatted as "XX/100" or similar)
function formatRiskScoreFromExcel(riskScoreStr) {
    if (!riskScoreStr || riskScoreStr === '') return '';
    
    // Try to extract number from "XX/100" format
    const match = String(riskScoreStr).match(/(\d+)/);
    if (match) {
        const score = parseInt(match[1]);
        return formatRiskScoreValue(score);
    }
    
    return riskScoreStr;
}

// Format risk score
function formatRiskScore(data) {
    if (!data) return '';
    
    const riskScore = data.risk_score;
    if (!riskScore) return '';
    
    if (typeof riskScore === 'number') {
        return formatRiskScoreValue(riskScore);
    }
    
    if (typeof riskScore === 'object') {
        const score = riskScore.score || riskScore.value || 0;
        return formatRiskScoreValue(score);
    }
    
    if (typeof riskScore === 'string') {
        // Try to extract number from string
        const match = riskScore.match(/(\d+)/);
        if (match) {
            return formatRiskScoreValue(parseInt(match[1]));
        }
        return riskScore;
    }
    
    return '';
}

// Format risk score value with badge
function formatRiskScoreValue(score) {
    if (typeof score !== 'number') return String(score);
    
    let badgeClass = 'risk-low';
    if (score >= 60) {
        badgeClass = 'risk-high';
    } else if (score >= 30) {
        badgeClass = 'risk-medium';
    }
    
    return `<span class="risk-score-badge ${badgeClass}">${score}/100</span>`;
}

// Calculation functions removed - only original data from documents is displayed

// Show empty state
function showEmptyState() {
    document.getElementById('loadingIndicator').style.display = 'none';
    document.getElementById('factorsContent').style.display = 'none';
    document.getElementById('emptyState').style.display = 'block';
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

