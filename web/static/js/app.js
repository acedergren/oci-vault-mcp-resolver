// MCP Gateway Web UI - Main JavaScript

// API Base URL
const API_BASE = '/api';

// State
let currentConfig = null;
let statusData = null;

// ===== Utility Functions =====

function showNotification(title, message, type = 'info') {
    const container = document.getElementById('notification-container');
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    
    const icons = {
        success: 'fa-check-circle',
        error: 'fa-exclamation-circle',
        warning: 'fa-exclamation-triangle',
        info: 'fa-info-circle'
    };
    
    notification.innerHTML = `
        <div class="notification-icon">
            <i class="fas ${icons[type]}"></i>
        </div>
        <div class="notification-content">
            <div class="notification-title">${title}</div>
            <div class="notification-message">${message}</div>
        </div>
    `;
    
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideIn 0.3s ease-out reverse';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'API request failed');
        }
        
        return data;
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

function formatTimestamp(timestamp) {
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
}

function formatAge(seconds) {
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
    return `${Math.floor(seconds / 86400)}d`;
}

// ===== Tab Navigation =====

function initTabs() {
    const navLinks = document.querySelectorAll('.nav-link');
    const tabContents = document.querySelectorAll('.tab-content');
    
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = link.dataset.tab;
            
            // Update nav links
            navLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // Update tab content
            tabContents.forEach(content => content.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            
            // Load data for specific tabs
            if (tabId === 'marketplace') {
                loadMarketplace();
            } else if (tabId === 'secrets') {
                loadSecrets();
            } else if (tabId === 'config') {
                loadConfigEditor();
            }
        });
    });
}

// ===== Dashboard Functions =====

async function loadDashboard() {
    try {
        // Load status
        statusData = await apiCall('/status');
        updateStatusCards();
        
        // Load servers
        const serversData = await apiCall('/servers');
        updateServersList(serversData.servers);
        
    } catch (error) {
        showNotification('Error', 'Failed to load dashboard: ' + error.message, 'error');
    }
}

function updateStatusCards() {
    // Docker MCP status
    const dockerCard = document.getElementById('docker-status-card');
    const dockerDot = dockerCard.querySelector('.status-dot');
    const dockerText = dockerCard.querySelector('.status-text');
    const dockerDetail = dockerCard.querySelector('.card-detail');
    
    if (statusData.docker_mcp.available) {
        dockerDot.className = 'status-dot status-active';
        dockerText.textContent = 'Connected';
        dockerDetail.textContent = statusData.docker_mcp.version || 'Available';
    } else {
        dockerDot.className = 'status-dot status-error';
        dockerText.textContent = 'Not Available';
        dockerDetail.textContent = statusData.docker_mcp.error || 'Install Docker MCP';
    }
    
    // OCI Vault status
    const ociCard = document.getElementById('oci-status-card');
    const ociDot = ociCard.querySelector('.status-dot');
    const ociText = ociCard.querySelector('.status-text');
    const ociDetail = ociCard.querySelector('.card-detail');
    
    if (statusData.oci_vault.available) {
        ociDot.className = 'status-dot status-active';
        ociText.textContent = 'Connected';
        ociDetail.textContent = statusData.oci_vault.version || 'Available';
    } else {
        ociDot.className = 'status-dot status-error';
        ociText.textContent = 'Not Configured';
        ociDetail.textContent = statusData.oci_vault.error || 'Configure OCI CLI';
    }
    
    // Cache status
    const cacheCard = document.getElementById('cache-status-card');
    const cacheDetail = cacheCard.querySelector('.card-detail');
    cacheDetail.textContent = `${statusData.cache.secret_count} secret(s) cached`;
    
    // Servers status (will be updated by updateServersList)
}

