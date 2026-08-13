import Link from "next/link";
import Header from "@/components/layout/Header";

export default function ProjectNotFound() {
  return (
    <div className="flex h-full flex-col">
      <Header />
      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm font-medium text-text">Project not found.</p>
        <p className="max-w-sm text-sm text-muted">
          It may have been deleted, or the link is incorrect.
        </p>
        <Link href="/projects" className="text-sm font-medium text-accent hover:text-accent-hover">
          Back to Projects
        </Link>
      </div>
    </div>
  );
}
