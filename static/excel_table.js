/**
 * Excel Table JavaScript
 * Handles loading and displaying Excel data in DataTables format
 */

let dataTable = null;

// Suppress DataTables error alerts - handle errors gracefully in UI instead
$.fn.dataTable.ext.errMode = 'none';

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    loadExcelData();
    
    // Handle DataTables errors gracefully
    $(document).on('error.dt', function(e, settings, techNote, message) {
        console.error('DataTables error:', message);
        showMessage('⚠️ Unable to display table. Please refresh the page or contact support.', 'error');
    });
});

/**
 * Load Excel data from API
 */
async function loadExcelData() {
    showLoading(true);
    hideMessage();
    
    try {
        console.log('Fetching Excel data from API...');
        const response = await fetch('/api/excel-data');
        const result = await response.json();
        
        console.log('API Response:', result);
        console.log('Data count:', result.data ? result.data.length : 0);
        
        if (result.success && result.data && result.data.length > 0) {
            console.log('Displaying table with', result.data.length, 'rows');
            displayTable(result.data);
            updateInfoCards(result.data);
            showMessage(`✓ Loaded ${result.data.length} extractions successfully!`, 'success');
            setTimeout(hideMessage, 3000);
        } else {
            console.log('No data found in Excel file');
            showMessage('📋 No data available yet. Upload and extract some documents to see them here!', 'info');
            displayEmptyTable();
            // Set info cards to zero
            document.getElementById('totalCount').textContent = '0';
            document.getElementById('leaseCount').textContent = '0';
            document.getElementById('ndaCount').textContent = '0';
            document.getElementById('contractCount').textContent = '0';
        }
    } catch (error) {
        console.error('Error loading Excel data:', error);
        showMessage('Failed to load Excel data: ' + error.message, 'error');
        displayEmptyTable();
    } finally {
        showLoading(false);
    }
}

/**
 * Display data in DataTable
 */
function displayTable(data) {
    console.log('displayTable called with', data.length, 'rows');
    
    // Destroy existing DataTable if it exists
    if (dataTable) {
        console.log('Destroying existing DataTable');
        dataTable.destroy();
    }
    
    // Clear existing table body
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '';
    
    // Populate table
    console.log('Populating table rows...');
    data.forEach((row, index) => {
        const tr = document.createElement('tr');
        const extractedRaw = row['Extracted At'] || '';
        const extractedOrder = Date.parse(extractedRaw) || 0;
        
        // Format each cell
        tr.innerHTML = `
            <td data-order="${extractedOrder}">${formatDateTime(extractedRaw)}</td>
            <td>${escapeHtml(row['Document Name'] || '-')}</td>
            <td style="max-width: 200px; word-wrap: break-word; font-size: 12px;">${escapeHtml(row['ID'] || '-')}</td>
            <td>${formatDocumentType(row['Document Type'])}</td>
            <td style="max-width: 150px; word-wrap: break-word;">${escapeHtml(row['Account Type (Head)'] || '-')}</td>
            <td style="max-width: 200px; word-wrap: break-word;">${escapeHtml(row['Party Names'] || '-')}</td>
            <td>${formatDate(row['Start Date'])}</td>
            <td>${formatDate(row['Due Date'])}</td>
            <td>${formatAmount(row['Amount'], row['Currency'])}</td>
            <td>${escapeHtml(row['Currency'] || '-')}</td>
            <td>${escapeHtml(row['Frequency'] || '1')}</td>
            <td>${formatRiskScore(row['Risk Score'])}</td>
        `;
        
        tbody.appendChild(tr);
    });
    
    console.log(`Table populated with ${data.length} rows`);
    
    // Initialize DataTable with advanced features
    console.log('Initializing DataTable...');
    try {
        dataTable = $('#contractsTable').DataTable({
            order: [[0, 'desc']], // Sort by Extracted At (newest first)
            pageLength: 10,
            lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, "All"]],
            dom: '<"top"Blf>rtip',  // B=buttons, l=length menu, f=filter, r=processing, t=table, i=info, p=pagination
            buttons: [
                {
                    extend: 'excel',
                    text: '📥 Export to Excel',
                    className: 'dt-button-excel'
                },
                {
                    extend: 'copy',
                    text: '📋 Copy',
                    className: 'dt-button-copy'
                }
            ],
            responsive: true,
            language: {
                search: "🔍 Search:",
                lengthMenu: "Show _MENU_ entries per page",
                info: "Showing _START_ to _END_ of _TOTAL_ extractions",
                infoEmpty: "No extractions found",
                infoFiltered: "(filtered from _MAX_ total extractions)",
                zeroRecords: "No matching extractions found",
                emptyTable: "No data available - extract some documents first!",
                paginate: {
                    first: "⏮ First",
                    last: "Last ⏭",
                    next: "Next ▶",
                    previous: "◀ Previous"
                }
            }
        });
        
        console.log('DataTable initialized successfully!');
        console.log('Page length:', dataTable.page.len());
        console.log('Total pages:', dataTable.page.info().pages);
    } catch (error) {
        console.error('Error initializing DataTable:', error);
        showMessage('⚠️ Error displaying table. Some features may not work correctly.', 'warning');
    }
}

