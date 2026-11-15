"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PartyPopper } from "lucide-react";
import { useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { QuestionCard } from "@/components/learn/QuestionCard";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import type { DueCard } from "@/lib/types";

export default function Review() {
  const { active } = useProfiles();
  const pid = active?.id;
  const client = useQueryClient();
  const { data: due = [], isLoading } = useQuery({ queryKey: ["due", pid], queryFn: () => api.get<DueCard[]>(`/api/profiles/${pid}/reviews/due`), enabled: !!pid });
  const [rated, setRated] = useState(false);
  const card = due[0];

  return (
    <>
      <PageHeader title="Review today" description="Recall the answer first, then rate yourself. Your rating decides when you see the question again." />
      {!pid ? <NoProfile /> : isLoading ? null : !card ? (
        <EmptyState icon={PartyPopper} title="Nothing due. Nice work." text="Open a lesson and rate its questions to start your review queue. Questions you find hard come back sooner." />
      ) : (
        <div className="space-y-4">
          <Card className="flex items-center justify-between py-4"><p className="text-sm text-muted">Questions due</p><p className="text-2xl font-semibold text-ink">{due.length}</p></Card>
          <QuestionCard key={card.slot + card.question} pid={pid} slot={card.slot} question={card.question} answer={card.answer} hint={card.hint} autoFocus onRated={() => setRated(true)} />
          {rated && <div className="flex justify-end"><Button variant="primary" onClick={() => { setRated(false); client.invalidateQueries({ queryKey: ["due", pid] }); }}>Next question</Button></div>}
        </div>
      )}
    </>
  );
}
