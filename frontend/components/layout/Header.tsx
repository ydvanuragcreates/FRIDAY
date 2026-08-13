import Link from "next/link";

export default function Header({
  projectName,
}: {
  projectName?: string;
}) {
  return (
    <header className="flex h-12 shrink-0 items-center justify-between border-b border-border bg-panel px-4">
      <div className="flex items-center gap-2 text-sm">
        <Link href="/projects" className="font-semibold text-text hover:text-accent">
          AI Coding Agent
        </Link>
        {projectName && (
          <>
            <span className="text-faint">/</span>
            <span className="text-muted">{projectName}</span>
          </>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs text-muted">
        <span className="h-2 w-2 rounded-full bg-success" aria-hidden="true" />
        Local Dev User
      </div>
    </header>
  );
}
