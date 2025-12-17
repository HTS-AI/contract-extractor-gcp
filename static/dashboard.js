// Dashboard JavaScript for JSON Data Display

let allJsonData = [];
let filteredData = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    loadJsonData();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    const searchInput = document.getElementById('searchInput');
    const typeFilter = document.getElementById('typeFilter');
    const expandAll = document.getElementById('expandAll');
    const collapseAll = document.getElementById('collapseAll');
    
    searchInput.addEventListener('input', handleSearch);
    typeFilter.addEventListener('change', handleFilter);
    expandAll.addEventListener('click', () => expandCollapseAll(true));
    collapseAll.addEventListener('click', () => expandCollapseAll(false));
}

// Load JSON data from API
async function loadJsonData() {
    try {
        console.log('Loading JSON data from API...');
        const response = await fetch('/api/json-data');
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('API Error:', errorText);
            throw new Error(`Failed to load JSON data: ${response.status} ${errorText}`);
        }
        
        const data = await response.json();
        console.log('Received data:', data);
        console.log('Number of extractions:', data.extractions?.length || 0);
        
        allJsonData = data.extractions || [];
        filteredData = [...allJsonData];
        
        console.log('All JSON data:', allJsonData);
        
        updateStats();
        renderJsonData();
        
        document.getElementById('loadingIndicator').style.display = 'none';
        
        if (allJsonData.length === 0) {
            document.getElementById('emptyState').style.display = 'block';
            document.getElementById('jsonContainer').style.display = 'none';
        } else {
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('jsonContainer').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading JSON data:', error);
        document.getElementById('loadingIndicator').innerHTML = 
            `<div style="color: #dc3545; text-align: center;">
                <p><strong>Error loading data:</strong></p>
                <p>${error.message}</p>
                <p style="margin-top: 10px; font-size: 0.9em;">Please check the console for more details.</p>
            </div>`;
    }
}

// Update statistics
function updateStats() {
    const total = allJsonData.length;
    // Use document_type from extracted data (priority over contract_type)
    const nda = allJsonData.filter(item => 
        (item.data?.document_type || item.data?.contract_type || '').toUpperCase() === 'NDA'
    ).length;
    const lease = allJsonData.filter(item => 
        (item.data?.document_type || item.data?.contract_type || '').toUpperCase() === 'LEASE'
    ).length;
    const contract = allJsonData.filter(item => {
        const type = (item.data?.document_type || item.data?.contract_type || '').toUpperCase();
        return type === 'CONTRACT' || (type !== 'NDA' && type !== 'LEASE');
    }).length;
    
    document.getElementById('totalExtractions').textContent = total;
    document.getElementById('totalNDA').textContent = nda;
    document.getElementById('totalLease').textContent = lease;
    document.getElementById('totalContract').textContent = contract;
}

// Handle search
function handleSearch() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const typeFilter = document.getElementById('typeFilter').value;
    
    filteredData = allJsonData.filter(item => {
        // Type filter - use document_type from extracted data (priority over contract_type)
        const itemType = (item.data?.document_type || item.data?.contract_type || '').toUpperCase();
        if (typeFilter !== 'all') {
            const filterType = typeFilter.toUpperCase();
            
            if (filterType === 'CONTRACT') {
                // For CONTRACT filter: match items that are CONTRACT or anything that's not NDA/LEASE
                // This matches the logic used in updateStats()
                if (itemType !== 'CONTRACT' && (itemType === 'NDA' || itemType === 'LEASE')) {
                    return false;
                }
            } else {
                // For NDA and LEASE filters: exact match
                if (itemType !== filterType) {
                    return false;
                }
            }
        }
        
        // Search filter
        if (!searchTerm) return true;
        
        const jsonString = JSON.stringify(item.data || {}).toLowerCase();
        const fileName = (item.file_name || '').toLowerCase();
        
        return jsonString.includes(searchTerm) || fileName.includes(searchTerm);
    });
    
    renderJsonData();
}

// Handle filter
function handleFilter() {
    handleSearch();
}

