"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  createProject as apiCreateProject,
  deleteProject as apiDeleteProject,
  getProjects,
} from "@/lib/api";
import type { Project, ProjectCreateInput } from "@/lib/types";

export function useProjects() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProjects(await getProjects());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load projects.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // The standard "fetch on mount" pattern (React's own docs show this
    // shape under "Synchronizing with Effects") — `refresh` sets loading/
    // error/data state, which `react-hooks/set-state-in-effect` flags on
    // principle (it wants effects to avoid synchronous setState so React
    // Compiler can batch more aggressively). There's no framework-level
    // data layer here (no React Query, no Next server loader — this is a
    // client-side hook over a separate FastAPI backend), so an effect is
    // the correct tool; this isn't a bug the rule is catching.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  // Errors from create/remove are intentionally NOT caught here — the
  // caller (e.g. CreateProjectModal) needs them to drive its own inline
  // loading/error UI, which a hook-level error state can't do well since
  // it's shared across every list-level consumer of this hook.
  const create = useCallback(async (input: ProjectCreateInput) => {
    const project = await apiCreateProject(input);
    setProjects((prev) => [project, ...prev]);
    return project;
  }, []);

  const remove = useCallback(async (projectId: string) => {
    await apiDeleteProject(projectId);
    setProjects((prev) => prev.filter((p) => p.id !== projectId));
  }, []);

  return { projects, loading, error, refresh, create, remove };
}
