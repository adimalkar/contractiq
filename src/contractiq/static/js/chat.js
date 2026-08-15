/**
 * ContractIQ — Chat & Grounded Studio Q&A Logic
 */

document.addEventListener('DOMContentLoaded', () => {
  const chatForm = document.getElementById('chat-form');
  const queryInput = document.getElementById('query-input');
  const chatMessages = document.getElementById('chat-messages');
  const welcomeCard = document.getElementById('welcome-message');
  const charCounter = document.getElementById('char-counter');
  const btnClearChat = document.getElementById('btn-clear-chat');
  const btnSend = document.getElementById('btn-send-query');

  let isGenerating = false;

  // ──── Auto-resize and char counter ────
  queryInput.addEventListener('input', () => {
    queryInput.style.height = 'auto';
    queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + 'px';
    charCounter.textContent = `${queryInput.value.length} / 2000`;
  });

  // ──── Enter key submit (Shift+Enter for newline) ────
  queryInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event('submit'));
    }
  });

  // ──── Curated deck and prompt chip clicks ────
  document.querySelectorAll('.chip, .deck-card').forEach((chip) => {
    chip.addEventListener('click', () => {
      const prompt = chip.dataset.prompt;
      if (!prompt) return;
      queryInput.value = prompt;
      queryInput.dispatchEvent(new Event('input'));
      chatForm.dispatchEvent(new Event('submit'));
    });
  });

  // ──── Clear Chat ────
  if (btnClearChat) {
    btnClearChat.addEventListener('click', () => {
      chatMessages.innerHTML = '';
      if (welcomeCard) {
        chatMessages.appendChild(welcomeCard);
      }
      showToast('Chat history cleared', 'info');
    });
  }

  // ──── Form Submit ────
  chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const query = queryInput.value.trim();
    if (!query || isGenerating) return;

    // Remove welcome card if present
    if (welcomeCard && welcomeCard.parentElement === chatMessages) {
      welcomeCard.remove();
    }

    // Append User Message
    appendMessage('user', escapeHtml(query));
    queryInput.value = '';
    queryInput.style.height = 'auto';
    charCounter.textContent = '0 / 2000';
    setGeneratingState(true);

    // Create Assistant Message Placeholder
    const assistantBubble = appendMessage('assistant', '<div class="typing-indicator"><span></span><span></span><span></span></div>');

    try {
      const response = await apiRequest('/api/v1/query', {
        method: 'POST',
        body: JSON.stringify({ query: query, stream: false }),
      });

      renderAssistantResponse(assistantBubble, response);
    } catch (err) {
      assistantBubble.innerHTML = `
        <div style="color: var(--color-error);">
          <strong>Analysis Error:</strong> ${escapeHtml(err.message || 'Failed to process contract query.')}
        </div>
      `;
    } finally {
      setGeneratingState(false);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  });

  function setGeneratingState(generating) {
    isGenerating = generating;
    btnSend.disabled = generating;
    btnSend.style.opacity = generating ? '0.6' : '1';
  }

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function formatMarkdown(text) {
    let html = escapeHtml(text);

    // Bold **text** -> <strong>text</strong>
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Bullet lists
    html = html.replace(/^\s*[\-\*]\s+(.*)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Section headers
    html = html.replace(/^### (.*$)/gim, '<h4 style="margin: 10px 0 4px 0; color: #fff;">$1</h4>');
    html = html.replace(/^## (.*$)/gim, '<h3 style="margin: 12px 0 6px 0; color: #fff;">$1</h3>');

    // Line breaks
    html = html.replace(/\n\n/g, '<br><br>');

    // Replace [Source N] with clickable pills
    html = html.replace(/\[Source\s+(\d+)\]/gi, (match, p1) => {
      const sourceNum = parseInt(p1);
      return `<button class="citation-badge" data-source-num="${sourceNum}">[Source ${sourceNum}]</button>`;
    });

    return html;
  }

  function appendMessage(role, initialHtml) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const avatarIcon = role === 'user' 
      ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`
      : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>`;

    row.innerHTML = `
      <div class="message-avatar">${avatarIcon}</div>
      <div class="message-content">
        <div class="message-bubble">${initialHtml}</div>
      </div>
    `;

    chatMessages.appendChild(row);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return row.querySelector('.message-bubble');
  }

  function renderAssistantResponse(bubbleElement, data) {
    const formattedAnswer = formatMarkdown(data.answer);

    let citationsHtml = '';
    if (data.citations && data.citations.length > 0) {
      const cardsHtml = data.citations.map((c) => `
        <div class="citation-card" data-source-num="${c.source_number}">
          <span class="badge badge-subtle">Src ${c.source_number}</span>
          <span>${c.document_filename}</span>
          <span style="color: var(--text-subtle);">p.${c.page_number || '1'}</span>
        </div>
      `).join('');

      citationsHtml = `
        <div class="citations-panel">
          ${cardsHtml}
        </div>
      `;
    }

    const confScore = Math.round(data.confidence_score * 100);
    const faithScore = Math.round(data.faithfulness_score * 100);

    const auditHtml = `
      <div class="audit-meta-row">
        <span class="audit-tag success">⚡ ${data.latency_ms}ms</span>
        <span class="audit-tag">🎯 ${confScore}% Confidence</span>
        <span class="audit-tag">🛡️ ${faithScore}% Entailed</span>
        ${data.pii_redacted ? '<span class="audit-tag warning">🔒 PII Sanitized</span>' : ''}
        <button class="btn-icon" style="margin-left: auto; width: 24px; height: 24px;" title="Copy Answer" onclick="navigator.clipboard.writeText(\`${data.answer.replace(/`/g, '\\`')}\`); showToast('Answer copied to clipboard', 'info');">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
          </svg>
        </button>
      </div>
    `;

    bubbleElement.innerHTML = `
      <div>${formattedAnswer}</div>
      ${citationsHtml}
      ${auditHtml}
    `;

    // Attach click listeners to all citation pills in this message
    const citationsMap = {};
    if (data.citations) {
      data.citations.forEach((c) => {
        citationsMap[c.source_number] = c;
      });
    }

    bubbleElement.querySelectorAll('.citation-badge, .citation-card').forEach((el) => {
      el.addEventListener('click', () => {
        const sNum = parseInt(el.dataset.sourceNum);
        const citation = citationsMap[sNum];
        if (citation) {
          openSourceDrawer(citation);
        } else {
          showToast(`Source ${sNum} details not available in payload`, 'info');
        }
      });
    });
  }
});
