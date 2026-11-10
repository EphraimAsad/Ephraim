# Ephraim v0.1.0-beta.3

## Experimental agent tools

This is the next Windows beta of Ephraim, the offline-first desktop AI and document assistant.

### New in Beta 3
- **Agent tools (opt-in):** compatible GGUF chat models can request `list_documents`, `search_documents`, `read_document` and `get_document_versions` to explore approved local documents.
- **Optional web tool:** `search_public_web` requires web configuration, explicit opt-in and native confirmation showing the original question. Retrieved private passages are not forwarded to the provider.
- **Bounded access:** Five tool calls maximum per response, one web lookup, and account-scoped document permissions enforced by Ephraim.
- **Tool visibility:** Chat displays tools invoked, alongside document and web citations when available.
- **Normal non-agent RAG is unchanged** and remains available; agent mode is disabled by default.

### Included from recent betas
- Windows blank-window fix: sandbox-compatible CommonJS preload and relative renderer assets.
- Administrator-only deletion of Ephraim-managed GGUF copies, without touching the originally imported source file.
- More informative reasoning-model test errors.
- Local GGUF chat/embeddings, indexed documents, source citations, streaming and local conversation management.

### Installation
Download **Ephraim.Setup.0.1.0-beta.3.exe** and **SHA256SUMS.txt**. Verify the installer checksum, close any previous Ephraim window, then install. No GGUF model weights or credentials are bundled.

### Verification and cautions
GitHub CI checks unit tests, TypeScript, full Git-history secret detection, real chat/embedding GGUF inference, packaged Windows UI startup and native inference, plus installer construction.

**Native agent tool calling is experimental.** The actual ability of Atem and Satella GGUFs to invoke tools reliably still needs on-device validation. Model compatibility varies.

**Do not use confidential, clinical or regulated documents yet:** local SQLite data is not encrypted at rest. The unsigned Windows installer may trigger SmartScreen.

For details consult the [README](https://github.com/EphraimAsad/Ephraim#readme).
