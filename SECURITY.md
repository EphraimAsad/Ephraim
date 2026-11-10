# Ephraim security policy (pre-release)

**Do not use real lab SOPs, client information, patient records or confidential files for testing.**
Do not put any API key in GitHub source, issues, commit messages, Actions variables, logs, screenshots, fixtures or PR comments.

Controls:
- Account-owned conversations; scoped message retrieval and separate inference contexts.
- Administrator import/approval for models and documents; status-aware document retrieval; opt-in shared documents.
- Electron renderer sandbox, context isolation, allowlisted IPC and blocked external navigation.
- Search disabled by default. Every external request asks the user to confirm the exact question, which is the sole submitted query. Retrieved documents are not included in Tavily payloads.
- Optional search key encrypted with Electron OS key store where available.
- Token and sensitive file patterns checked on PRs; a passing regex scan is not a comprehensive credential/PII audit.
- No telemetry, no remote inference or external CDN in production renderer.

Remaining security blockers: full history and dependency audit; robust native document parser isolation; OS-backed disk encryption setup; explicit threat modelling of local admin and untrusted users; log and crash-dump review; Windows binary validation, and formal validation for laboratory use. Local DB and documents are plaintext.

Security issues should be disclosed privately to the repository maintainer, without attaching documents, secrets, logs containing private content or credentials.

## Milestone 5 outbound-data controls
- Web search is never enabled automatically. Electron main validates the signed-in user, verifies that a credential exists, and asks for explicit consent with the exact query before making any Tavily request.
- Returned web results are untrusted evidence. They are labelled separately from local citations and only accepted as clickable links if they use HTTPS and pass URL checks. Links open outside Ephraim.
- Live GGUF text streams only to the active Electron window with an ephemeral request identifier; the renderer ignores events for other requests. On account changes or cancellation, partial results are not committed to the message history.
- Automated scans cannot prove the absence of all personal data. Public Git commit authorship metadata remains visible. A human release review is required.
