/**
 * The only place that calls `fetch()` against the FastAPI backend. Every
 * component/hook goes through one of the functions below instead of
 * scattering raw fetch calls — see README (Phase 8) for why, and for the
 * full frontend-action -> backend-endpoint mapping table these mirror.
 */

import type {
  Conversation,
  ExecutionDetail,
  ExecutionSummary,
  Message,
  Project,
  ProjectCreateInput,
  ProjectUpdateInput,
  SendMessageResponse,
  TaskResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Extracts a readable message from FastAPI's error body — either
 * `{"detail": "message"}` (HTTPException) or `{"detail": [{"msg": ...}]}`
 * (422 request-validation errors) — falling back to the raw status text
 * if the body isn't JSON at all (e.g. the backend is down and something
 * in front of it, or Next's own dev proxy, returns an HTML error page).
 */
async function extractErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) {
      return body.detail
        .map((err: { msg?: string }) => err.msg)
        .filter(Boolean)
        .join("; ");
    }
  } catch {
    // response body wasn't JSON — fall through to the generic message
  }
  return `Request failed with status ${response.status}`;
}

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    // fetch() itself threw — the backend is unreachable (down, wrong
    // NEXT_PUBLIC_API_URL, CORS misconfigured, network offline, ...)
    throw new ApiError(
      `Could not reach the backend at ${API_URL}. Is it running?`,
      0,
    );
  }

  if (!response.ok) {
    throw new ApiError(await extractErrorMessage(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

// ---- Projects ----

export function getProjects(): Promise<Project[]> {
  return apiRequest<Project[]>("/api/projects");
}

export function createProject(input: ProjectCreateInput): Promise<Project> {
  return apiRequest<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProject(projectId: string): Promise<Project> {
  return apiRequest<Project>(`/api/projects/${projectId}`);
}

export function updateProject(
  projectId: string,
  input: ProjectUpdateInput,
): Promise<Project> {
  return apiRequest<Project>(`/api/projects/${projectId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function deleteProject(projectId: string): Promise<void> {
  return apiRequest<void>(`/api/projects/${projectId}`, { method: "DELETE" });
}

// ---- Conversations & messages ----

export function getConversations(projectId: string): Promise<Conversation[]> {
  return apiRequest<Conversation[]>(
    `/api/projects/${projectId}/conversations`,
  );
}

export function createConversation(
  projectId: string,
  title: string,
): Promise<Conversation> {
  return apiRequest<Conversation>(`/api/projects/${projectId}/conversations`, {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function getConversation(conversationId: string): Promise<Conversation> {
  return apiRequest<Conversation>(`/api/conversations/${conversationId}`);
}

export function getMessages(conversationId: string): Promise<Message[]> {
  return apiRequest<Message[]>(
    `/api/conversations/${conversationId}/messages`,
  );
}

/** Runs the LangGraph agent — blocks until it finishes or pauses for
 * approval. See hooks/useSendMessage.ts for how the UI stays responsive
 * (and shows live progress) while this is in flight.
 */
export function sendMessage(
  conversationId: string,
  content: string,
): Promise<SendMessageResponse> {
  return apiRequest<SendMessageResponse>(
    `/api/conversations/${conversationId}/messages`,
    { method: "POST", body: JSON.stringify({ content }) },
  );
}

// ---- Executions (history/detail) ----

export function getExecutions(projectId: string): Promise<ExecutionSummary[]> {
  return apiRequest<ExecutionSummary[]>(
    `/api/projects/${projectId}/executions`,
  );
}

export function getExecution(executionId: string): Promise<ExecutionDetail> {
  return apiRequest<ExecutionDetail>(`/api/executions/${executionId}`);
}

// ---- Tasks — the pending-approval view + the decision itself ----
// (execution_id doubles as `thread_id` — see lib/types.ts's TaskResponse)

export function getTask(executionId: string): Promise<TaskResponse> {
  return apiRequest<TaskResponse>(`/api/tasks/${executionId}`);
}

export function submitTaskDecision(
  executionId: string,
  approved: boolean,
): Promise<TaskResponse> {
  return apiRequest<TaskResponse>(`/api/tasks/${executionId}/decision`, {
    method: "POST",
    body: JSON.stringify({ approved }),
  });
}
