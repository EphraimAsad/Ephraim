<div align="center">

# ✦ Ephraim

### Your documents. Your models. Your AI.

**An offline-first Windows AI assistant with local GGUF inference and document-grounded answers.**

[Releases](https://github.com/EphraimAsad/Ephraim/releases) · [Installation](#installation) · [Features](#features) · [Privacy](#privacy--security) · [Development](#development)

![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-beta-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20x64-0078D6)
![Inference](https://img.shields.io/badge/AI-local%20GGUF-5955AD)
![Cost](https://img.shields.io/badge/mandatory%20API%20cost-%C2%A30-brightgreen)

</div>

---

> [!IMPORTANT]
> **Beta software.** Ephraim is under active development. Test with non-sensitive files first. Local documents, chat history and the SQLite database are **not encrypted at rest**. Security and lab-usage validation are not complete. See [Security](#privacy--security) and [Known limitations](#known-limitations).

## What is Ephraim?

**Ephraim** is a desktop AI knowledge assistant designed to run on your own computer. Import a compatible **GGUF language model**, add documents to a knowledge library, and ask questions in a conversational interface.

Ephraim retrieves relevant excerpts from approved local documents and presents source references alongside AI responses. You can summarise entire indexed procedures, investigate a topic using optional web search, or chat offline without Ollama, Python, paid AI APIs or a cloud server.

### Example

**You:** “Summarise TP 4122, including the procedure, incubation requirements and precautions.”

**Ephraim:** Searches the approved version of TP 4122, processes its indexed sections and produces a document-grounded summary with references to indexed passages. Exact wording depends on the model and document; all outputs require human review.

## Features

| Feature | Details |
| --- | --- |
| **Local LLMs** | Administrator imports, tests and enables compatible GGUF chat models using `node-llama-cpp` / `llama.cpp` |
| **No Ollama dependency** | Local native model execution is included in the packaged application |
| **RAG knowledge library** | PDF, DOCX, XLSX, CSV, TXT and Markdown text extraction and chunking |
| **Search** | SQLite full-text retrieval; optional local embedding GGUF for hybrid semantic retrieval |
| **Evidence** | Document identifiers, versions and page references when available; open original files |
| **Summaries** | Multi-stage whole-document summarisation of named procedures |
| **Web research** | Optional Tavily search; separately labelled web sources; explicit confirmation before each query |
| **Conversation management** | Account-scoped chat history with rename and delete |
| **Responsive chat** | Streaming responses, Stop control, token limits and model selection |
| **Administration** | Local admin/user roles, model/document approval and safe deletion of Ephraim-managed GGUF copies |
| **Personal settings** | Dark, light and system appearance; response length preferences |
| **Offline by default** | No mandatory registration, cloud inference or telemetry |

**Important:** GGUF compatibility and performance depend on the model's architecture and the user's hardware. No models or private datasets are included with the installer.

## Installation

**Windows beta update:** If Beta 1 opened to a blank window, install **v0.1.0-beta.2** from [Releases](https://github.com/EphraimAsad/Ephraim/releases). It corrects the sandboxed preload bridge and adds an actual packaged-UI startup test.


### Windows (recommended for beta)

1. Open [GitHub Releases](https://github.com/EphraimAsad/Ephraim/releases) and choose the latest **pre-release**.
2. Download `Ephraim.Setup.*.exe` (an unsigned Windows x64 installer) and check the accompanying SHA-256 checksum.
3. Run the installer. Windows SmartScreen may display an unrecognised publisher warning because the app is not commercially code-signed.
4. Launch **Ephraim** and create the first administrator account with a strong password (12+ characters).
5. Open **Models**, import a chat GGUF from disk, click **Test**, then **Enable**.
6. Optionally import an embedding GGUF, test it, enable it, and build the semantic index.
7. Open **Knowledge**, import *non-confidential* documents, assign an explicit reference and select private or shared visibility.
8. Open **Chat**, choose an enabled model, and ask a question.

> **Hardware:** 64-bit Windows. A modern CPU is required; adequate memory depends on the GGUF model size and quantisation. GPU offload may help when supported. The Windows installer is intended to include the inference runtime; users should not have to install Node.js or Python.

### Try it offline

Import a chat GGUF, select it, and ask a general question. Web search remains off unless you opt in and provide an API key.

### Optional internet search

Ephraim supports Tavily through a user-provided key. A local administrator configures this key in **Settings**, where it is encrypted using OS-backed credential encryption when available.

**External search is off by default.** Each search requires a native confirmation dialog showing the **exact question** sent to Tavily. Ephraim does not intentionally send private retrieved passages, uploaded files or previous conversation history to the search provider. However, if you type private information into the question itself and approve transmission, that information will be sent.

The Tavily account and any applicable usage limits are managed independently of Ephraim. No paid service is required for local chat/RAG.

## How it works

```text
                              EPHRAIM DESKTOP
┌───────────────────────────────────────────────────────────┐
│ Electron + React interface                                │
│  Chat • Knowledge • Models • Settings                     │
├───────────────────────────────────────────────────────────┤
│ Electron main process                                      │
│  Identity & permissions • Approved GGUFs • Settings       │
│  Local SQLite FTS5 • Document versions • Source references│
├───────────────────────────────────────────────────────────┤
│ Document import ──> Extract ──> Chunk ──> Index           │
│                                     │                      │
│ User question ──> Hybrid retrieval ─┴──> GGUF LLM         │
│                                          │                 │
│                             Streamed answer + citations   │
└───────────────────────────────────────────────────────────┘
                       │ optional, explicit consent
                       ▼
                    Tavily Search
```

For document questions, Ephraim retrieves searchable chunks from approved documents and supplies them as **untrusted evidence** to the locally loaded model. For named full-document summaries, a hierarchical summarisation pipeline processes the indexed document in sections.

References identify the passages **provided to the model**. They do not guarantee every generated statement is correct. Always inspect original sources before relying on important results.

## Privacy & security

Ephraim is intended to be *offline-first and locally controlled*. Its security design includes:

- Model execution, retrieval, chat history and document indexes stay on the user's machine.
- Local user roles and account-scoped conversations.
- Admin-controlled model and document import; explicit private/shared document visibility.
- Electron renderer sandboxing, context isolation, allowlisted IPC and blocked arbitrary in-app navigation.
- Optional Tavily API key stored through Electron OS-backed encryption where available, rather than in source code.
- Opt-in outbound search with exact-question native confirmation.
- GitHub CI tests plus history-wide Gitleaks checks; no keys, user documents or GGUF weights should be committed.
- No built-in telemetry.

**Security limitations of this beta:**

- The SQLite database and document content are **not encrypted at rest**. Use OS full-disk encryption and protect user accounts.
- Text extraction and model files still require a stronger untrusted-input/parser security review.
- Uploaded scans requiring OCR are not yet supported.
- Page-level citations are available for text-extractable PDFs; DOCX, TXT and other inputs may not have reliable original pagination.
- Source references are not formal verification of model output.
- Some GGUF formats/hardware combinations may not work. Windows clean-machine and GPU verification remain necessary.
- This beta is **not validated for regulated laboratory, clinical or other safety-critical use**.

Please do not include API keys, personal records or confidential documents in issues, logs, discussions or pull requests. See [SECURITY.md](SECURITY.md).

## Development

**Stack:** Electron · React · TypeScript · Vite · `node-llama-cpp` · SQLite FTS5 · `pdf-parse` · `mammoth` · ExcelJS · electron-builder.

To develop from source:

```bash
git clone https://github.com/EphraimAsad/Ephraim.git
cd Ephraim
npm install
npm run dev
```

Requirements: Node.js 22+ and a native build environment suitable for `node-llama-cpp`. No Ollama required.

```bash
npm test                 # unit and privacy tests
npm run typecheck        # TypeScript validation
npm run security:check   # basic tracked-source secret patterns
npm run build            # compile Electron application
npm run pack:win         # create unsigned Windows installer on Windows
```

GitHub Actions also performs an actual small public GGUF inference and embedding smoke test. Windows packaging runs separately and must pass before distributing a candidate.

## Roadmap

- [x] Local GGUF import and inference
- [x] Document ingestion and local RAG
- [x] Local user accounts, permissions and chat history
- [x] Optional web search and labelled sources
- [x] Streaming and desktop settings
- [ ] Full disk/application data encryption and parser isolation
- [ ] More robust controlled-document validation and citation accuracy
- [ ] Scanned PDF OCR
- [ ] Windows code signing and auto-update after security review
- [ ] Cross-platform binary testing

## Contributing

Issues and pull requests are welcome for bugs and enhancements. Use synthetic files only; never upload actual private documents or credentials. For security issues, contact the maintainer privately rather than posting exploit data in public.

## License

**MIT** — see [LICENSE](LICENSE). Individual GGUF models and dependencies have their own licences.

---

<div align="center">

**Ephraim** · Local intelligence, grounded in your knowledge.

Built to give users control over their AI, documents and research.

</div>

## Model test troubleshooting

A GGUF can load successfully but fail to produce a final chat answer if its reasoning phase consumes the available tokens or if the chat template is incompatible. The Model **Test** action applies a bounded reasoning budget and reports the stop reason when no final answer is generated. The embedding test uses a separate model pipeline and does not confirm chat compatibility.

Administrators can delete an imported model using **Models → Delete**. Ephraim removes only its managed GGUF copy and registry record; it does not delete the original GGUF you selected during import. Removing an embedding model also invalidates stored vectors generated by that model, so rerun indexing after enabling another embedding model.

## Experimental agent tools

Select **Agent tools (local document tools)** in Chat to let compatible GGUF chat models choose between four read-only local tools: `list_documents`, `search_documents`, `read_document` and `get_document_versions`. The local account and document-approval rules are still enforced by Ephraim, not delegated to the model.

If you additionally configure Tavily and tick **Allow web tool**, the model may request `search_public_web`. Before any lookup, Ephraim asks for explicit confirmation showing the **original question verbatim**. Private retrieved documents, generated summaries and tool arguments are **never forwarded to Tavily**. Rejecting the dialog prevents the request.

Tool use is bounded (up to 5 calls, at most 1 web lookup), and the selected model must support function calling. Tool results are treated as untrusted evidence rather than commands. The app displays the tools used alongside citations and does not expose file-write, shell, code-execution or model-management capabilities to the model. Normal non-agent RAG remains available and enabled by default.
