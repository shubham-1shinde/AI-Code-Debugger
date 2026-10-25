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

const BACKEND_URL = "https://ai-production-debugger.onrender.com";


export async function sendDebugRequest(
  request: DebugRequest
): Promise<DebugResponse> {
  try {
    const response = await fetch(
      `${BACKEND_URL}/api/debug`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(request),
        signal: AbortSignal.timeout(120_000),
      }
    );

    const text = await response.text();

    let data: DebugResponse;

    try {
      data = JSON.parse(text) as DebugResponse;
    } catch {
      throw new Error(
        `Backend returned invalid JSON (HTTP ${response.status}): ${
          text.slice(0, 300) || "(empty response)"
        }`
      );
    }

    if (!response.ok) {
      throw new Error(
        data.detail || `Backend returned HTTP ${response.status}`
      );
    }

    return data;
  } catch (error) {
    console.error("[AI Debugger] Request failed:", error);

    if (error instanceof Error && error.name === "TimeoutError") {
      throw new Error("Request timed out after 120 seconds.");
    }

    if (error instanceof TypeError) {
      throw new Error(
        `Cannot connect to the AI Debugger backend: ${error.message}. ` +
        "Check Render logs and the backend health endpoint."
      );
    }

    throw error;
  }
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