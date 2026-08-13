import type { ExecutionStatus, ToolCallStatus } from "@/lib/types";

type Tone = "success" | "warning" | "danger" | "info" | "muted";

const TONE_CLASSES: Record<Tone, string> = {
  success: "bg-success/10 text-success border-success/30",
  warning: "bg-warning/10 text-warning border-warning/30",
  danger: "bg-danger/10 text-danger border-danger/30",
  info: "bg-info/10 text-info border-info/30",
  muted: "bg-panel-alt text-muted border-border",
};

export default function Badge({
  tone = "muted",
  children,
}: {
  tone?: Tone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium ${TONE_CLASSES[tone]}`}
    >
      {children}
    </span>
  );
}

const EXECUTION_STATUS_TONE: Record<ExecutionStatus, Tone> = {
  pending: "muted",
  running: "info",
  waiting_for_approval: "warning",
  completed: "success",
  failed: "danger",
  cancelled: "muted",
};

const EXECUTION_STATUS_LABEL: Record<ExecutionStatus, string> = {
  pending: "Pending",
  running: "Running",
  waiting_for_approval: "Waiting for approval",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export function ExecutionStatusBadge({ status }: { status: ExecutionStatus }) {
  return (
    <Badge tone={EXECUTION_STATUS_TONE[status]}>
      {EXECUTION_STATUS_LABEL[status]}
    </Badge>
  );
}

export function ToolCallStatusBadge({ status }: { status: ToolCallStatus }) {
  return (
    <Badge tone={status === "success" ? "success" : "danger"}>
      {status === "success" ? "Success" : "Error"}
    </Badge>
  );
}