/**
 * Display empty table
 */
function displayEmptyTable() {
    console.log('Displaying empty table');
    
    // Destroy existing DataTable if it exists
    if (dataTable) {
        try {
            dataTable.destroy();
            console.log('Destroyed existing DataTable');
        } catch (e) {
            console.error('Error destroying DataTable:', e);
        }
    }
    
    const tbody = document.getElementById('tableBody');
    tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; padding: 40px; color: #999; font-size: 16px;">📋 No data available. Extract some documents to see them here!</td></tr>';
    
    // Initialize empty DataTable with error suppression
    try {
        dataTable = $('#contractsTable').DataTable({
            searching: false,
            paging: false,
            info: false,
            ordering: false,
            language: {
                emptyTable: "No data available - extract some documents first!",
                zeroRecords: "No matching records found"
            }
        });
        console.log('Empty DataTable initialized successfully');
    } catch (e) {
        console.error('Error initializing empty DataTable:', e);
        // If DataTable fails, just leave the simple HTML message
    }
}

/**
 * Update info cards with statistics
 */
function updateInfoCards(data) {
    // Count totals
    const total = data.length;
    const leaseCount = data.filter(row => row['Document Type'] === 'LEASE').length;
    const ndaCount = data.filter(row => row['Document Type'] === 'NDA').length;
    const contractCount = data.filter(row => row['Document Type'] === 'CONTRACT').length;
    
    console.log('Updating info cards:', { total, leaseCount, ndaCount, contractCount });
    
    // Update cards
    document.getElementById('totalCount').textContent = total;
    document.getElementById('leaseCount').textContent = leaseCount;
    document.getElementById('ndaCount').textContent = ndaCount;
    document.getElementById('contractCount').textContent = contractCount;
}

/**
 * Refresh table data
 */
async function refreshTable() {
    await loadExcelData();
}

/**
 * Download Excel file
 */
async function downloadExcel() {
    try {
        showLoading(true);
        const response = await fetch('/api/excel-data');
        const result = await response.json();
        
        if (result.success) {
            // Create a link to download the actual Excel file
            const link = document.createElement('a');
            link.href = '/api/download-excel';
            link.download = 'contract_extractions.xlsx';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            
            showMessage('Excel file download started!', 'success');
            setTimeout(hideMessage, 3000);
        } else {
            showMessage('No Excel file available to download!', 'error');
        }
    } catch (error) {
        console.error('Error downloading Excel:', error);
        showMessage('Failed to download Excel file: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

/**
 * Format datetime for display in Qatar (date and time both in Asia/Qatar).
 * The stored time is already in Qatar time (UTC+3) but stored as tz-naive string.
 * We need to append timezone info so JavaScript parses it correctly.
 */
function formatDateTime(dateStr) {
    if (!dateStr || dateStr === '-') return '-';
    
    try {
        // The stored time is in format "YYYY-MM-DD HH:MM:SS" (Qatar time, tz-naive)
        // Append "+03:00" to indicate it's already in Qatar time (UTC+3)
        let dateStrWithTz = dateStr;
        
        // If it's in format "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS", append timezone
        if (dateStr.match(/^\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2}$/)) {
            // Replace space with T for ISO format, then append Qatar timezone
            dateStrWithTz = dateStr.replace(' ', 'T') + '+03:00';
        } else if (!dateStr.includes('+') && !dateStr.includes('Z')) {
            // If no timezone info, assume it's Qatar time and append +03:00
            dateStrWithTz = dateStr.replace(' ', 'T') + '+03:00';
        }
        
        const date = new Date(dateStrWithTz);
        if (isNaN(date.getTime())) {
            // Fallback: try parsing without timezone
            const fallbackDate = new Date(dateStr);
            if (isNaN(fallbackDate.getTime())) return dateStr;
            return new Intl.DateTimeFormat('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true,
                timeZone: 'Asia/Qatar'
            }).format(fallbackDate);
        }
        
        // Format in Qatar timezone (should show same time since input is already Qatar time)
        return new Intl.DateTimeFormat('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true,
            timeZone: 'Asia/Qatar'
        }).format(date);
    } catch (e) {
        return dateStr;
    }
}

