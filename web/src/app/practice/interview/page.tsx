"use client";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, Mic } from "lucide-react";
import { useEffect, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { InterviewSession } from "@/components/practice/InterviewSession";
import { InterviewSetup } from "@/components/practice/InterviewSetup";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useProfiles, type Status } from "@/lib/profile";
import type { InterviewOptions, InterviewSummary } from "@/lib/types";

export default function Interview() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: options } = useQuery({ queryKey: ["interview-options", pid], queryFn: () => api.get<InterviewOptions>(`/api/profiles/${pid}/interviews/options`), enabled: !!pid });
  const { data: sessions = [], isLoading } = useQuery({ queryKey: ["interviews", pid], queryFn: () => api.get<InterviewSummary[]>(`/api/profiles/${pid}/interviews`), enabled: !!pid });
  const [selected, setSelected] = useState("");
  const [setupOpen, setSetupOpen] = useState<boolean | null>(null);
  useEffect(() => { if (!selected && sessions[0]) setSelected(sessions[0].id); }, [sessions, selected]);
  const open = setupOpen ?? sessions.length === 0;

  return (
    <>
      <PageHeader title="Interview Room" description="A mock interview you answer out loud. Practice only, never for use during a real interview." />
      {!pid ? <NoProfile /> : isLoading || !options ? null : (
        <div className="space-y-6">
          <div>
            <Button onClick={() => setSetupOpen(!open)} aria-expanded={open}><Mic className="size-4" /> Start an interview <ChevronDown className={cn("size-4 transition-transform", open && "rotate-180")} /></Button>
            {open && <div className="mt-4"><InterviewSetup pid={pid} options={options} hasKey={!!status?.has_key} onCreated={(id) => { setSelected(id); setSetupOpen(false); }} /></div>}
          </div>
          {sessions.length === 0 && !open && <EmptyState icon={Mic} title="Start a short mock interview" text="Answer by voice or by typing. You get a score, a better answer and a follow-up for each question." />}
          {sessions.length > 0 && (
            <>
              <select aria-label="Saved interview" value={selected} onChange={(e) => setSelected(e.target.value)} className="h-10 w-full max-w-md rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">
                {sessions.map((s) => <option key={s.id} value={s.id}>{s.mode} · {s.state} · {s.id.slice(0, 6)}</option>)}
              </select>
              {selected && <InterviewSession key={selected} pid={pid} sid={selected} hasKey={!!status?.has_key} options={options} onDeleted={() => setSelected("")} />}
            </>
          )}
        </div>
      )}
    </>
  );
}
