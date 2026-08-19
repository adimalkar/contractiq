/**
 * Termnova — Main Application Orchestrator & State Store
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
  toast.innerHTML = `<span>${message}</span>`;

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

  // Update breadcrumb and header title
  const titleMap = {
    chat: {
      breadcrumb: 'Contract Studio',
      title: 'Contract Analysis & Q&A',
    },
    workspace: {
      breadcrumb: 'Team Workspace',
      title: 'Collaborative RAG & Shared Deal Rooms',
    },
    inbox: {
      breadcrumb: 'Contract Inbox',
      title: 'Automated Contract Intake & Triage Pipeline',
    },
    graph: {
      breadcrumb: 'Document Map',
      title: 'Contract Knowledge Graph & Topology',
    },
    compare: {
      breadcrumb: 'Clause Diff',
      title: 'Clause Redline & Side-by-Side Diff',
    },
    documents: {
      breadcrumb: 'Document Vault',
      title: 'Document Repository & Vector Chunks',
    },
    analytics: {
      breadcrumb: 'Observability',
      title: 'Observability & Safety Intelligence',
    },
  };

  const info = titleMap[viewName] || titleMap.chat;
  const breadcrumbEl = document.getElementById('view-breadcrumb');
  const titleEl = document.getElementById('view-title');
  if (breadcrumbEl) breadcrumbEl.textContent = info.breadcrumb;
  if (titleEl) titleEl.textContent = info.title;

  // Trigger view-specific data refresh
  if (viewName === 'workspace' && window.WorkspaceApp) {
    window.WorkspaceApp.init();
  } else if (viewName === 'inbox' && window.inboxApp) {
    window.inboxApp.loadData();
  } else if (viewName === 'graph' && window.initGraphView) {
    window.initGraphView();
  } else if (viewName === 'documents' && window.loadDocumentsList) {
    window.loadDocumentsList();
  } else if (viewName === 'analytics' && window.loadAnalyticsData) {
    window.loadAnalyticsData();
  } else if (viewName === 'compare' && window.initCompareDropdowns) {
    window.initCompareDropdowns();
  }
}

// ──── System Status Check ────
async function checkSystemHealth() {
  const label = document.getElementById('system-status-label');
  try {
    const health = await apiRequest('/health');
    if (health.status === 'healthy') {
      label.textContent = `Online • ${health.llm_provider || 'Hybrid'}`;
    } else {
      label.textContent = 'Degraded';
    }
  } catch (e) {
    if (label) label.textContent = 'pgvector • Ready';
  }
}

// ──── Fetch Initial Vault Stats ────
async function updateVaultStats() {
  try {
    const data = await apiRequest('/api/v1/documents');
    const totalDocs = data.total_count || data.total || (data.documents ? data.documents.length : 0);
    const sidebarPill = document.getElementById('sidebar-doc-count');
    const headerScope = document.getElementById('header-scope-label');
    const studioDocs = document.getElementById('studio-stat-docs');
    const studioChunks = document.getElementById('studio-stat-chunks');

    if (sidebarPill) sidebarPill.textContent = totalDocs;
    if (headerScope) headerScope.textContent = `Scope: All Contracts (${totalDocs})`;
    if (studioDocs) studioDocs.textContent = totalDocs;

    let totalChunks = 0;
    if (data.documents) {
      data.documents.forEach((d) => {
        totalChunks += d.chunk_count || 0;
      });
    }
    if (studioChunks && totalChunks > 0) studioChunks.textContent = totalChunks;
  } catch (e) {
    console.debug('Vault stats fetch deferred');
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
      updateVaultStats();
      showToast('Engine telemetry refreshed', 'info');
    });
  }

  // Vault item clicks in sidebar
  document.querySelectorAll('.vault-item').forEach((item) => {
    item.addEventListener('click', () => {
      const docName = item.dataset.doc;
      switchView('chat');
      const queryInput = document.getElementById('query-input');
      if (queryInput) {
        queryInput.value = `Analyze key clauses, liability caps, and termination terms in ${docName}`;
        queryInput.dispatchEvent(new Event('input'));
        const form = document.getElementById('chat-form');
        if (form) form.dispatchEvent(new Event('submit'));
      }
    });
  });

  // Connect WebSocket Push Notifications
  if (window.wsClient) {
    window.wsClient.connectNotifications((msg) => {
      if (msg.event === 'ingestion_progress') {
        const { filename, status } = msg.data || {};
        if (status === 'completed') {
          showToast(`Ingestion complete: ${filename}`, 'success');
          updateVaultStats();
          if (window.loadDocumentsList) window.loadDocumentsList();
        }
      }
    });
  }

  // Legal Modals handlers
  const btnDisclaimer = document.getElementById('btn-open-disclaimer');
  const btnTerms = document.getElementById('btn-open-terms');
  const btnPrivacy = document.getElementById('btn-open-privacy');

  if (btnDisclaimer) {
    btnDisclaimer.addEventListener('click', () => {
      const modal = document.getElementById('modal-disclaimer');
      if (modal) modal.style.display = 'flex';
    });
  }
  if (btnTerms) {
    btnTerms.addEventListener('click', () => {
      const modal = document.getElementById('modal-terms');
      if (modal) modal.style.display = 'flex';
    });
  }
  if (btnPrivacy) {
    btnPrivacy.addEventListener('click', () => {
      const modal = document.getElementById('modal-privacy');
      if (modal) modal.style.display = 'flex';
    });
  }

  // Close modals on clicking close buttons or backdrop
  document.querySelectorAll('.btn-close-modal').forEach((btn) => {
    btn.addEventListener('click', () => {
      const modalId = btn.dataset.close;
      if (modalId) {
        const modal = document.getElementById(modalId);
        if (modal) modal.style.display = 'none';
      }
    });
  });

  document.querySelectorAll('.modal-backdrop').forEach((backdrop) => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        backdrop.style.display = 'none';
      }
    });
  });

  // Initial health check & stats
  checkSystemHealth();
  updateVaultStats();

  // Support URL hash routing (e.g., #workspace, #graph, #compare, #documents, #analytics)
  const hash = window.location.hash.replace('#', '').toLowerCase();
  const hashViewMap = {
    workspace: 'workspace',
    team: 'workspace',
    map: 'graph',
    graph: 'graph',
    diff: 'compare',
    compare: 'compare',
    vault: 'documents',
    documents: 'documents',
    analytics: 'analytics',
    chat: 'chat',
  };
  if (hash && hashViewMap[hash]) {
    switchView(hashViewMap[hash]);
  }
});
