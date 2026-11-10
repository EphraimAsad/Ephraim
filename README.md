# Ephraim — Offline-first desktop AI assistant

**Status:** Milestone 5 development candidate; security review and clean-machine validation still required before public release.

Ephraim is an Electron + React/TypeScript desktop RAG assistant. It runs imported GGUF chat models locally without Ollama, uses optional local embedding GGUFs, imports PDF/DOCX/XLSX/CSV/TXT/MD documents, retrieves indexed evidence, and offers opt-in external Tavily search. The chat now streams locally generated tokens, offers per-user history management and theme/response-length settings, and displays safe HTTPS web references.

## Setup for developers
Use Node.js 22+ and a Windows machine for Windows installer testing.

1. Run `npm install`.
2. Run `npm test`, `npm run typecheck`, `npm run build`, and `npm run security:check`.
3. Run `npm run dev` to start the desktop app.
4. Create the first administrator with a 12+ character password.
5. Import a GGUF, **Test** it using real local inference, then **Enable** it.
6. Import a sample procedure with reference `TP 4122`, choose shared/private.
7. Optionally import and enable a dedicated embedding GGUF, then choose **Build semantic index**.
8. Ask to summarise `TP 4122`. The app attempts to summarise every indexed section, including long documents, and exposes retrieved source labels.
9. Optional Tavily provider key is entered in Settings and stored via Electron OS-encrypted safeStorage. Internet search is off by default and asks before every request.

## Security and limitations
- Every conversation is owned by one local user. Retrieval filters by document visibility and current approval state.
- Imported documents are assigned to administrator ownership; shared documents are readable by local user accounts. Previous versions are retained as superseded and not normally retrieved.
- A new inference context is created for each generation, preventing reuse of chat context across users.
- No telemetry; no prompt or private source text is passed to an external provider unless the **literal question itself** contains it and the user consents to web search.
- Imported GGUF files stay in the app data folder. We never commit tokens, models, document content, conversation exports or databases.
- **Files and SQLite are currently plaintext at rest, not encrypted.** Use OS full-disk encryption; this release is not approved for regulated or confidential laboratory documents.
- PDF page citations use per-page extraction; DOCX/TXT references may not have reliable page numbers. Scanned PDFs need OCR (not yet implemented).
- Retrieval cites the passages given to the model; a cited passage is not proof a model's claim was correct.
- Untrusted parser files and source content still require stronger isolation and threat-model review.
- The Windows NSIS packaging includes an experimental native GGUF runtime setup. A successful CI compilation is **not** evidence of clean-machine installation, GPU support or successful real GGUF inference.

## Commands
- `npm test` — deterministic unit tests and privacy isolation tests
- `npm run typecheck` — TypeScript check
- `npm run build` — Electron bundling
- `npm run pack:win` — unsigned Windows NSIS installer
- `npm run security:check` — basic tracked-source secret pattern check (NOT historical)
- Windows PR workflow — attempts installer packaging, checks artifact existence and uploads installer for internal testing

## No-charge objective
Core offline inference needs no paid API. GitHub Actions standard hosted runners are free for public repositories within platform rules. External Tavily search is optional and subject to its provider quotas. No API key is included in CI or source code.

## Repository history
Original terminal agent archived on `archive/terminal-agent-2026-11-09`; its git history remains visible and requires a separate secrets audit. The application is MIT; third-party model weights have independent licences.

## Milestone 5 preview
- Response streaming uses only the allowlisted preload bridge and binds events to the active request ID and signed-in user.
- Each user can rename and delete their own conversations; deletion removes stored messages.
- Themes: dark, light and system. Maximum answer tokens can be configured per user.
- Tavily results are displayed as separately labelled, clickable HTTPS sources; arbitrary URL schemes and direct local addresses are blocked.
- External search remains opt-in and requires a native Electron confirmation with the exact outbound question on every request.
- Web links are **external**; opening a link leaves the offline application and may expose ordinary web-browsing data to that site.
- Chat history remains stored locally and **not encrypted at rest**. Do not use confidential laboratory or client records in this preview.

## Maintainer security note
Automated Gitleaks history checks run on pull requests. Commit author metadata is part of GitHub's public history and is not anonymised by application code. Never put keys, documents, model weights or real user details into source files, test fixtures, commit messages or CI environment variables.
