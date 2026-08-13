import { notFound } from "next/navigation";
import { ApiError, getProject } from "@/lib/api";
import ProjectWorkspace from "@/components/projects/ProjectWorkspace";
import Header from "@/components/layout/Header";
import ErrorState from "@/components/ui/ErrorState";
import type { Project } from "@/lib/types";

// Server Component: extracts the dynamic segment and fetches the project
// server-side (fast first paint, and a clean place to turn a 404 into
// Next's not-found UI) before handing off to ProjectWorkspace — a Client
// Component, because everything below this point (chat, polling,
// approval) is inherently interactive. This is the "server/client
// components where appropriate" split described in the README; contrast
// with app/projects/page.tsx, which is client-only because it has no
// meaningfully static part.
export default async function ProjectPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;

  // The JSX return lives OUTSIDE the try block on purpose: React doesn't
  // render JSX synchronously where it's constructed, so a `return <X/>`
  // inside `try` wouldn't actually have X's render errors caught by this
  // catch anyway — only the `await getProject(...)` below is really
  // guarded here.
  let project: Project;
  try {
    project = await getProject(projectId);
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      notFound();
    }
    const message =
      err instanceof ApiError ? err.message : "Failed to load this project.";
    return (
      <div className="flex h-full flex-col">
        <Header />
        <div className="flex flex-1 items-center justify-center">
          <ErrorState message={message} />
        </div>
      </div>
    );
  }

  return <ProjectWorkspace projectId={projectId} initialProject={project} />;
}
