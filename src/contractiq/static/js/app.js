/**
 * ContractIQ — Main Application Orchestrator & State Store
 */

const AppState = {
  activeView: 'chat',
  documents: [],
  activeDrawerCitation: null,
};

// ──── API Fetch Wrapper ────
async function apiRequest(endpoint, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json',
  };

  if (options.body instanceof FormData) {
    delete defaultHeaders['Content-Type'];
  }

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  try {
    const res = await fetch(endpoint, config);
    if (!res.ok) {
      const errJson = await res.json().catch(() => ({}));
      throw new Error(errJson.detail || `HTTP ${res.status}: ${res.statusText}`);
    }
    if (res.status === 204) return null;
    return await res.json();
  } catch (err) {
    console.error(`API error on ${endpoint}:`, err);
    throw err;
  }
}

// ──── Toast Notifications ────
function showToast(message, type = 'info', duration = 3500) {
  const hub = document.getElementById('toast-hub');
  if (!hub) return;

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${message}</span>
  `;

  hub.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 200ms ease';
    setTimeout(() => toast.remove(), 200);
  }, duration);
}
window.showToast = showToast;

// ──── Source Drawer Management ────
function openSourceDrawer(citation) {
  const drawer = document.getElementById('source-drawer');
  const badge = document.getElementById('drawer-source-badge');
  const docTitle = document.getElementById('drawer-doc-title');
  const pageNum = document.getElementById('drawer-page-num');
  const secHeader = document.getElementById('drawer-section-header');
  const excerptText = document.getElementById('drawer-excerpt-text');

  if (!drawer) return;

  badge.textContent = `Source ${citation.source_number || 1}`;
  docTitle.textContent = citation.document_filename || 'Contract Document';
  pageNum.textContent = citation.page_number ? `Page ${citation.page_number}` : 'Page N/A';
  secHeader.textContent = citation.section_header || 'General Section';
  excerptText.textContent = citation.excerpt || 'No chunk text snippet available.';

  drawer.classList.add('open');
}

function closeSourceDrawer() {
  const drawer = document.getElementById('source-drawer');
  if (drawer) {
    drawer.classList.remove('open');
  }
}

// ──── Navigation & View Switching ────
function switchView(viewName) {
  AppState.activeView = viewName;

  // Update nav buttons
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === viewName);
  });

  // Update view panels
  document.querySelectorAll('.view-panel').forEach((panel) => {
    panel.classList.toggle('active', panel.id === `view-${viewName}`);
  });

  // Update titles
  const titleMap = {
    chat: {
      title: 'Contract Analysis & Q&A',
      subtitle: 'Ask questions backed by citation-grounded retrieval and guardrails',
    },
    compare: {
      title: 'Clause-by-Clause Comparison & Redline Diff',
      subtitle: 'Align sections across agreements and spot financial and term changes',
    },
    documents: {
      title: 'Document Repository & Chunk Vectors',
      subtitle: 'Inspect parsed sections, token chunks, and extracted metadata',
    },
    analytics: {
      title: 'RAG Analytics & Quality Auditing',
      subtitle: 'Real-time throughput, faithfulness scores, and hallucination monitoring',
    },
  };

  const info = titleMap[viewName] || titleMap.chat;
  document.getElementById('view-title').textContent = info.title;
  document.getElementById('view-subtitle').textContent = info.subtitle;

  // Trigger view-specific data refresh
  if (viewName === 'documents' && window.loadDocumentsList) {
    window.loadDocumentsList();
  } else if (viewName === 'analytics' && window.loadAnalyticsData) {
    window.loadAnalyticsData();
  }
}

// ──── System Status Check ────
async function checkSystemHealth() {
  const label = document.getElementById('system-status-label');
  try {
    const health = await apiRequest('/health');
    if (health.status === 'healthy') {
      const provider = health.llm_provider ? (health.llm_provider.details || health.llm_provider.status || 'Active') : 'Online';
      label.textContent = `Online • ${provider}`;
    } else {
      label.textContent = 'Degraded';
    }
  } catch (e) {
    if (label) label.textContent = 'Offline / Local';
  }
}

// ──── Initialization ────
document.addEventListener('DOMContentLoaded', () => {
  // Nav clicks
  document.querySelectorAll('.nav-item').forEach((btn) => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });

  // Drawer close button
  const btnCloseDrawer = document.getElementById('btn-close-drawer');
  if (btnCloseDrawer) {
    btnCloseDrawer.addEventListener('click', closeSourceDrawer);
  }

  // Refresh status button
  const btnRefresh = document.getElementById('btn-refresh-status');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      checkSystemHealth();
      showToast('Engine status refreshed', 'info');
    });
  }

  // Connect WebSocket Push Notifications
  if (window.wsClient) {
    window.wsClient.connectNotifications((msg) => {
      if (msg.event === 'ingestion_progress') {
        const { filename, status } = msg.data || {};
        if (status === 'completed') {
          showToast(`✅ Ingestion complete: ${filename}`, 'success');
          if (window.loadDocumentsList) window.loadDocumentsList();
        }
      }
    });
  }

  // Initial health check
  checkSystemHealth();
});
