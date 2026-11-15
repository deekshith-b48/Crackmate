"use client";
import { Workflow } from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Project } from "@/lib/types";

/** Shared by Projects, Pitch and Architecture. Calls onPick with the first project until you choose. */
export function ProjectPicker({ projects, value, onPick }: { projects: Project[]; value: string; onPick: (id: string) => void }) {
  useEffect(() => { if (!value && projects[0]) onPick(projects[0].id); }, [value, projects, onPick]);
  if (!projects.length) return <EmptyState icon={Workflow} title="Add a project first" text="Projects are where interviews go deep. Add one in your profile." action={<Link href="/setup/"><Button variant="primary">Add a project</Button></Link>} />;
  return (
    <div className="flex flex-wrap gap-2" role="tablist" aria-label="Project">
      {projects.map((p) => (
        <button key={p.id} role="tab" aria-selected={p.id === value} onClick={() => onPick(p.id)}
          className={`rounded-full border px-4 py-1.5 text-sm font-medium transition-colors duration-150 ${p.id === value ? "border-brand-600 bg-brand-600 text-white" : "border-line bg-surface text-body hover:border-brand-200 hover:bg-brand-50"}`}>
          {p.title}
        </button>
      ))}
    </div>
  );
}
