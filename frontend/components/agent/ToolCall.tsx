"use client";

import { useState } from "react";
import type { ToolCall as ToolCallType } from "@/lib/types";
import { ToolCallStatusBadge } from "@/components/ui/Badge";

const TOOL_ICONS: Record<string, string> = {
  list_files: "📁",
  read_file: "📄",
  search_code: "🔍",
  semantic_code_search: "🔍",
  run_command: "⚙️",
  run_tests: "🧪",
  create_file: "✏️",
  write_file: "✏️",
};

const MAX_COLLAPSED_OUTPUT_CHARS = 300;

/** Tool outputs are persisted as `{"result": "<the tool's actual text>"}`
 * by execution_recorder.record_tool_call — see backend README. Falling
 * back to raw JSON keeps this component correct even if that shape ever
 * changes, rather than silently showing nothing.
 */
function extractOutputText(output: Record<string, unknown>): string {
  if (typeof output.result === "string") return output.result;
  return JSON.stringify(output, null, 2);
}

export default function ToolCallItem({ toolCall }: { toolCall: ToolCallType }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [outputExpanded, setOutputExpanded] = useState(false);

  const outputText = extractOutputText(toolCall.output);
  const isLongOutput = outputText.length > MAX_COLLAPSED_OUTPUT_CHARS;
  const displayedOutput =
    outputExpanded || !isLongOutput
      ? outputText
      : `${outputText.slice(0, MAX_COLLAPSED_OUTPUT_CHARS)}…`;

  return (
    <div className="rounded-md border border-border-subtle bg-panel-alt">
      <button
        onClick={() => setDetailsOpen((open) => !open)}
        className="flex w-full items-center justify-between gap-2 px-2 py-1.5 text-left"
      >
        <span className="flex min-w-0 items-center gap-1.5 text-xs font-medium text-text">
          <span aria-hidden="true">{TOOL_ICONS[toolCall.tool_name] ?? "🔧"}</span>
          <span className="truncate">{toolCall.tool_name}</span>
        </span>
        <span className="flex items-center gap-1.5">
          <ToolCallStatusBadge status={toolCall.status} />
          <span className="text-faint">{detailsOpen ? "▾" : "▸"}</span>
        </span>
      </button>

      {detailsOpen && (
        <div className="flex flex-col gap-2 border-t border-border-subtle px-2 py-2">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
              Input
            </p>
            <pre className="mt-1 overflow-x-auto rounded bg-bg p-2 font-mono text-[11px] text-muted">
              {JSON.stringify(toolCall.input, null, 2)}
            </pre>
          </div>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wide text-faint">
              Output
            </p>
            <pre className="mt-1 max-h-64 overflow-y-auto overflow-x-auto whitespace-pre-wrap rounded bg-bg p-2 font-mono text-[11px] text-muted">
              {displayedOutput}
            </pre>
            {isLongOutput && (
              <button
                onClick={() => setOutputExpanded((e) => !e)}
                className="mt-1 text-[11px] font-medium text-accent hover:text-accent-hover"
              >
                {outputExpanded ? "Show less" : "Show full output"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