function updateServersList(servers) {
    const serversList = document.getElementById('servers-list');
    const serversCard = document.getElementById('servers-status-card');
    const serversText = serversCard.querySelector('.status-text');
    const serversDetail = serversCard.querySelector('.card-detail');
    
    if (servers.length === 0) {
        serversList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-server"></i>
                <p>No servers configured yet</p>
                <button class="btn btn-primary" onclick="document.querySelector('[data-tab=marketplace]').click()">
                    Browse Marketplace
                </button>
            </div>
        `;
        serversText.textContent = '0 configured';
        serversDetail.textContent = 'Add servers from marketplace';
        return;
    }
    
    serversText.textContent = `${servers.length} configured`;
    serversDetail.textContent = 'View all servers';
    
    serversList.innerHTML = servers.map(server => `
        <div class="server-item">
            <div class="server-icon">
                <i class="fas fa-server"></i>
            </div>
            <div class="server-info">
                <h3>${server.name}</h3>
                <p>${server.description || 'MCP Server'}</p>
                ${server.category ? `<span class="server-badge">${server.category}</span>` : ''}
            </div>
            <div>
                <button class="btn btn-sm btn-outline" onclick="viewServer('${server.name}')">
                    <i class="fas fa-eye"></i> View
                </button>
            </div>
        </div>
    `).join('');
}

// ===== Marketplace Functions =====

async function loadMarketplace() {
    try {
        const data = await apiCall('/catalog');
        renderMarketplace(data.servers);
        setupMarketplaceFilters(data.categories);
    } catch (error) {
        showNotification('Error', 'Failed to load marketplace: ' + error.message, 'error');
    }
}

function setupMarketplaceFilters(categories) {
    const filterBtns = document.querySelectorAll('.filter-btn');
    
    filterBtns.forEach(btn => {
        btn.addEventListener('click', async () => {
            filterBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const category = btn.dataset.category;
            const endpoint = category === 'all' ? '/catalog' : `/catalog?category=${category}`;
            
            try {
                const data = await apiCall(endpoint);
                renderMarketplace(data.servers);
            } catch (error) {
                showNotification('Error', 'Failed to filter marketplace', 'error');
            }
        });
    });
}

function renderMarketplace(servers) {
    const grid = document.getElementById('marketplace-grid');
    
    grid.innerHTML = servers.map(server => `
        <div class="marketplace-card" onclick="showServerDetails('${server.id}')">
            <div class="marketplace-card-header">
                <div class="marketplace-card-icon">
                    <i class="fas fa-${getServerIcon(server.category)}"></i>
                </div>
                <div class="marketplace-card-title">
                    <h3>${server.name}</h3>
                    <span class="marketplace-card-category">${server.category}</span>
                </div>
            </div>
            <p class="marketplace-card-description">${server.description}</p>
            <div class="marketplace-card-footer">
                <div class="marketplace-card-tags">
                    ${server.requires_secrets ? '<span class="tag"><i class="fas fa-key"></i> Secrets</span>' : ''}
                    <span class="tag"><i class="fas fa-docker"></i> Docker</span>
                </div>
            </div>
        </div>
    `).join('');
}

function getServerIcon(category) {
    const icons = {
        'Core': 'layer-group',
        'Development': 'code',
        'Database': 'database',
        'Monitoring': 'chart-line',
        'Communication': 'comments',
        'Automation': 'robot'
    };
    return icons[category] || 'server';
}

async function showServerDetails(serverId) {
    try {
        const server = await apiCall(`/catalog/${serverId}`);
        
        const modalBody = document.getElementById('modal-body');
        modalBody.innerHTML = `
            <div style="margin-bottom: 1rem;">
                <h3 style="margin-bottom: 0.5rem;">${server.name}</h3>
                <span class="marketplace-card-category">${server.category}</span>
            </div>
            
            <p style="margin-bottom: 1rem; color: var(--text-secondary);">${server.description}</p>
            
            <div style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--border-radius-sm); margin-bottom: 1rem;">
                <h4 style="margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 600;">Docker Image</h4>
                <code style="font-family: var(--font-mono); font-size: 0.875rem;">${server.image}</code>
            </div>
            
            ${server.requires_secrets ? `
                <div style="background: #fef3c7; border-left: 4px solid var(--warning-color); padding: 1rem; border-radius: var(--border-radius-sm); margin-bottom: 1rem;">
                    <h4 style="margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 600;">
                        <i class="fas fa-key"></i> Required Secrets
                    </h4>
                    <ul style="margin: 0; padding-left: 1.5rem;">
                        ${server.requires_secrets.map(s => `<li>${s}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
            
            <div style="background: var(--bg-secondary); padding: 1rem; border-radius: var(--border-radius-sm);">
                <h4 style="margin-bottom: 0.5rem; font-size: 0.875rem; font-weight: 600;">Configuration Template</h4>
                <pre style="font-family: var(--font-mono); font-size: 0.8125rem; overflow-x: auto;">${JSON.stringify(server.config_template, null, 2)}</pre>
            </div>
        `;
        
        document.getElementById('modal-title').textContent = `Install ${server.name}`;
        const actionBtn = document.getElementById('modal-action-btn');
        actionBtn.textContent = 'Add to Configuration';
        actionBtn.onclick = () => installServer(server);
        
        openModal();
    } catch (error) {
        showNotification('Error', 'Failed to load server details', 'error');
    }
}

function installServer(server) {
    closeModal();
    showNotification('Info', `Adding ${server.name} to configuration. Please configure secrets in the Configuration tab.`, 'info');
    
    // Switch to config tab
    setTimeout(() => {
        document.querySelector('[data-tab="config"]').click();
    }, 500);
}

// ===== Secrets Functions =====

async function loadSecrets() {
    try {
        const data = await apiCall('/secrets');
        renderSecretsTable(data.secrets);
    } catch (error) {
        showNotification('Error', 'Failed to load secrets: ' + error.message, 'error');
    }
}

function renderSecretsTable(secrets) {
    const tbody = document.querySelector('#secrets-table tbody');
    const emptyState = document.getElementById('secrets-empty');
    const table = document.getElementById('secrets-table');
    
    if (secrets.length === 0) {
        table.style.display = 'none';
        emptyState.style.display = 'block';
        return;
    }
    
    table.style.display = 'table';
    emptyState.style.display = 'none';
    
    tbody.innerHTML = secrets.map(secret => {
        const isStale = secret.age_seconds > 3600; // 1 hour
        const statusClass = isStale ? 'warning' : 'success';
        const statusText = isStale ? 'Stale' : 'Fresh';
        
        return `
            <tr>
                <td><code style="font-family: var(--font-mono); font-size: 0.8125rem;">${secret.cache_key}</code></td>
                <td>${formatTimestamp(secret.cached_at)}</td>
                <td>${formatAge(secret.age_seconds)}</td>
                <td>
                    <span class="tag" style="background: var(--${statusClass}-color); color: white;">
                        ${statusText}
                    </span>
                </td>
            </tr>
        `;
    }).join('');
}

// ===== Configuration Functions =====

async function loadConfigEditor() {
    try {
        const config = await apiCall('/config');
        currentConfig = config;
        
        const editor = document.getElementById('config-editor');
        editor.value = jsyaml.dump(config);
    } catch (error) {
        showNotification('Error', 'Failed to load configuration: ' + error.message, 'error');
    }
}

async function saveConfig() {
    try {
        const editor = document.getElementById('config-editor');
        const config = jsyaml.load(editor.value);
        
        await apiCall('/config', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        
        showNotification('Success', 'Configuration saved successfully', 'success');
        currentConfig = config;
    } catch (error) {
        showNotification('Error', 'Failed to save configuration: ' + error.message, 'error');
    }
}

async function resolveAndSave() {
    try {
        const editor = document.getElementById('config-editor');
        const config = jsyaml.load(editor.value);
        
        showNotification('Info', 'Resolving OCI Vault secrets...', 'info');
        
        const resolved = await apiCall('/config/resolve', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        
        await apiCall('/config', {
            method: 'POST',
            body: JSON.stringify(resolved.config)
        });
        
        showNotification('Success', 'Secrets resolved and configuration saved', 'success');
        editor.value = jsyaml.dump(resolved.config);
        currentConfig = resolved.config;
    } catch (error) {
        showNotification('Error', 'Failed to resolve and save: ' + error.message, 'error');
    }
}

// ===== Action Functions =====

async function resolveSecrets() {
    try {
        showNotification('Info', 'Resolving OCI Vault secrets...', 'info');
        
        const config = await apiCall('/config');
        const resolved = await apiCall('/config/resolve', {
            method: 'POST',
            body: JSON.stringify(config)
        });
        
        await apiCall('/config', {
            method: 'POST',
            body: JSON.stringify(resolved.config)
        });
        
        showNotification('Success', 'Secrets resolved successfully', 'success');
        loadDashboard();
    } catch (error) {
        showNotification('Error', 'Failed to resolve secrets: ' + error.message, 'error');
    }
}

async function clearCache() {
    if (!confirm('Are you sure you want to clear all cached secrets?')) {
        return;
    }
    
    try {
        await apiCall('/secrets/clear', { method: 'POST' });
        showNotification('Success', 'Cache cleared successfully', 'success');
        loadDashboard();
    } catch (error) {
        showNotification('Error', 'Failed to clear cache: ' + error.message, 'error');
    }
}

async function restartGateway() {
    if (!confirm('Are you sure you want to restart the MCP Gateway?')) {
        return;
    }
    
    try {
        await apiCall('/gateway/restart', { method: 'POST' });
        showNotification('Success', 'Gateway restarted successfully', 'success');
    } catch (error) {
        showNotification('Error', 'Failed to restart gateway: ' + error.message, 'error');
    }
}

// ===== Modal Functions =====

function openModal() {
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

// ===== Event Listeners =====

document.addEventListener('DOMContentLoaded', () => {
    // Initialize tabs
    initTabs();
    
    // Load dashboard
    loadDashboard();
    
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', loadDashboard);
    
    // Quick actions
    document.getElementById('resolve-secrets-btn').addEventListener('click', resolveSecrets);
    document.getElementById('clear-cache-btn').addEventListener('click', clearCache);
    document.getElementById('restart-gateway-btn').addEventListener('click', restartGateway);
    
    // Secrets actions
    document.getElementById('clear-all-cache-btn').addEventListener('click', clearCache);
    
    // Config actions
    document.getElementById('load-config-btn').addEventListener('click', loadConfigEditor);
    document.getElementById('save-config-btn').addEventListener('click', saveConfig);
    document.getElementById('resolve-and-save-btn').addEventListener('click', resolveAndSave);
    
    // Close modal on overlay click
    document.getElementById('modal-overlay').addEventListener('click', (e) => {
        if (e.target.id === 'modal-overlay') {
            closeModal();
        }
    });
});

// Load js-yaml from CDN for YAML parsing
const script = document.createElement('script');
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js';
document.head.appendChild(script);
