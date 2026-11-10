# Ephraim v0.1.0-beta.1

**First Windows beta — local AI, local knowledge, optional web research.**

Ephraim brings together GGUF language models, private local documents and source-grounded conversations in one standalone Electron desktop application.

### What's included
- Local GGUF chat models without requiring Ollama, Python or paid AI APIs.
- Administrator-controlled import, testing and approval of chat and embedding models.
- Document import for text-extractable PDF, DOCX, XLSX, CSV, Markdown and TXT.
- Local full-text search and optional GGUF embedding hybrid retrieval.
- Hierarchical summaries of referenced documents, version-aware source snippets and page information where available.
- Separate per-user chat histories and administrative controls.
- Local token streaming, Stop button, response length preferences and light/dark themes.
- Optional Tavily search with explicit per-query permission and labelled external sources.

### Download
Choose **Ephraim Setup 0.1.0.exe** below (Windows x64, unsigned). See the corresponding **SHA256SUMS.txt** asset to verify its checksum. No GGUF model weights or API credentials are bundled.

### Getting started
1. Install Ephraim and create your administrator credentials.
2. Import a compatible GGUF file, run **Test**, then enable it.
3. Optionally import a local embedding GGUF and index your knowledge library.
4. Import a non-sensitive document with an explicit reference (such as TP 4122).
5. Select an enabled model in Chat and ask a question.
6. Configure optional web search in Settings; external queries always require consent.

### Important beta warnings
- **Not ready for confidential, clinical or regulated laboratory data.** Documents, chats and the SQLite database are not encrypted at rest.
- Untrusted-file isolation and full security validation are ongoing.
- Scanned PDF OCR and reliable pagination for non-PDF documents are not implemented.
- Model outputs may contain factual errors even when citations are present.
- The unsigned installer may show Windows SmartScreen warnings.
- This release targets Windows x64. Model/hardware compatibility varies; GPU functionality is experimental.

### Testing
Release packaging runs 20+ deterministic tests, TypeScript checking, full Git-history secret scanning, real local GGUF text and embedding smoke tests, and a packaged-Windows GGUF inference smoke test. These checks do not replace human acceptance testing on a clean user machine.

**No telemetry, paid API or external AI server is required for core use.**

See the [README](https://github.com/EphraimAsad/Ephraim#readme) for full installation, development, security and support details.
