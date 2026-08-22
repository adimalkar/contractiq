/**
 * Termnova — Document Upload and Repository Management
 */

window.loadDocumentsList = async function () {
  const tbody = document.getElementById('documents-table-body');
  const docCountPill = document.getElementById('sidebar-doc-count');

  try {
    const data = await apiRequest('/api/v1/documents');
    AppState.documents = data.documents || [];

    if (docCountPill) {
      docCountPill.textContent = data.total_count || 0;
    }

    window.renderSidebarVault(AppState.documents);

    if (!AppState.documents.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state" style="padding: 2.5rem 1rem; text-align: center;">
            <div style="font-size: 1rem; font-weight: 600; color: #fff; margin-bottom: 0.5rem;">No contracts in repository yet</div>
            <div style="font-size: 0.82rem; color: var(--text-muted); margin-bottom: 1.25rem;">
              Drag & drop a contract above, or initialize the vault with 60 authentic enterprise agreements (CUAD / SEC EDGAR).
            </div>
            <button class="btn btn-primary btn-sm" id="btn-empty-seed" onclick="window.seedRealContracts()">
              📥 Ingest 60 Real Enterprise Contracts
            </button>
          </td>
        </tr>
      `;
      return;
    }

    const formatTitle = window.formatContractTitle || ((t) => t);

    tbody.innerHTML = AppState.documents.map((doc) => {
      const statusBadgeClass = 
        doc.processing_status === 'completed' ? 'badge-success' :
        doc.processing_status === 'processing' ? 'badge-warning' : 'badge-error';

      const uploadDate = new Date(doc.created_at).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });

      const cleanTitle = formatTitle(doc.filename);

      return `
        <tr>
          <td>
            <div style="font-weight: 600; color: #fff; line-height: 1.3;">${cleanTitle}</div>
            <div style="font-size: 0.72rem; color: var(--text-subtle); font-family: var(--font-mono); margin-top: 2px;">${doc.filename}</div>
          </td>
          <td><span class="badge">${doc.file_type.toUpperCase()}</span></td>
          <td>${doc.page_count || 1}</td>
          <td><strong>${doc.chunk_count || 0}</strong></td>
          <td><span class="badge ${statusBadgeClass}">${doc.processing_status}</span></td>
          <td style="color: var(--text-muted); font-size: 0.8rem;">${uploadDate}</td>
          <td class="text-right">
            <button class="btn-icon btn-delete-doc" data-id="${doc.id}" title="Delete Document">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </td>
        </tr>
      `;
    }).join('');

    // Attach delete listeners
    document.querySelectorAll('.btn-delete-doc').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const docId = btn.dataset.id;
        if (!confirm('Are you sure you want to delete this contract and its vector chunks?')) return;

        try {
          await apiRequest(`/api/v1/documents/${docId}`, { method: 'DELETE' });
          showToast('Document deleted from knowledge base', 'success');
          window.loadDocumentsList();
        } catch (e) {
          showToast(`Delete failed: ${e.message}`, 'error');
        }
      });
    });

  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="7" class="empty-state" style="color: var(--color-error);">
          Failed to load documents: ${err.message}
        </td>
      </tr>
    `;
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const btnBrowse = document.getElementById('btn-browse-files');
  const btnRefreshDocs = document.getElementById('btn-refresh-docs');
  const progressContainer = document.getElementById('upload-progress');
  const progressFilename = document.getElementById('progress-filename');
  const progressPercent = document.getElementById('progress-percent');
  const progressBarFill = document.getElementById('progress-bar-fill');

  if (btnBrowse && fileInput) {
    btnBrowse.addEventListener('click', () => fileInput.click());
  }

  const btnSeedDocs = document.getElementById('btn-seed-contracts');

  if (btnSeedDocs) {
    btnSeedDocs.addEventListener('click', () => window.seedRealContracts());
  }

  if (btnRefreshDocs) {
    btnRefreshDocs.addEventListener('click', () => {
      window.loadDocumentsList();
      showToast('Document repository refreshed', 'info');
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  if (dropZone) {
    ['dragenter', 'dragover'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
      });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files.length) {
        handleFileUpload(e.dataTransfer.files[0]);
      }
    });

    dropZone.addEventListener('click', (e) => {
      if (e.target !== btnBrowse) {
        fileInput.click();
      }
    });
  }

  async function handleFileUpload(file) {
    progressContainer.style.display = 'block';
    progressFilename.textContent = file.name;
    progressPercent.textContent = '20%';
    progressBarFill.style.width = '20%';

    const formData = new FormData();
    formData.append('file', file);

    try {
      progressBarFill.style.width = '60%';
      progressPercent.textContent = '60% (Parsing & Embedding)...';

      const resp = await apiRequest('/api/v1/documents/upload', {
        method: 'POST',
        body: formData,
      });

      progressBarFill.style.width = '100%';
      progressPercent.textContent = '100%';
      showToast(resp.message || 'Contract uploaded and indexed!', 'success');

      setTimeout(() => {
        progressContainer.style.display = 'none';
        progressBarFill.style.width = '0%';
        window.loadDocumentsList();
      }, 800);

    } catch (err) {
      showToast(`Upload failed: ${err.message}`, 'error');
      progressContainer.style.display = 'none';
    }
  }

window.renderSidebarVault = function(docs) {
  const vaultList = document.getElementById('sidebar-vault-list');
  if (!vaultList) return;

  if (!docs || docs.length === 0) {
    vaultList.innerHTML = `
      <div style="padding: 0.5rem 0.75rem; font-size: 0.75rem; color: var(--text-muted);">
        No contracts indexed.
      </div>
    `;
    return;
  }

  const formatTitle = window.formatContractTitle || ((t) => t);

  // Update header scope text if present
  const scopeEl = document.querySelector('.header-scope, [id*="scope"]');
  if (scopeEl) {
    const iconSpan = scopeEl.querySelector('svg, span');
    const iconHtml = iconSpan ? iconSpan.outerHTML : '📁';
    scopeEl.innerHTML = `${iconHtml} Scope: All Contracts (${docs.length})`;
  }

  vaultList.innerHTML = docs.slice(0, 25).map((d) => {
    const fnLower = (d.filename || '').toLowerCase();
    let tag = 'COMMERCIAL';
    let tagClass = 'tag-commercial';

    if (fnLower.includes('msa') || fnLower.includes('master')) {
      tag = 'MSA';
      tagClass = 'tag-msa';
    } else if (fnLower.includes('sow') || fnLower.includes('statement')) {
      tag = 'SOW';
      tagClass = 'tag-sow';
    } else if (fnLower.includes('nda') || fnLower.includes('confidential')) {
      tag = 'NDA';
      tagClass = 'tag-nda';
    } else if (fnLower.includes('lease') || fnLower.includes('estate')) {
      tag = 'LEASE';
      tagClass = 'tag-lease';
    } else if (fnLower.includes('vendor') || fnLower.includes('supply') || fnLower.includes('manufacturing')) {
      tag = 'VENDOR';
      tagClass = 'tag-vendor';
    } else if (fnLower.includes('license') || fnLower.includes('software') || fnLower.includes('ip')) {
      tag = 'LICENSE';
      tagClass = 'tag-license';
    } else if (fnLower.includes('distributor') || fnLower.includes('reseller')) {
      tag = 'DISTRIB';
      tagClass = 'tag-distributor';
    } else if (fnLower.includes('service') || fnLower.includes('hosting') || fnLower.includes('maintenance')) {
      tag = 'SERVICE';
      tagClass = 'tag-service';
    } else if (fnLower.includes('affiliate') || fnLower.includes('co_branding') || fnLower.includes('partner')) {
      tag = 'PARTNER';
      tagClass = 'tag-partnership';
    }

    const cleanName = formatTitle(d.filename);

    return `
      <div class="vault-item" data-doc-id="${d.id}" data-doc="${d.filename}" title="${d.filename}">
        <span class="type-tag ${tagClass}">${tag}</span>
        <span class="vault-item-name">${cleanName}</span>
      </div>
    `;
  }).join('');

  // Attach click handler to switch to chat / ask AI about this document
  vaultList.querySelectorAll('.vault-item').forEach((item) => {
    item.addEventListener('click', () => {
      const docName = item.getAttribute('data-doc');
      const input = document.getElementById('chat-input');
      if (input) {
        input.value = `Analyze key clauses, liability limits, and termination rights in ${docName}`;
        input.focus();
      }
      if (window.switchView) {
        window.switchView('chat');
      }
    });
  });
}
window.seedRealContracts = async function () {
  const seedBtn = document.getElementById('btn-seed-contracts');
  const emptySeedBtn = document.getElementById('btn-empty-seed');
  const activeBtn = seedBtn || emptySeedBtn;

  if (activeBtn) {
    activeBtn.disabled = true;
    activeBtn.innerHTML = '⏳ Ingesting authentic contracts...';
  }
  showToast('Indexing authentic commercial contract dataset (CUAD/SEC EDGAR)...', 'info');

  try {
    const res = await apiRequest('/api/v1/documents/seed?limit=60', { method: 'POST' });
    showToast(res.message || 'Successfully seeded enterprise contracts!', 'success');
    await window.loadDocumentsList();
    if (window.loadAnalytics) window.loadAnalytics();
    if (window.loadInboxContracts) window.loadInboxContracts();
  } catch (err) {
    showToast(`Seeding failed: ${err.message}`, 'error');
  } finally {
    if (activeBtn) {
      activeBtn.disabled = false;
      activeBtn.innerHTML = '📥 Ingest 60 Real Contracts';
    }
  }
};

  // Load documents on initial start
  window.loadDocumentsList();
});
