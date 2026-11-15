import { ArrowDown, ArrowRight, ArrowUp } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { riskLabel, riskTone } from "@/lib/career";
import type { RiskRow } from "@/lib/types";

export function RiskBadge({ row }: { row: RiskRow }) {
  return <span title={row.why.join("\n")} className="cursor-help"><Badge tone={riskTone(row.risk)}>{riskLabel(row.risk)} · {row.risk.toFixed(1)}</Badge></span>;
}

export function Trend({ trend }: { trend: RiskRow["trend"] }) {
  const Icon = trend === "up" ? ArrowUp : trend === "down" ? ArrowDown : ArrowRight;
  return <Icon className={`size-4 ${trend === "up" ? "text-good" : trend === "down" ? "text-bad" : "text-muted"}`} aria-label={`Trend ${trend}`} />;
}

export function WhyList({ why }: { why: string[] }) {
  return <ul className="list-disc space-y-1 pl-5 text-sm text-body">{why.map((w, i) => <li key={i}>{w}</li>)}</ul>;
}
