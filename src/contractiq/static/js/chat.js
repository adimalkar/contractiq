/**
 * ContractIQ — Chat & Streaming Q&A Logic
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

  // ──── Quick prompt chips ────
  document.querySelectorAll('.chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      queryInput.value = chip.dataset.prompt;
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
    appendMessage('user', query);
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
          <strong>Analysis Error:</strong> ${err.message || 'Failed to process contract query.'}
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

  function appendMessage(role, initialHtml) {
    const row = document.createElement('div');
    row.className = `message-row ${role}`;

    const avatarIcon = role === 'user' 
      ? `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`
      : `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>`;

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
    // Format citations in text: replace [Source N] with clickable tags
    let formattedAnswer = data.answer;

    // Convert markdown bold **text** to <strong>text</strong>
    formattedAnswer = formattedAnswer.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Replace [Source N] with clickable pills
    formattedAnswer = formattedAnswer.replace(/\[Source\s+(\d+)\]/gi, (match, p1) => {
      const sourceNum = parseInt(p1);
      return `<button class="citation-badge" data-source-num="${sourceNum}">[Source ${sourceNum}]</button>`;
    });

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
        <span class="audit-tag">🛡️ ${faithScore}% Faithfulness</span>
        ${data.pii_redacted ? '<span class="audit-tag warning">🔒 PII Redacted</span>' : ''}
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
