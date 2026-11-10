# Ephraim v0.1.0-beta.2

## Windows blank-window hotfix

**Beta 2 fixes a packaging defect that could leave Ephraim v0.1.0-beta.1 displaying an empty application window.**

### Fixed
- Electron's preload bridge is now bundled as sandbox-compatible CommonJS (`index.cjs`) and loaded from the correct packaged path.
- Renderer JavaScript and CSS assets use file-relative paths in packaged Windows builds.
- A visible startup message replaces the formerly empty screen if the renderer fails.
- Privacy-conscious startup diagnostics for preload/renderer failures.

### New release gates
- Packaged React login interface must mount successfully in Windows CI.
- A small public GGUF must load and generate a response inside the packaged Windows application.
- Built renderer JS/CSS paths and the preload IPC bridge are verified before publishing.
- Existing unit tests, type checking, real GGUF/embedding checks and Git-history secret scanning remain required.

### Getting started
1. Download **Ephraim Setup 0.1.0-beta.2.exe** and verify its SHA-256 checksum using **SHA256SUMS.txt**.
2. Close the old Ephraim app and run the Beta 2 installer.
3. Launch Ephraim. It should display the sign-in / first-administrator setup screen.
4. Import, test and enable a compatible GGUF model.
5. Use only synthetic or non-confidential documents during beta testing.

### Privacy and limitations
No credentials or GGUF weights are bundled. The application remains offline-first and does not require Ollama.

**Local SQLite data and imported documents are not encrypted at rest.** Do not use regulated, clinical, personal or confidential documents yet. The Windows installer is unsigned and may trigger SmartScreen. Models and GPU compatibility depend on local hardware; this remains beta software.

For full instructions see [README](https://github.com/EphraimAsad/Ephraim#readme).
