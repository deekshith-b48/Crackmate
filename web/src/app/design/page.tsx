"use client";
import { Inbox } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge, DifficultyBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";

const DEMO = ["Reading your project details…", "Finding trusted sources…", "Writing the lesson…", "Checking the format…"];

export default function Design() {
  const toast = useToast();
  const [shown, setShown] = useState(0);
  const [running, setRunning] = useState(false);
  const [startedAt, setStartedAt] = useState(0);
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setShown((n) => (n >= DEMO.length ? n : n + 1)), 1200);
    return () => clearInterval(timer);
  }, [running]);
  useEffect(() => { if (running && shown >= DEMO.length) setTimeout(() => setRunning(false), 1200); }, [running, shown]);

  return (
    <>
      <PageHeader title="Design system" description="Every building block of the CrackMate interface, in one place." />
      <div className="space-y-8">
        <Card>
          <h2 className="mb-4 font-semibold text-ink">Buttons</h2>
          <div className="flex flex-wrap gap-3">
            <Button variant="primary">Generate lesson</Button>
            <Button>Regenerate</Button>
            <Button variant="ghost">Cancel</Button>
            <Button variant="danger">Delete profile</Button>
            <Button variant="primary" loading>Working</Button>
            <Button variant="primary" size="sm">Small</Button>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-semibold text-ink">Badges (colour only ever means something)</h2>
          <div className="flex flex-wrap items-center gap-3">
            <Badge>Neutral</Badge><Badge tone="brand">Shared lesson</Badge><Badge tone="good">Defended</Badge><Badge tone="warn">Assumption</Badge><Badge tone="bad">High risk</Badge>
            <DifficultyBadge position={0} total={6} /><DifficultyBadge position={3} total={6} /><DifficultyBadge position={5} total={6} />
          </div>
        </Card>
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold text-ink">Generating animation</h2>
            <Button variant="primary" size="sm" onClick={() => { setShown(1); setStartedAt(Date.now()); setRunning(true); }} disabled={running}>Play demo</Button>
          </div>
          {shown > 0 ? <StepGenerating title="Writing your lesson" steps={DEMO.slice(0, shown)} running={running} startedAt={startedAt} /> : <p className="text-sm text-muted">Press “Play demo”.</p>}
        </section>
        <Card>
          <h2 className="mb-4 font-semibold text-ink">Toasts</h2>
          <div className="flex gap-3">
            <Button onClick={() => toast("good", "Profile changes saved.")}>Success</Button>
            <Button onClick={() => toast("bad", "Groq is rate limiting requests. Retry after the reset.")}>Error</Button>
          </div>
        </Card>
        <EmptyState icon={Inbox} title="Nothing due. Nice work." text="Open a lesson and rate its questions to start your review queue." action={<Button variant="primary">Open a lesson</Button>} />
        <Card>
          <h2 className="mb-4 font-semibold text-ink">Type</h2>
          <p className="text-[28px] font-semibold tracking-tight text-ink">Heading 28 · Inter semibold</p>
          <p className="mt-2 text-xl font-semibold text-ink">Heading 20</p>
          <p className="mt-2">Body 15. Plain, encouraging language that is easy to scan.</p>
          <p className="mt-2 font-mono text-[13px]">def two_sum(nums, target): # JetBrains Mono 13</p>
        </Card>
      </div>
    </>
  );
}
