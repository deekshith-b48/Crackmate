"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog, Dialog } from "@/components/ui/Dialog";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import type { TopicDetail } from "@/lib/types";

export function TopicDialog({ pid, tid, onClose }: { pid: string; tid: string | null; onClose: () => void }) {
  const client = useQueryClient();
  const toast = useToast();
  const [confirm, setConfirm] = useState(false);
  const { data } = useQuery({ queryKey: ["topic", pid, tid], queryFn: () => api.get<TopicDetail>(`/api/profiles/${pid}/learning/topics/${tid}`), enabled: !!tid });

  async function act(action: string, message: string) {
    try {
      const next = await api.post<TopicDetail>(`/api/profiles/${pid}/learning/topics/${tid}`, { action });
      client.setQueryData(["topic", pid, tid], next);
      client.invalidateQueries({ queryKey: ["progress", pid] });
      client.invalidateQueries({ queryKey: ["dashboard", pid] });
      toast("good", message);
    } catch (error) { toast("bad", error instanceof Error ? error.message : "That did not work."); }
  }

  return (
    <>
      <Dialog open={!!tid} onClose={onClose} title={data?.name ?? "Topic"} wide>
        {data && (
          <div className="space-y-4">
            <p className="text-sm text-body"><span className="font-medium text-ink">{data.state}</span> · {data.count} compatible scored attempts · next review {data.due ?? "not scheduled"}</p>
            <p className="text-xs text-muted">{data.limitation}</p>
            <div className="max-h-72 space-y-2 overflow-y-auto">
              {data.evidence.length === 0 && <p className="text-sm text-muted">No scored answers for this topic yet. Practise a few questions to see evidence here.</p>}
              {data.evidence.map((e, i) => (
                <details key={i} className="rounded-[var(--radius-control)] border border-line px-3 py-2 text-sm">
                  <summary className="cursor-pointer font-medium text-ink">{e.question}</summary>
                  <p className="mt-1 text-xs text-muted">{e.source} · {e.time?.slice(0, 16) ?? "unknown date"} · {e.independent ? "independent" : "assisted or unknown"}</p>
                  <p className="mt-1 font-mono text-xs">{Object.entries(e.scores).map(([k, v]) => `${k} ${v}/4`).join(" · ")}</p>
                  {e.missing && <p className="mt-1 text-body">Gap: {e.missing}</p>}
                </details>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => act("review_tomorrow", "Review scheduled for tomorrow.")}>Review tomorrow</Button>
              <Button size="sm" onClick={() => act("reset_schedule", "Review date reset to today.")}>Reset review date to today</Button>
              <Button size="sm" variant="danger" onClick={() => setConfirm(true)}>Reset topic progress…</Button>
            </div>
          </div>
        )}
      </Dialog>
      <ConfirmDialog open={confirm} onClose={() => setConfirm(false)} title="Reset progress for this topic?" text="Learning progress for this topic restarts from zero. Your original practice history is kept." confirmLabel="Reset progress"
        onConfirm={async () => { await act("reset_progress", "Topic progress reset."); setConfirm(false); }} />
    </>
  );
}