/**
 * Format date for display
 */
function formatDate(dateStr) {
    if (!dateStr || dateStr === '-') return '-';
    
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    } catch (e) {
        return dateStr;
    }
}

/**
 * Format amount with currency
 */
function formatAmount(amount, currency) {
    if (!amount || amount === '-') return '-';
    
    try {
        const numAmount = parseFloat(amount.toString().replace(/,/g, ''));
        if (isNaN(numAmount)) return amount;
        
        const formatted = numAmount.toLocaleString('en-IN');
        return currency ? `${formatted}` : formatted;
    } catch (e) {
        return amount;
    }
}

/**
 * Format document type with badge
 */
function formatDocumentType(type) {
    if (!type) return '-';
    
    const typeUpper = type.toUpperCase();
    const className = `document-type-${typeUpper.toLowerCase()}`;
    
    return `<span class="${className}">${typeUpper}</span>`;
}

/**
 * Format risk score with color
 */
function formatRiskScore(score) {
    if (!score || score === '-') return '-';
    
    try {
        let numScore;
        let riskLevel;
        
        // Extract numeric score from format like "20/100 (Low)" or just "20"
        const match = score.toString().match(/(\d+)(?:\/\d+)?\s*(?:\((\w+)\))?/);
        
        if (match) {
            numScore = parseInt(match[1]);
            riskLevel = match[2]; // May be undefined if not in "score (level)" format
            
            // If level not provided, calculate from score
            if (!riskLevel) {
                if (numScore >= 80) {
                    riskLevel = 'Critical';
                } else if (numScore >= 60) {
                    riskLevel = 'High';
                } else if (numScore >= 30) {
                    riskLevel = 'Medium';
                } else {
                    riskLevel = 'Low';
                }
            }
            
            // Determine CSS class
            let className = 'risk-low';
            const levelLower = riskLevel.toLowerCase();
            if (levelLower === 'critical' || numScore >= 80) {
                className = 'risk-critical';
            } else if (levelLower === 'high' || numScore >= 60) {
                className = 'risk-high';
            } else if (levelLower === 'medium' || numScore >= 30) {
                className = 'risk-medium';
            }
            
            // Return just the label, not the number
            return `<span class="${className}">${riskLevel}</span>`;
        }
        
        // If it's already just a label (Low, Medium, High, Critical)
        if (['low', 'medium', 'high', 'critical'].includes(score.toString().toLowerCase())) {
            const level = score.toString();
            const levelLower = level.toLowerCase();
            let className = 'risk-low';
            if (levelLower === 'critical') className = 'risk-critical';
            else if (levelLower === 'high') className = 'risk-high';
            else if (levelLower === 'medium') className = 'risk-medium';
            
            return `<span class="${className}">${level.charAt(0).toUpperCase() + level.slice(1).toLowerCase()}</span>`;
        }
        
        return score;
    } catch (e) {
        return score;
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show loading overlay
 */
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    overlay.style.display = show ? 'flex' : 'none';
}

/**
 * Show message
 */
function showMessage(message, type = 'info') {
    const messageBox = document.getElementById('messageBox');
    let className = 'info-message';
    
    if (type === 'success') {
        className = 'success-message';
    } else if (type === 'error') {
        className = 'error-message';
    } else if (type === 'warning') {
        className = 'warning-message';
    } else if (type === 'info') {
        className = 'info-message';
    }
    
    messageBox.innerHTML = `<div class="${className}">${escapeHtml(message)}</div>`;
}

/**
 * Hide message
 */
function hideMessage() {
    const messageBox = document.getElementById('messageBox');
    messageBox.innerHTML = '';
}

/**
 * Open dashboard modal
 */
function openDashboard() {
    const modal = document.getElementById('dashboardModal');
    modal.classList.add('active');
    // Prevent body scroll when modal is open
    document.body.style.overflow = 'hidden';
}

/**
 * Close dashboard modal
 */
function closeDashboard() {
    const modal = document.getElementById('dashboardModal');
    modal.classList.remove('active');
    // Restore body scroll
    document.body.style.overflow = 'auto';
}

// Close modal when clicking outside
document.addEventListener('click', function(event) {
    const modal = document.getElementById('dashboardModal');
    if (event.target === modal) {
        closeDashboard();
    }
});

// Close modal with Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeDashboard();
    }
});

