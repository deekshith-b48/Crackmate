"use client";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { RepoView } from "@/lib/types";

/** Which commit authors are you? Lets CrackMate separate what you wrote from what teammates wrote. */
export function IdentityPicker({ pid, projectId, repo, initial = [], onSaved }: { pid: string; projectId: string; repo: RepoView; initial?: string[]; onSaved?: () => void }) {
  const [me, setMe] = useState<string[]>(initial);
  const client = useQueryClient();
  const toast = useToast();
  async function save() {
    try {
      await api.put(`/api/profiles/${pid}/career/repos/${projectId}/identity`, { identities: me });
      client.invalidateQueries({ queryKey: ["career-overview", pid] });
      toast("good", "Ownership updated.");
      onSaved?.();
    } catch (e) { toast("bad", e instanceof Error ? e.message : "Could not save."); }
  }
  return (
    <div className="space-y-2 rounded-[var(--radius-control)] border border-line p-3">
      <p className="text-sm text-body">Which of these commit authors are you? Tick every name or email you committed with.</p>
      {repo.authors.map((a) => {
        const on = me.includes(a.email);
        return (
          <label key={a.email} className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={on} onChange={() => setMe(on ? me.filter((x) => x !== a.email) : [...me, a.email])} className="size-4 accent-[var(--color-brand-600)]" />
            {a.name} <span className="text-muted">&lt;{a.email}&gt; · {a.commits} commits</span>
          </label>
        );
      })}
      <Button size="sm" variant="primary" onClick={save} disabled={!me.length}>Save</Button>
    </div>
  );
}
