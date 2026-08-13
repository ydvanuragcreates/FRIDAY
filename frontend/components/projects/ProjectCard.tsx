import Link from "next/link";
import type { Project } from "@/lib/types";
import { formatRelativeTime } from "@/lib/format";

export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      href={`/projects/${project.id}`}
      className="block rounded-lg border border-border bg-panel p-4 transition-colors hover:border-faint"
    >
      <h3 className="truncate text-sm font-semibold text-text">{project.name}</h3>
      <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-xs text-muted">
        {project.description || "No description."}
      </p>
      <p className="mt-3 truncate rounded bg-panel-alt px-2 py-1 font-mono text-xs text-faint">
        {project.repository_path}
      </p>
      <p className="mt-3 text-xs text-faint">
        Updated {formatRelativeTime(project.updated_at)}
      </p>
    </Link>
  );
}
