
export interface DebugResult {
    error: string;
    rootCause: string;
    evidence: string[];
    solution: string;
    filesToChange: string[];
    fix: string;
    verification: string[];
}

export interface DebugResponse {
    success: boolean;
    answer?: DebugResult;
    index?: any;
    detail?: string;
}

export interface DebugRequest {
    repo: string;
    branch: string;
    errorMessage: string;
    terminalLogs: string;
    workspacePath: string;
    activeFile: string;
    activeCode: string;
    diagnostics: any[];
}

const BACKEND_URL = "https://ai-production-debugger.onrender.com";
const TIMEOUT_MS = 360_000; // 6 minutes

export async function sendDebugRequest(
    request: DebugRequest
): Promise<DebugResponse> {
    const url = `${BACKEND_URL}/api/debug`;
    const controller = new AbortController();

    let timedOut = false;

    const timeout = setTimeout(() => {
        timedOut = true;
        controller.abort();
    }, TIMEOUT_MS);

    try {
        console.log("[AI Debugger] Sending request...");
        console.log("[AI Debugger] URL:", url);
        console.log("[AI Debugger] Repository:", request.repo);
        console.log("[AI Debugger] Branch:", request.branch);
        console.log("[AI Debugger] Active file:", request.activeFile);
        console.log(
            "[AI Debugger] Active code length:",
            request.activeCode?.length ?? 0
        );
        console.log(
            "[AI Debugger] Terminal logs length:",
            request.terminalLogs?.length ?? 0
        );
        console.log(
            "[AI Debugger] Diagnostics count:",
            request.diagnostics?.length ?? 0
        );
        console.log("[AI Debugger] Timeout:", TIMEOUT_MS / 1000, "seconds");

        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Accept: "application/json",
            },
            body: JSON.stringify(request),
            signal: controller.signal,
        });

        console.log("[AI Debugger] HTTP status:", response.status);
        console.log("[AI Debugger] Response OK:", response.ok);

        const responseText = await response.text();

        console.log(
            "[AI Debugger] Response body:",
            responseText || "<empty response>"
        );

        if (!responseText.trim()) {
            throw new Error(
                `Backend returned an empty response (HTTP ${response.status}). ` +
                "Check the Render logs for the backend error."
            );
        }

        let data: DebugResponse;

        try {
            data = JSON.parse(responseText) as DebugResponse;
        } catch {
            throw new Error(
                `Backend returned invalid JSON (HTTP ${response.status}): ` +
                responseText.slice(0, 300)
            );
        }

        if (!response.ok) {
            throw new Error(
                data.detail ||
                `Backend returned HTTP ${response.status}: ${responseText.slice(0, 300)}`
            );
        }

        if (data.success !== true || !data.answer) {
            throw new Error(
                data.detail ||
                "The backend response does not contain a debug answer."
            );
        }

        console.log("[AI Debugger] Request completed successfully.");

        return data;
    } catch (error: unknown) {
        console.error("[AI Debugger] Request failed:", error);

        if (error instanceof Error) {
            console.error("[AI Debugger] Error name:", error.name);
            console.error("[AI Debugger] Error message:", error.message);
            console.error("[AI Debugger] Error cause:", error.cause);

            if (timedOut || error.name === "AbortError") {
                throw new Error(
                    `The debug request timed out after ${TIMEOUT_MS / 1000} seconds. ` +
                    "Check the Render logs and backend processing time."
                );
            }

            throw error;
        }

        throw new Error(String(error));
    } finally {
        clearTimeout(timeout);
    }
}
