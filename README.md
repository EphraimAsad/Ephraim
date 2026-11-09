# Ephraim — Local AI Knowledge Assistant

**Status: early development / security review required before deployment.**

Ephraim is an offline-first Electron desktop application with local GGUF inference, administrator-managed models, private document search, optional Tavily web search, and source-aware answers. No Ollama, hosted AI API, or subscription is required for core chat.

## Development
- Node.js 22+, Windows recommended.
- Run npm install, then npm run dev.
- Run npm run security:check, npm test, npm run typecheck, npm run build.
- Run npm run pack:win to build an unsigned Windows NSIS installer (Windows host).
- On first launch, create the local administrator account.
- As administrator, import a GGUF chat model from your computer; test it before enabling it.
- Upload documents into the local library. Files, indexes and settings live in Electron's per-user application data folder, not in this repository.
- Add an optional Tavily key in Settings. Web search is off by default, and sends only the exact question after the user consents.

## Privacy and limitations
The desktop app has no telemetry and does not upload documents or prompts unless the user explicitly turns on web search; Tavily receives the text of the question, not private retrieved passages. A search API key is encrypted via Electron safeStorage; the app refuses weak Linux key storage. Never place real keys, model files, lab records or personal documents in source control.

Local files and the SQLite database are **not yet encrypted at rest**. Operating-system account security and disk encryption are recommended. The current implementation is an **early prototype**, not validated for regulated laboratory use. Model output is not authoritative; always verify citations and current controlled-document versions. PDF extraction does not reliably preserve page locations yet. PDF/DOCX/XLSX ingestion is not a hardened sandbox; only import trusted files during this phase.

The Windows installer and GGUF inference must be validated on a Windows machine before the first release. We do not claim these unverified builds are production-ready.

## Architecture
Electron main process: SQLite, local GGUF via node-llama-cpp, document ingestion, optional web API. Renderer: isolated React/TypeScript app with a typed allowlisted preload bridge. Browser sandbox + context isolation and no arbitrary browser navigation.

The original terminal coding agent was preserved on branch archive/terminal-agent-2026-11-09.

## License
MIT (see LICENSE). The dependencies and imported model weights may have their own terms.
