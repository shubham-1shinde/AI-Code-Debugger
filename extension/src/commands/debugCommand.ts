import * as vscode from "vscode";
import { getWorkspaceInfo } from "../services/workspaceService";
import { getActiveEditorContext } from "../services/editorService";
import { getDiagnostics } from "../services/diagnosticService";
import { getTerminalLogs } from "../services/terminalService";
import { sendDebugRequest, DebugResult } from "../services/backendService";


export async function runDebugCommand() {

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: "AI Code Debugger",
                cancellable: false
            },
            async progress => {
                progress.report({
                    message: "Collecting debugging context..."
                });
                const workspace = await getWorkspaceInfo();
                const editor = getActiveEditorContext();
                const diagnostics = getDiagnostics();
                const terminalLogs = getTerminalLogs();
                if (!terminalLogs.trim()) {
                    vscode.window.showWarningMessage("No terminal output captured yet.");
                }
                const errorMessage = terminalLogs;
                progress.report({
                    message: "Sending data to AI debugger..."
                });
                const result = await sendDebugRequest({
                    repo: workspace.repo,
                    branch: workspace.branch,
                    errorMessage,
                    terminalLogs,
                    workspacePath: workspace.workspacePath,
                    activeFile: editor.activeFile,
                    activeCode: editor.activeCode,
                    diagnostics
                });

                progress.report({
                    message: "Debug analysis completed."
                });

                if (!result.success) {
                    throw new Error(result.detail || "Debugger failed.");
                }

                if (!result.answer) {
                    throw new Error(
                        "Backend returned no debugging result."
                    );
                }

                showDebugResult(result.answer);
            }
        );

    } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`AI Debugger: ${message}`);
    }
}


