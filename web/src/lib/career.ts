import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Blast, CareerSummary, ClaimRow, Signals } from "./types";

export const riskTone = (risk: number) => (risk >= 6 ? "bad" : risk >= 3 ? "warn" : "good") as "bad" | "warn" | "good";
export const riskLabel = (risk: number) => (risk >= 6 ? "High" : risk >= 3 ? "Medium" : "Low");
export const lessonHref = (topic: string) => `/learn/skills/?topic=${encodeURIComponent(topic)}&level=Basics`;

export const useSignals = (pid?: string) => useQuery({ queryKey: ["signals", pid], queryFn: () => api.get<Signals>(`/api/profiles/${pid}/career/signals`), enabled: !!pid });
export const useSummary = (pid?: string) => useQuery({ queryKey: ["career-summary", pid], queryFn: () => api.get<CareerSummary>(`/api/profiles/${pid}/career/summary`), enabled: !!pid });
export const useClaims = (pid?: string) => useQuery({ queryKey: ["career-claims", pid], queryFn: () => api.get<ClaimRow[]>(`/api/profiles/${pid}/career/claims`), enabled: !!pid });
export const useBlast = (pid: string | undefined, topic: string) => useQuery({ queryKey: ["blast", pid, topic], queryFn: () => api.get<Blast>(`/api/profiles/${pid}/career/blast?topic=${encodeURIComponent(topic)}`), enabled: !!pid && !!topic });

import type { ProjectCard, SecurityReport } from "./types";
export const useOverview = (pid?: string) => useQuery({ queryKey: ["career-overview", pid], queryFn: () => api.get<ProjectCard[]>(`/api/profiles/${pid}/career/overview`), enabled: !!pid });
export const useSecurity = (pid?: string) => useQuery({ queryKey: ["career-security", pid], queryFn: () => api.get<SecurityReport>(`/api/profiles/${pid}/career/security`), enabled: !!pid });
