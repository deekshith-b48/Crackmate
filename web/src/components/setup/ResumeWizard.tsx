"use client";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, FileText, ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input, Textarea } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { Tabs } from "@/components/ui/Tabs";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Status } from "@/lib/profile";
import { useJob } from "@/lib/stream";
import type { ProfileRecord } from "@/lib/types";

export function ResumeWizard({ onCreated }: { onCreated: (id: string) => void }) {
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const [mode, setMode] = useState<"paste" | "upload">("paste");
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState("");
  const [readError, setReadError] = useState("");
  const [reading, setReading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [target, setTarget] = useState({ role: "", company: "", job_description: "" });
  const [consent, setConsent] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const job = useJob<ProfileRecord>();
  const limit = status?.limits.text_chars ?? 12000;

  async function readFile(file: File) {
    setReadError("");
    setReading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const result = await api.post<{ text: string }>("/api/resume/read", form);
      setText(result.text);
      setFileName(file.name);
    } catch (error) {
      setReadError(error instanceof Error ? error.message : "That file could not be read.");
    } finally {
      setReading(false);
    }
  }

  async function extract() {
    const result = await job.run("/api/profile/extract", { text, consent, ...target });
    if (result) onCreated(result.id);
  }

  async function blank() {
    const record = await api.post<ProfileRecord>("/api/profiles");
    onCreated(record.id);
  }

  if (job.status === "running") return <StepGenerating title="Reading your resume" steps={job.steps} running startedAt={job.startedAt} />;

  const noKey = status && !status.has_key;
  const ready = text.trim().length > 0 && text.length <= limit && consent && !noKey;

  return (
    <div className="space-y-6">
      {job.status === "error" && (
        <div role="alert" className="flex gap-3 rounded-[var(--radius-card)] border border-red-200 bg-bad-tint p-4 text-sm text-bad">
          <AlertCircle className="mt-0.5 size-5 shrink-0" /><p>{job.error} Your text is still here, so you can try again.</p>
        </div>
      )}
      <Card>
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-brand-700"><span className="flex size-6 items-center justify-center rounded-full bg-brand-600 text-xs text-white">1</span> Add your resume</div>
        <p className="mb-4 text-sm text-muted">Paste the text or upload a text-based PDF or LaTeX file. You will review everything before it is used.</p>
        <Tabs tabs={[{ id: "paste", label: "Paste text" }, { id: "upload", label: "Upload PDF or LaTeX" }]} value={mode} onChange={setMode} />
        {mode === "upload" && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const file = e.dataTransfer.files[0]; if (file) readFile(file); }}
            onClick={() => picker.current?.click()}
            className={cn("mb-4 flex cursor-pointer flex-col items-center rounded-[var(--radius-card)] border-2 border-dashed px-6 py-10 text-center transition-colors duration-150", dragging ? "border-brand-500 bg-brand-50" : "border-slate-300 hover:border-brand-500 hover:bg-brand-50/40")}
          >
            <UploadCloud className="mb-2 size-8 text-brand-600" aria-hidden />
            <p className="font-medium text-ink">{reading ? "Reading your file…" : fileName ? `Loaded ${fileName}` : "Drop your resume here, or click to choose"}</p>
            <p className="mt-1 text-xs text-muted">PDF or .tex, up to {status?.limits.file_mb ?? 5} MB and {status?.limits.pages ?? 10} pages</p>
            <input ref={picker} type="file" accept=".pdf,.tex" className="sr-only" aria-label="Resume file" onChange={(e) => { const f = e.target.files?.[0]; if (f) readFile(f); e.target.value = ""; }} />
          </div>
        )}
        {readError && <p role="alert" className="mb-4 text-sm text-bad">{readError}</p>}
        <Field label="Resume text" htmlFor="resume-text" hint={`${text.length.toLocaleString()} of ${limit.toLocaleString()} characters. Remove contact details and anything you want to keep private.`}>
          <Textarea id="resume-text" value={text} onChange={(e) => setText(e.target.value)} className="min-h-64 font-mono text-[13px]" placeholder="Paste your resume text here, or load a file above." />
        </Field>
      </Card>

      <Card>
        <div className="mb-1 flex items-center gap-2 text-sm font-semibold text-brand-700"><span className="flex size-6 items-center justify-center rounded-full bg-brand-600 text-xs text-white">2</span> Interview target <span className="font-normal text-muted">(optional)</span></div>
        <p className="mb-4 text-sm text-muted">Tailors examples and questions. Stays on this computer until you generate something.</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Target role" htmlFor="role"><Input id="role" maxLength={200} value={target.role} onChange={(e) => setTarget({ ...target, role: e.target.value })} placeholder="Backend engineer" /></Field>
          <Field label="Company" htmlFor="company"><Input id="company" maxLength={200} value={target.company} onChange={(e) => setTarget({ ...target, company: e.target.value })} placeholder="Optional" /></Field>
        </div>
        <Field className="mt-4" label="Job description" htmlFor="jd"><Textarea id="jd" maxLength={8000} value={target.job_description} onChange={(e) => setTarget({ ...target, job_description: e.target.value })} placeholder="Paste the job posting if you have one." /></Field>
      </Card>

      <Card>
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-brand-700"><span className="flex size-6 items-center justify-center rounded-full bg-brand-600 text-xs text-white">3</span> Extract your profile</div>
        <div className="mb-4 flex gap-3 rounded-[var(--radius-control)] bg-brand-50 p-3 text-sm text-brand-700"><ShieldCheck className="mt-0.5 size-4 shrink-0" /><p>Extracting sends only your reviewed resume text to Groq. Your key never leaves this computer.</p></div>
        <Checkbox checked={consent} onChange={(e) => setConsent(e.target.checked)} label="Send the reviewed resume text to Groq" />
        {noKey && <p className="mt-3 text-sm text-warn">Add your Groq key to <code className="font-mono">.streamlit/secrets.toml</code> and restart to enable extraction. You can still start with a blank profile.</p>}
        <div className="mt-5 flex flex-wrap gap-3">
          <Button variant="primary" onClick={extract} disabled={!ready}><FileText className="size-4" /> Extract profile</Button>
          <Button variant="ghost" onClick={blank}>Start with a blank profile</Button>
        </div>
      </Card>
    </div>
  );
}