function showDebugResult(result: DebugResult) {

    const panel = vscode.window.createWebviewPanel(
        "aiDebuggerResult",
        "AI Debugger",
        vscode.ViewColumn.Beside,
        {
            enableScripts: true
        }
    );

    panel.webview.html = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8" />
    <meta
        http-equiv="Content-Security-Policy"
        content="default-src 'none';
                 style-src 'unsafe-inline';
                 script-src 'unsafe-inline';"
    />
    <style>
        *{
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: var(--vscode-font-family);
            color: var(--vscode-foreground);
            background: var(--vscode-editor-background);
            font-size: 14px;

        }

        .header {
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 22px;
            border-bottom: 1px solid var(--vscode-panel-border);
            background: var(--vscode-sideBar-background);
            backdrop-filter: blur(10px);
        }

        .brand {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo {
            width: 38px;
            height: 38px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 10px;
            font-size: 20px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }


        .title {
            font-size: 16px;
            font-weight: 700;
        }

        .subtitle {
            margin-top: 2px;
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }

        .status {
            display: flex;
            align-items: center;
            gap: 7px;
            padding: 6px 10px;
            border-radius: 20px;
            font-size: 11px;
            background: var(--vscode-badge-background);
            color: var(--vscode-badge-foreground);
        }

        .status-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: #4ade80;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 26px 24px 60px;
        }

        .hero {
            margin-bottom: 22px;
        }

        .hero h1 {
            margin: 0 0 7px;
            font-size: 27px;
            letter-spacing: -0.5px;
        }

        .hero p {
            margin: 0;
            color: var(--vscode-descriptionForeground);
            line-height: 1.5;
        }

        .summary {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
            margin-bottom: 22px;
        }

        .summary-card {
            padding: 15px;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 10px;
            background: var(--vscode-textCodeBlock-background);
        }

        .summary-label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: .7px;
            color: var(--vscode-descriptionForeground);
            margin-bottom: 7px;
        }

        .summary-value {
            font-size: 13px;
            font-weight: 600;
        }

        .section {
            margin-bottom: 18px;
            border: 1px solid var(--vscode-panel-border);
            border-radius: 12px;
            overflow: hidden;
            background: var(--vscode-sideBar-background);
        }

        .section-header {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 13px 16px;
            border-bottom: 1px solid var(--vscode-panel-border);
            background: var(--vscode-textCodeBlock-background);
        }

        .section-icon {
            width: 27px;
            height: 27px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 7px;
            background: var(--vscode-badge-background);
            font-size: 14px;
        }

        .section-title {
            font-weight: 700;
            font-size: 13px;
        }

        .section-body {
            padding: 17px;
            line-height: 1.65;
        }

        .error-box {
            border-left: 3px solid #ef4444;
            padding: 13px 15px;
            border-radius: 7px;
            background: rgba(239, 68, 68, 0.08);
            font-family: var(--vscode-editor-font-family);
            font-size: 13px;
            white-space: pre-wrap;
            overflow-x: auto;
        }

        .root-cause {
            border-left: 3px solid #f59e0b;
            padding: 14px 16px;
            border-radius: 7px;
            background: rgba(245, 158, 11, 0.08);
        }

        .root-cause strong {
            display: block;
            margin-bottom: 6px;
        }

        .evidence {
            display: flex;
            flex-direction: column;
            gap: 9px;
        }

        .evidence-item {
            display: flex;
            gap: 10px;
            padding: 11px 13px;
            border-radius: 7px;
            background: var(--vscode-textCodeBlock-background);
            border: 1px solid var(--vscode-panel-border);
        }

        .evidence-number {
            min-width: 23px;
            height: 23px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            font-size: 11px;
            font-weight: 700;
        }

        .file {
            display: inline-flex;
            align-items: center;
            gap: 7px;
            padding: 6px 9px;
            margin: 4px 5px 4px 0;
            border-radius: 6px;
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
            background: var(--vscode-textCodeBlock-background);
            border: 1px solid var(--vscode-panel-border);
        }

        .code-wrapper {
            position: relative;
            margin: 12px 0;
        }

        pre {
            margin: 0;
            padding: 17px;
            overflow-x: auto;
            border-radius: 9px;
            background: var(--vscode-textCodeBlock-background);
            border: 1px solid var(--vscode-panel-border);
            font-family: var(--vscode-editor-font-family);
            font-size: 12px;
            line-height: 1.6;
        }

        code {
            font-family: var(--vscode-editor-font-family);
        }

        .copy-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            border: none;
            padding: 5px 9px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 11px;
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }

        .copy-btn:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .steps {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .step {
            display: flex;
            gap: 12px;
            padding: 11px;
            border-radius: 7px;
            background: var(--vscode-textCodeBlock-background);
        }

        .step-number {
            min-width: 25px;
            height: 25px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
            font-size: 11px;
            font-weight: 700;
        }

        .success {
            border-left: 3px solid #22c55e;
            padding: 13px 15px;
            border-radius: 7px;
            background: rgba(34, 197, 94, 0.08);
        }

        .markdown {
            white-space: normal;
        }

        .markdown h2 {
            font-size: 17px;
            margin: 22px 0 10px;
        }

        .markdown h3 {
            font-size: 14px;
            margin: 17px 0 8px;
        }

        .markdown p {
            margin: 7px 0;
        }

        .markdown ul {
            padding-left: 22px;
        }

        .markdown li {
            margin: 5px 0;
        }


        .markdown strong {
            font-weight: 700;
        }

        .markdown .inline-code {
            padding: 2px 5px;
            border-radius: 4px;
            background: var(--vscode-textCodeBlock-background);
            font-family: var(--vscode-editor-font-family);
        }

        .actions {
            display: flex;
            gap: 10px;
            margin-top: 25px;
        }

        button.action {
            border: none;
            border-radius: 7px;
            padding: 9px 15px;
            cursor: pointer;
            font-family: inherit;
            font-size: 12px;
            background: var(--vscode-button-background);
            color: var(--vscode-button-foreground);
        }

        button.action:hover {
            background: var(--vscode-button-hoverBackground);
        }

        button.secondary {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
        }

        @media (max-width: 700px) {
            .container {
                padding: 18px 14px;
            }

            .summary {
                grid-template-columns: 1fr;
            }

            .header {
                padding: 12px 14px;
            }
        }
    </style>
</head>

<body>
    <header class="header">
        <div class="brand">
            <div class="logo">
                🐞
            </div>

            <div>
                <div class="title">
                    AI Code Debugger
                </div>
                <div class="subtitle">
                    AI-powered root cause analysis
                </div>
            </div>
        </div>

        <div class="status">
            <span class="status-dot"></span>
            Analysis complete
        </div>
    </header>

    <main class="container">
        <div class="hero">
            <h1>
                Debugging Analysis
            </h1>

            <p>
                AI analysis based on your error,
                repository context, diagnostics,
                terminal logs and retrieved code.
            </p>
        </div>

        <div class="summary">
            <div class="summary-card">
                <div class="summary-label">
                    Status
                </div>

                <div class="summary-value">
                    ✓ Investigation completed
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-label">
                    Analysis
                </div>

                <div class="summary-value">
                    Root cause identified
                </div>
            </div>

            <div class="summary-card">
                <div class="summary-label">
                    AI Engine
                </div>

                <div class="summary-value">
                    Gemini + RAG
                </div>
            </div>
        </div>

        <section class="section">
            <div class="section-header">
                <div class="section-icon">
                    ⚠
                </div>

                <div class="section-title">
                    Error Detected
                </div>
            </div>

            <div class="section-body">
                <div class="error-box">
                    ${escapeHtml(
                        extractError(result.error)
                    )}
                </div>
            </div>
        </section>

        <section class="section">
            <div class="section-header">
                <div class="section-icon">
                    🎯
                </div>

                <div class="section-title">
                    Root Cause
                </div>
            </div>

            <div class="section-body">
                <div class="root-cause">
                    ${formatRootCause(result.rootCause)}
                </div>
            </div>
        </section>

        <section class="section">
            <div class="section-header">
                <div class="section-icon">
                    🔎
                </div>

                <div class="section-title">
                    AI Investigation
                </div>
            </div>

            <div class="section-body">
                <div class="markdown">
                    ${formatAIResponse(
                        result.evidence.join("\n")
                    )}
                </div>
            </div>
        </section>

        <section class="section">
            <div class="section-header">
                <div class="section-icon">
                    🛠
                </div>

                <div class="section-title">
                    Recommended Fix
                </div>
            </div>

            <div class="section-body">
                ${formatSolution(result.solution)}
            </div>
        </section>

        <section class="section">
            <div class="section-header">
                <div class="section-icon">
                    ✓
                </div>

                <div class="section-title">
                    Verification
                </div>
            </div>

            <div class="section-body">
                <div class="success">
                    After applying the fix, run the
                    affected command again and verify
                    that the original error no longer
                    occurs.
                </div>
            </div>
        </section>

        <div class="actions">
            <button
                class="action"
                onclick="copyResult()"
            >
                Copy Analysis
            </button>

            <button
                class="action secondary"
                onclick="closePanel()"
            >
                Close
            </button>
        </div>
    </main>

    <script>

        const vscode = acquireVsCodeApi();

        function copyResult() {
            const text = ${JSON.stringify(result)};
            navigator.clipboard.writeText(text);
        }

        function closePanel() {
            vscode.postMessage({
                command: "close"
            });
        }

        document.addEventListener(
            "click",
            function(event) {
                const button =
                    event.target.closest(
                        ".copy-code"
                    );
                if (!button) {
                    return;
                }
                const code =
                    button.parentElement
                        .querySelector("code")
                        .innerText;

                navigator.clipboard.writeText(code);

                button.innerText = "Copied!";

                setTimeout(() => {
                    button.innerText =
                        "Copy";
                },
                1500);
            }
        );

    </script>

</body>

</html>
    `;

    panel.webview.onDidReceiveMessage(message => {
        if (message.command === "close") {
            panel.dispose();
        }
    },
    undefined,
    []);
}

function extractError(answer: string): string {

    const match = answer.match(
        /(?:ERROR|Error|Exception)\s*[:\-]?\s*([\s\S]*?)(?=\n\s*(?:ROOT CAUSE|Root Cause|CAUSE|Cause|SOLUTION|Solution|FIX|Fix)\s*[:\-]?)/i
    );

    return match?.[1]?.trim() || answer.slice(0, 500);
}


function formatRootCause(answer: string): string {

    const match = answer.match(
        /(?:ROOT CAUSE|Root Cause|CAUSE|Cause)\s*[:\-]?\s*([\s\S]*?)(?=\n\s*(?:EVIDENCE|Evidence|SOLUTION|Solution|FIX|Fix|VERIFICATION|Verification)\s*[:\-]?)/i
    );

    if (!match) {
        return `
            <strong>
                Root cause analysis
            </strong>

            See the detailed AI investigation below.
        `;
    }

    return formatText(
        match[1].trim()
    );
}


function formatSolution(answer: string): string {

    const match = answer.match(
        /(?:SOLUTION|Solution|FIX|Fix|RECOMMENDED FIX|Recommended Fix)\s*[:\-]?\s*([\s\S]*?)(?=\n\s*(?:VERIFICATION|Verification|EVIDENCE|Evidence)\s*[:\-]?|$)/i
    );

    if (!match) {
        return `
            <div class="markdown">
                ${formatAIResponse(answer)}
            </div>
        `;
    }

    return `
        <div class="markdown">
            ${formatText(match[1].trim())}
        </div>
    `;
}


function formatAIResponse(answer: string): string {

    let html = escapeHtml(answer);

    html = html.replace(
        /```(\w+)?\n([\s\S]*?)```/g,
        (_match, language, code) => {

            return `
                <div class="code-wrapper">
                    <button class="copy-btn copy-code">
                        Copy
                    </button>
                    <pre><code>${code.trim()}</code></pre>
                </div>
            `;
        }
    );

    html = html.replace(
        /^### (.*)$/gm,
        "<h3>$1</h3>"
    );

    html = html.replace(
        /^## (.*)$/gm,
        "<h2>$1</h2>"
    );

    html = html.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );

    html = html.replace(
        /`([^`]+)`/g,
        '<span class="inline-code">$1</span>'
    );

    html = html.replace(
        /^\s*[-*]\s+(.*)$/gm,
        "<li>$1</li>"
    );

    html = html.replace(
        /(<li>.*<\/li>)/gs,
        "<ul>$1</ul>"
    );

    html = html.replace(
        /\n{2,}/g,
        "</p><p>"
    );

    html = "<p>" + html + "</p>";

    return html;
}

function formatText(text: string): string {

    let html = escapeHtml(text);

    html = html.replace(
        /\*\*(.*?)\*\*/g,
        "<strong>$1</strong>"
    );

    html = html.replace(
        /`([^`]+)`/g,
        '<span class="inline-code">$1</span>'
    );

    html = html.replace(
        /\n/g,
        "<br>"
    );

    return html;
}

function escapeHtml(text: string): string {
    return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}