"use client";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, FileCode2, FileText, GraduationCap, MessageSquare, Send, Square, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { CitedMarkdown } from "@/components/ui/CitedMarkdown";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";
import { useAsk } from "@/lib/ask";
import { useProfiles, type Status } from "@/lib/profile";
import type { AskStatus, Citation } from "@/lib/types";

const KIND = { resume: ["Your resume", FileText], repo: ["Your code", FileCode2], lesson: ["Your lesson", GraduationCap], knowledge: ["Knowledge base", BookOpen] } as const;
const safeUrl = (u: string) => (/^https?:\/\//.test(u) ? u : null);

export default function Ask() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: info } = useQuery({ queryKey: ["ask-status", pid], queryFn: () => api.get<AskStatus>(`/api/profiles/${pid}/ask/status`), enabled: !!pid });
  const { messages, busy, ask, stop, clear } = useAsk(pid);
  const [input, setInput] = useState("");
  const [cite, setCite] = useState<Citation | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  const submit = (q: string) => { if (!q.trim() || busy) return; setInput(""); setCite(null); ask(q); };
  // Show only sources the answer actually cites, so small talk does not carry unrelated source chips.
  const cited = (m: { text: string; sources?: Citation[] }) => (m.sources ?? []).filter((s) => m.text.includes(`[${s.n}]`));
  const open = (sources: Citation[] | undefined, n: number) => setCite(sources?.find((s) => s.n === n) ?? null);

  return (
    <>
      <PageHeader title="Ask CrackMate" description="Ask anything about your projects, your code or a concept. Answers use only your resume, your repositories, your saved lessons and the knowledge base, and every claim is numbered so you can check it."
        actions={messages.length > 0 ? <Button size="sm" variant="ghost" onClick={clear}><Trash2 className="size-4" /> New chat</Button> : undefined} />
      {!pid ? <NoProfile /> : (
        <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="flex min-h-[60vh] flex-col">
            <div className="flex-1 space-y-5 pb-4" aria-live="polite">
              {messages.length === 0 ? (
                <EmptyState icon={MessageSquare} title="What do you want to understand?" text={info ? `Searching ${info.passages.toLocaleString()} passages from your profile${info.knowledge_sources ? ` and ${info.knowledge_sources} knowledge-base sources` : ""}. Nothing is sent anywhere until you ask.` : "Loading your index…"}
                  action={<div className="flex max-w-xl flex-wrap justify-center gap-2">{info?.suggestions.map((s) => <button key={s} onClick={() => submit(s)} disabled={!status?.has_key} className="rounded-full border border-line bg-surface px-3 py-1.5 text-left text-sm text-body transition-colors hover:border-brand-200 hover:bg-brand-50 disabled:opacity-50">{s}</button>)}</div>} />
              ) : messages.map((m, i) => m.role === "user" ? (
                <div key={i} className="flex justify-end"><p className="max-w-[85%] rounded-2xl rounded-br-md bg-brand-600 px-4 py-2.5 text-white">{m.text}</p></div>
              ) : (
                <div key={i} className="max-w-[92%]">
                  {m.error ? <p role="alert" className="rounded-[var(--radius-control)] bg-bad-tint p-3 text-sm text-bad">{m.error}</p> : (
                    <Card className="space-y-3 py-4">
                      {m.text ? <CitedMarkdown count={m.sources?.length ?? 0} onCite={(n) => open(m.sources, n)}>{m.text}</CitedMarkdown> : <p className="text-sm text-muted">Searching your sources…</p>}
                      {m.pending && <span className="inline-block h-4 w-1.5 animate-pulse rounded-sm bg-brand-600 align-middle" aria-label="Writing" />}
                      {cited(m).length > 0 && (
                        <div className="flex flex-wrap gap-1.5 border-t border-line pt-3">
                          <span className="text-xs text-muted">Sources</span>
                          {cited(m).map((s) => <button key={s.n} onClick={() => setCite(s)} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-body hover:bg-brand-50" title={s.title}><span className="font-semibold text-brand-700">{s.n}</span><span className="max-w-32 truncate">{s.title}</span></button>)}
                        </div>
                      )}
                    </Card>
                  )}
                </div>
              ))}
              <div ref={end} />
            </div>
            <form onSubmit={(e) => { e.preventDefault(); submit(input); }} className="sticky bottom-4 flex gap-2 rounded-[var(--radius-card)] border border-line bg-surface p-2">
              <input aria-label="Your question" value={input} onChange={(e) => setInput(e.target.value)} maxLength={1000} placeholder={status?.has_key ? "Ask about your project, a concept, or a trade-off…" : "Add your Groq key to ask questions"} disabled={!status?.has_key}
                className="min-w-0 flex-1 bg-transparent px-3 text-sm text-ink outline-none placeholder:text-slate-400" />
              {busy ? <Button type="button" onClick={stop}><Square className="size-4" /> Stop</Button> : <Button type="submit" variant="primary" disabled={!input.trim() || !status?.has_key}><Send className="size-4" /> Ask</Button>}
            </form>
          </div>
          <aside aria-live="polite">
            {cite ? (
              <Card className="space-y-3 lg:sticky lg:top-6">
                <div className="flex items-start gap-2"><div className="min-w-0 flex-1"><Badge tone="brand">Source {cite.n} · {KIND[cite.kind][0]}</Badge><h2 className="mt-2 font-semibold text-ink">{cite.title}</h2></div><button onClick={() => setCite(null)} aria-label="Close source" className="text-muted hover:text-ink"><X className="size-4" /></button></div>
                <p className="max-h-80 overflow-y-auto whitespace-pre-wrap rounded-[var(--radius-control)] bg-slate-50 p-3 text-sm text-body">{cite.text}</p>
                <div className="space-y-1 text-xs text-muted">
                  {safeUrl(cite.location) ? <a href={cite.location} target="_blank" rel="noreferrer noopener" className="break-all text-brand-700 underline">{cite.location}</a> : <p>{cite.location}</p>}
                  {cite.license && <p>License: {cite.license}</p>}
                </div>
              </Card>
            ) : (
              <Card className="space-y-2 text-sm text-muted lg:sticky lg:top-6"><p className="font-medium text-ink">How answers are grounded</p><p>Click a numbered marker in an answer to read the exact passage it came from.</p>
                {info && <div className="space-y-1 pt-1">{Object.entries(info.indexed).map(([k, n]) => <p key={k}>{k.startsWith("repo:") ? "A repository" : k === "profile" ? "Your resume" : "Your saved lessons"}: {n} passages</p>)}</div>}
              </Card>
            )}
          </aside>
        </div>
      )}
    </>
  );
}
