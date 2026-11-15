"use client";
import { Sparkles, Square, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { ProjectPicker } from "@/components/learn/ProjectPicker";
import { RunBar } from "@/components/learn/RunBar";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { useProfiles } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import type { PitchData } from "@/lib/types";
import { useArtifact } from "@/lib/useArtifact";

export default function Pitch() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: record } = useProfile(pid);
  const [projectId, setProjectId] = useState("");
  const { state, job, run, exportHref } = useArtifact<PitchData>(pid, "pitch", projectId, !!projectId);
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => { window.speechSynthesis?.cancel(); }, []);
  useEffect(() => { window.speechSynthesis?.cancel(); setSpeaking(false); }, [projectId]);
  const pitch = state?.data;
  const words = pitch?.pitch.split(/\s+/).filter(Boolean).length ?? 0;

  function speak() {
    const synth = window.speechSynthesis;
    if (!synth || !pitch) return;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const utterance = new SpeechSynthesisUtterance(pitch.pitch);
    utterance.onend = utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
    setSpeaking(true);
  }

  return (
    <>
      <PageHeader title="Project Pitch" description="A spoken-style 2-minute pitch for each project. Read it aloud, then rehearse it in your own words." />
      {!pid || !record ? <NoProfile /> : (
        <div className="space-y-6">
          <ProjectPicker projects={record.profile.projects} value={projectId} onPick={setProjectId} />
          {projectId && <RunBar state={state} job={job as never} onRun={run} runLabel="Write my pitch" redoLabel="Rewrite pitch" runningTitle="Writing and checking your pitch" exportHref={exportHref} />}
          {projectId && !pitch && job.status !== "running" && <EmptyState icon={Sparkles} title="Your pitch is ready to write" text="It uses only what your profile says, so no invented numbers. The more you add under Clarify, the better it gets." />}
          {pitch && (
            <>
              <Card className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <h2 className="text-xl font-semibold text-ink">{pitch.opening}</h2>
                  <Button size="sm" onClick={speak}>{speaking ? <><Square className="size-4" /> Stop</> : <><Volume2 className="size-4" /> Hear it</>}</Button>
                </div>
                <p className="max-w-[720px] whitespace-pre-line text-[17px] leading-8 text-ink">{pitch.pitch}</p>
                <p className="text-xs text-muted">About {words} words · roughly {Math.max(1, Math.round(words / 140))} minutes spoken</p>
              </Card>
              <Card>
                <h3 className="mb-2 font-semibold text-ink">Be ready to expand on</h3>
                <ul className="list-disc space-y-1 pl-5">{pitch.key_points.map((p) => <li key={p}>{p}</li>)}</ul>
              </Card>
              <Card className="border-amber-200 bg-warn-tint"><h3 className="mb-1 font-semibold text-ink">Assumptions</h3><Markdown>{pitch.assumptions}</Markdown></Card>
            </>
          )}
        </div>
      )}
    </>
  );
}
