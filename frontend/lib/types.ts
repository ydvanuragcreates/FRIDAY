/**
 * TypeScript mirrors of the FastAPI Pydantic schemas — kept in one file,
 * one interface per backend model, field-for-field. See ../../README.md
 * (Phase 8) for the API mapping table these correspond to. Do not add a
 * field here that the backend doesn't actually return; do not rename one
 * to be "nicer" — a mismatch here is a silent runtime bug, not a type
 * error, since `fetch` doesn't validate shapes for you.
 */

// ---- Enums (string unions, matching the Python str Enums exactly) ----

export type MessageRole = "user" | "assistant" | "system" | "tool";

export type ExecutionStatus =
  | "pending"
  | "running"
  | "waiting_for_approval"
  | "completed"
  | "failed"
  | "cancelled";

export type ToolCallStatus = "success" | "error";

export type ChangeType = "create" | "modify" | "delete";

// ---- app/schemas/project.py ----

export interface Project {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  repository_path: string;
  repository_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreateInput {
  name: string;
  description?: string | null;
  repository_path: string;
  repository_url?: string | null;
}

export interface ProjectUpdateInput {
  name?: string;
  description?: string | null;
  repository_path?: string;
  repository_url?: string | null;
}

// ---- app/schemas/conversation.py ----

export interface Conversation {
  id: string;
  project_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

export interface SendMessageResponse {
  conversation_id: string;
  execution_id: string;
  status: string;
  user_message: Message;
  assistant_message: Message | null;
}

// ---- app/schemas/execution.py ----

export interface AgentPlan {
  id: string;
  plan: string;
  created_at: string;
}

export interface ToolCall {
  id: string;
  tool_name: string;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  status: ToolCallStatus;
  created_at: string;
}

export interface CodeChange {
  id: string;
  file_path: string;
  change_type: ChangeType;
  diff: string;
  approved: boolean | null;
  applied: boolean;
  created_at: string;
}

export interface TestResult {
  id: string;
  command: string;
  passed: boolean;
  output: string;
  error_output: string | null;
  created_at: string;
}

export interface ExecutionSummary {
  id: string;
  project_id: string;
  conversation_id: string | null;
  status: ExecutionStatus;
  user_request: string;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
  retry_count: number;
}

export interface ExecutionDetail extends ExecutionSummary {
  agent_plans: AgentPlan[];
  tool_calls: ToolCall[];
  code_changes: CodeChange[];
  test_results: TestResult[];
}

// ---- app/models/schemas.py — the Phase 5 task/approval endpoints ----
// (execution_id doubles as `thread_id` here — see README > "How LangGraph
// talks to the database")

export interface ProposedChange {
  file_path: string;
  action: string; // "create" | "write" — see app/graph/state.py
  content: string;
  diff: string;
}

export interface TaskResponse {
  thread_id: string;
  status: string; // "awaiting_approval" | "completed"
  plan: string;
  analysis: string;
  files_inspected: string[];
  proposed_changes: ProposedChange[];
  applied_changes: string[];
  test_results: string;
  test_passed: boolean;
  retry_count: number;
  errors: string[];
  final_response: string;
}
