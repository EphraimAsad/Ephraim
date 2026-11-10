# Ephraim v0.2.0-beta.1

## Conversational research beta

- **Multi-turn context:** Conversation history now uses a selectable 4K, 8K, 16K or 32K token window with local rolling summaries of older turns. Context window requirements vary by model and machine.
- **Research routing:** Ordinary chat, approved local documents, public research, combined comparisons and full-document summaries are coordinated by the application. Combined local/web retrieval does not depend on a model's function-calling capabilities.
- **Mixed evidence:** Deduplicated approved local passages and independently retrieved public results are ranked, labelled and provided to the model for synthesis.
- **Consent-led external research:** Public search is disabled by default. Exact proposed queries are displayed for permission before each Tavily request. Approved public result URLs may be extracted by the provider for additional evidence.
- **Traceability:** Chat displays research mode, approximate prompt usage, public queries, tools invoked, sources and warnings for unrecognised citation labels.
- **Generic examples:** Public help text and release documentation use synthetic document references rather than any organisation-specific laboratory procedures.

## Install

Download the unsigned Windows installer for this pre-release and compare it against `SHA256SUMS.txt`. Exit an older Ephraim instance before upgrading. GGUF weights and API keys are not distributed.

## Security and limitations

Ephraim still stores local documents, chat history, summary memory and its SQLite database without application-level encryption at rest. Use operating-system full-disk encryption. **Do not use confidential, clinical or regulated materials until the security and workflow validation has been completed.**

Citation labels refer to passages provided for generation. They do not establish that a statement is entailed by a reference. Small local models can misinterpret evidence, hallucinate, exceed token budgets or fail to use tool calling. External research is optional and needs a configured Tavily account; some sites cannot be extracted. Important comparisons should be checked against source documents.

This is beta software, not a validated laboratory decision-support tool.