// Render JSON data
function renderJsonData() {
    const container = document.getElementById('jsonContainer');
    container.innerHTML = '';
    
    if (filteredData.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>No data matches your filters.</p></div>';
        return;
    }
    
    filteredData.forEach((item, index) => {
        const jsonViewer = document.createElement('div');
        jsonViewer.className = 'json-viewer';
        
        // Use document_type from extracted data (this is set by the extractors: NDA, LEASE, CONTRACT)
        // Priority: document_type (from extractor) > contract_type (legacy) > UNKNOWN
        // Read document_type directly from extracted data - this is the source of truth
        let type = 'UNKNOWN';
        if (item.data) {
            // Prioritize document_type field (set by extractors: NDA, LEASE, CONTRACT)
            if (item.data.document_type) {
                type = String(item.data.document_type).toUpperCase().trim();
            } else if (item.data.contract_type) {
                type = String(item.data.contract_type).toUpperCase().trim();
            }
        }
        
        const typeBadge = getTypeBadge(type);
        
        // Format date
        let dateStr = 'Unknown date';
        if (item.extracted_at) {
            try {
                const date = new Date(item.extracted_at);
                dateStr = date.toLocaleString();
            } catch (e) {
                dateStr = item.extracted_at;
            }
        } else if (item.uploaded_at) {
            try {
                const date = new Date(item.uploaded_at);
                dateStr = date.toLocaleString();
            } catch (e) {
                dateStr = item.uploaded_at;
            }
        }
        
        jsonViewer.innerHTML = `
            <div class="json-item-header" onclick="toggleJsonItem(${index})">
                <div style="flex: 1;">
                    <div class="json-item-title">${escapeHtml(item.file_name || 'Unknown Document')}</div>
                    <div class="json-item-meta">
                        ${typeBadge}
                        <span>📅 ${dateStr}</span>
                        ${item.extraction_id ? `<span>ID: ${item.extraction_id.substring(0, 8)}...</span>` : ''}
                    </div>
                </div>
                <div style="font-size: 1.2em; margin-left: 15px;">▼</div>
            </div>
            <div class="json-content" id="jsonContent${index}">
                <div class="json-tree">${formatJson(item.data || {})}</div>
            </div>
        `;
        
        container.appendChild(jsonViewer);
    });
}

// Toggle JSON item
function toggleJsonItem(index) {
    const content = document.getElementById(`jsonContent${index}`);
    const header = content.previousElementSibling;
    
    if (content.classList.contains('active')) {
        content.classList.remove('active');
        header.classList.remove('active');
        header.querySelector('div:last-child').textContent = '▼';
    } else {
        content.classList.add('active');
        header.classList.add('active');
        header.querySelector('div:last-child').textContent = '▲';
    }
}

// Expand/Collapse all
function expandCollapseAll(expand) {
    const items = document.querySelectorAll('.json-content');
    const headers = document.querySelectorAll('.json-item-header');
    
    items.forEach((item, index) => {
        if (expand) {
            item.classList.add('active');
            headers[index].classList.add('active');
            headers[index].querySelector('div:last-child').textContent = '▲';
        } else {
            item.classList.remove('active');
            headers[index].classList.remove('active');
            headers[index].querySelector('div:last-child').textContent = '▼';
        }
    });
}

// Format JSON for display
function formatJson(obj, indent = 0) {
    const indentStr = '&nbsp;&nbsp;'.repeat(indent);
    let html = '';
    
    if (obj === null || obj === undefined) {
        return `<span class="json-null">null</span>`;
    }
    
    if (Array.isArray(obj)) {
        if (obj.length === 0) {
            return `<span class="json-null">[]</span>`;
        }
        html = '[<br>';
        obj.forEach((item, index) => {
            html += indentStr + '&nbsp;&nbsp;';
            html += formatJson(item, indent + 1);
            if (index < obj.length - 1) html += ',';
            html += '<br>';
        });
        html += indentStr + ']';
        return html;
    }
    
    if (typeof obj === 'object') {
        const keys = Object.keys(obj);
        if (keys.length === 0) {
            return `<span class="json-null">{}</span>`;
        }
        html = '{<br>';
        keys.forEach((key, index) => {
            html += indentStr + '&nbsp;&nbsp;';
            html += `<span class="json-key">"${escapeHtml(key)}"</span>: `;
            html += formatJson(obj[key], indent + 1);
            if (index < keys.length - 1) html += ',';
            html += '<br>';
        });
        html += indentStr + '}';
        return html;
    }
    
    if (typeof obj === 'string') {
        // Truncate very long strings
        let displayStr = obj;
        if (displayStr.length > 500) {
            displayStr = displayStr.substring(0, 500) + '... (truncated)';
        }
        return `<span class="json-string">"${escapeHtml(displayStr)}"</span>`;
    }
    
    if (typeof obj === 'number') {
        return `<span class="json-number">${obj}</span>`;
    }
    
    if (typeof obj === 'boolean') {
        return `<span class="json-boolean">${obj}</span>`;
    }
    
    return escapeHtml(String(obj));
}

// Escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Get type badge
function getTypeBadge(type) {
    const typeLower = type.toLowerCase().trim();
    if (typeLower === 'nda') {
        return '<span class="badge badge-nda">NDA</span>';
    } else if (typeLower === 'lease') {
        return '<span class="badge badge-lease">LEASE</span>';
    } else {
        return '<span class="badge badge-contract">CONTRACT</span>';
    }
}

