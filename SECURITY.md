# Security policy (pre-release)
- NEVER commit or paste API tokens, passwords, private documents, internal procedures, model weights, conversation exports, database files, screenshots of personal data, or local config.
- Use the application's Settings screen to enter an optional Tavily key. It is stored in the OS key store using Electron safeStorage; no secret is shipped in source code or Actions.
- Web search is explicit, disabled by default, and restricted to the exact user-approved query. Retrieved document content and conversation history must not be sent to a search provider.
- Only administrators import and approve GGUFs and documents. Never treat model output or document instructions as trusted application commands.
- Electron renderer has sandbox + contextIsolation; no Node integration, arbitrary IPC or remote page loading.
- Never log credentials, document bodies or prompts. Handle API failures without leaking auth headers.
- Local SQLite and copies of documents are plaintext in this prototype; configure disk encryption and access permissions. Do NOT use regulated or confidential data until reviewed.
- Report suspected vulnerabilities privately to the repository owner. Do not post credentials or sensitive document excerpts in public issues.
- Before deployment: threat modelling, native parser sandboxing, release binary verification, security scan of the full repository and history, reproducible dependencies and lockfile, code signing where applicable.
