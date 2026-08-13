"use client";

import { useState } from "react";
import type { CodeChange as CodeChangeType } from "@/lib/types";
import Badge from "@/components/ui/Badge";
import DiffView from "./DiffView";

const CHANGE_TYPE_LABEL: Record<CodeChangeType["change_type"], string> = {
  create: "Created",
  modify: "Modified",
  delete: "Deleted",
};

export default function CodeChange({ change }: { change: CodeChangeType }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="rounded-md border border-border-subtle bg-panel-alt">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left"
      >
        <span className="min-w-0 truncate font-mono text-xs text-text">
          {change.file_path}
        </span>
        <span className="flex shrink-0 items-center gap-1">
          <Badge tone="info">{CHANGE_TYPE_LABEL[change.change_type]}</Badge>
          {change.approved === true && <Badge tone="success">Approved</Badge>}
          {change.approved === false && <Badge tone="danger">Rejected</Badge>}
          {change.approved === null && <Badge tone="warning">Pending</Badge>}
          {change.applied && <Badge tone="success">Applied</Badge>}
        </span>
      </button>
      {open && (
        <div className="border-t border-border-subtle p-2">
          <DiffView diff={change.diff} />
        </div>
      )}
    </div>
  );
}
