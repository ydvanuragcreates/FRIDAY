"use client";

import { useState } from "react";
import type { TestResult as TestResultType } from "@/lib/types";
import Badge from "@/components/ui/Badge";

export default function TestResult({ result }: { result: TestResultType }) {
  const [showOutput, setShowOutput] = useState(false);

  return (
    <div className="rounded-md border border-border-subtle bg-panel-alt p-2">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 text-xs font-medium text-text">
          {result.passed ? (
            <Badge tone="success">✓ Passed</Badge>
          ) : (
            <Badge tone="danger">✗ Failed</Badge>
          )}
        </span>
        <span className="truncate font-mono text-[11px] text-faint">{result.command}</span>
      </div>

      {!result.passed && result.error_output && (
        <div className="mt-2">
          <button
            onClick={() => setShowOutput((s) => !s)}
            className="text-[11px] font-medium text-accent hover:text-accent-hover"
          >
            {showOutput ? "Hide error output" : "Show error output"}
          </button>
          {showOutput && (
            <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-bg p-2 font-mono text-[11px] text-danger">
              {result.error_output}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
