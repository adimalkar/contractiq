# Termnova — Privacy Policy

**Last Updated: August 17, 2026**

Termnova ("we", "our", or "us") is dedicated to safeguarding your confidentiality, data privacy, and proprietary legal assets. This Privacy Policy explains how we collect, process, protect, and manage your data when using the Termnova platform.

---

### 1. Information We Collect
1. **Document Data**: Contract files (PDF, DOCX, TXT) and structured clauses uploaded for semantic analysis.
2. **Query & Chat History**: Prompts, redline queries, and interactive feedback submitted to the Contract Studio.
3. **Account & Access Info**: API keys, user identifiers, and authorization credentials.
4. **Telemetry & Technical Data**: System audit logs, IP addresses, latency metrics, and browser metadata (excluding document contents).

---

### 2. How We Use & Protect Your Information
* **Strictly for Serving Requests**: Your uploaded contract files and queries are processed solely to generate embeddings, retrieve relevant clauses, and stream factual answers back to your session.
* **No AI Training on Customer Data**: We do NOT use, share, or sell your uploaded contracts, queries, or redactions to train any third-party or proprietary foundation models.
* **Automated Guardrails & PII Redaction**: All AI generations are actively scanned by our built-in guardrails engine to redact Social Security Numbers, credit cards, emails, and sensitive credentials.
* **Enterprise Encryption**:
  - **In Transit**: All data transmission is protected using TLS 1.3 encryption (`HTTPS` / `WSS`).
  - **At Rest**: Document vectors and metadata are stored in isolated encrypted database partitions with TLS enforcement.

---

### 3. Data Retention & Deletion
* Users have full control to permanently delete indexed contracts, associated vector embeddings, and conversation histories at any time through the Document Vault interface or the `/api/v1/documents/{id}` endpoint.
* Once deleted, document records and vector representations are permanently purged from primary storage.

---

### 4. GDPR & CCPA Compliance Rights
Depending on your jurisdiction, you have the right to:
* Access the personal information we hold about you.
* Request deletion or rectification of your personal data.
* Restrict or object to certain processing activities.
* Export your data in a portable structured format.

---

### 5. Third-Party Infrastructure Providers
Termnova utilizes SOC-2 / ISO-27001 certified cloud infrastructure partners for hosting, vector search, and model inference:
* **Inference APIs**: OpenRouter / Anthropic / Meta / Google (stateless inference with zero-data-retention options).
* **Database & Vector Storage**: Neon Tech PostgreSQL (pgvector) with SSL encryption.
* **Caching & Rate Limiting**: Upstash Redis over TLS.

For data privacy inquiries or Data Processing Addendum (DPA) requests, contact `privacy@termnova.ai`.
