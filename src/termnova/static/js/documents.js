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

    if (!AppState.documents.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="7" class="empty-state">No contracts uploaded yet. Drag and drop a PDF/DOCX agreement above.</td>
        </tr>
      `;
      return;
    }

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

      return `
        <tr>
          <td>
            <div style="font-weight: 600; color: #fff;">${doc.filename}</div>
            <div style="font-size: 0.75rem; color: var(--text-subtle);">${doc.id}</div>
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

  // Load documents on initial start
  window.loadDocumentsList();
});
