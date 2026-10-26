# AI Code Debugger

<p align="center">
  <strong>AI-powered debugging, right inside Visual Studio Code.</strong>
</p>

<p align="center">
  Analyze errors, understand potential root causes, and explore AI-generated fixes using relevant repository context.
</p>

<p align="center">
  <a href="https://marketplace.visualstudio.com/items?itemName=shubham1shinde.ai-code-debugger">
    <img src="https://img.shields.io/visual-studio-marketplace/v/shubham1shinde.ai-code-debugger?label=VS%20Code%20Marketplace" alt="Visual Studio Marketplace Version">
  </a>
  <a href="https://marketplace.visualstudio.com/items?itemName=shubham1shinde.ai-code-debugger">
    <img src="https://img.shields.io/visual-studio-marketplace/i/shubham1shinde.ai-code-debugger?label=Installs" alt="Marketplace Installs">
  </a>
  <a href="https://github.com/shubham-1shinde/AI-Code-Debugger/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License">
  </a>
  <a href="https://github.com/shubham-1shinde/AI-Code-Debugger">
    <img src="https://img.shields.io/badge/GitHub-Repository-black?logo=github" alt="GitHub Repository">
  </a>
</p>

---

## Overview

**AI Code Debugger** is a Visual Studio Code extension designed to make debugging more context-aware and efficient.

Instead of relying only on an isolated error message, the extension can use relevant repository and code context to help investigate an issue, explain its likely root cause, and suggest possible fixes.

The goal is to help developers spend less time investigating errors and more time building reliable software.

## Features

- **Context-aware debugging** — use relevant project context to investigate errors.
- **AI-powered analysis** — obtain explanations of potential root causes.
- **Fix suggestions** — explore possible solutions and recommended code changes.
- **Evidence-based investigation** — use retrieved code and available evidence to support debugging results.
- **Verification guidance** — review suggested steps for checking a potential fix.
- **VS Code integration** — start debugging from the editor's Command Palette.
- **Developer-focused workflow** — investigate problems without leaving your development environment.

## Installation

### Install from the VS Code Marketplace

1. Open Visual Studio Code.
2. Open the Extensions view using `Ctrl + Shift + X`.
3. Search for **AI Code Debugger**.
4. Select the extension published by **Shubham Shinde**.
5. Click **Install**.

**Direct Marketplace link:** [Install AI Code Debugger](https://marketplace.visualstudio.com/items?itemName=shubham1shinde.ai-code-debugger)

### Install from a VSIX package

If you have downloaded the extension's `.vsix` file:

1. Open Visual Studio Code.
2. Open the Command Palette with `Ctrl + Shift + P`.
3. Search for `Extensions: Install from VSIX...`.
4. Select the downloaded VSIX package.

## How to Use

1. Open your project in Visual Studio Code.
2. Open the Command Palette with `Ctrl + Shift + P`.
3. Search for **AI Code Debugger: Debug**.
4. Run the command.
5. Review the returned analysis, including the potential root cause, supporting evidence, and suggested solution.
6. Apply changes carefully and run the relevant tests to verify the result.

The quality of the analysis depends on the available repository context, retrieved information, backend availability, and AI model response.

## How It Works

The extension connects the VS Code development environment to an AI-powered debugging backend.

A typical debugging workflow is:

1. **Error identification** — identify the issue being investigated.
2. **Context collection** — gather relevant available project information.
3. **Code retrieval** — retrieve code or repository context relevant to the issue.
4. **Error investigation** — analyze the error alongside the retrieved context.
5. **Root cause analysis** — determine a plausible explanation supported by available evidence.
6. **Solution generation** — present potential fixes and verification guidance.

The exact information available to the backend depends on the extension implementation and the current workspace.

## Technology Stack

| Component | Technology |
|---|---|
| Editor integration | Visual Studio Code Extension API |
| Extension language | TypeScript |
| Runtime | Node.js |
| Backend API | Python, FastAPI |
| AI capabilities | Generative AI |
| Context retrieval | Retrieval-Augmented Generation (RAG) |

## Requirements

- Visual Studio Code `1.85.0` or later.
- An internet connection to reach the configured debugging backend.
- Availability of the deployed backend service.

## Troubleshooting

**The command does not appear**

- Confirm that AI Code Debugger is installed and enabled.
- Reload VS Code using `Developer: Reload Window`.
- Open the Command Palette and search for `AI Code Debugger: Debug`.

**The request fails or times out**

- Check your internet connection.
- Confirm that the configured backend URL is correct and uses HTTPS.
- Check whether the backend service is running and responding.
- Retry after a short interval if the service or AI provider is temporarily unavailable.

**The analysis is incomplete or inaccurate**

- Ensure the relevant source files and error details are available to the debugging workflow.
- Review the retrieved context and supporting evidence when provided.
- Treat the suggested root cause as a hypothesis until verified.

## Security and Responsible Use

AI-generated output may be incorrect, incomplete, or unsuitable for your codebase.

- Review every suggested change before applying it.
- Run appropriate tests after modifying code.
- Do not submit passwords, API keys, access tokens, or other secrets.
- Avoid sending confidential source code or proprietary information unless you are authorized to do so.
- Follow your organization's policies for source-code handling and external AI services.

## Contributing

Contributions, bug reports, and suggestions are welcome.

1. Open an issue describing the problem or proposed improvement.
2. For code changes, fork the repository and create a feature branch.
3. Test your changes before submitting a pull request.

- **Source code:** [GitHub Repository](https://github.com/shubham-1shinde/AI-Code-Debugger)
- **Report a bug:** [GitHub Issues](https://github.com/shubham-1shinde/AI-Code-Debugger/issues)

## License

This project is licensed under the [MIT License](LICENSE).

## Author

**Shubham Shinde**

Computer Science undergraduate and software developer interested in developer tools, full-stack development, and AI-powered applications.

- **GitHub:** [@shubham-1shinde](https://github.com/shubham-1shinde)
- **Portfolio:** [shubhamshinde.vercel.app](https://portfolio-shubhamshinde.vercel.app)

---

<p align="center">
  <strong>Build better software. Debug with context.</strong>
</p>