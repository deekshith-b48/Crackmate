"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

export type ProfileSummary = { id: string; revision: number; name: string | null; role: string | null; company: string | null; projects: number };
export type Status = { has_key: boolean; model: string; fast_model: string; fallback_model: string; audio_seconds: number; limits: { file_mb: number; pages: number; text_chars: number } };

type Ctx = { profiles: ProfileSummary[]; active?: ProfileSummary; setActive: (id: string) => void; loading: boolean; refresh: () => void };
const ProfileContext = createContext<Ctx>({ profiles: [], setActive: () => {}, loading: true, refresh: () => {} });
export const useProfiles = () => useContext(ProfileContext);

const KEY = "crackmate.profile";

export function ProfileProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const { data = [], isLoading } = useQuery({ queryKey: ["profiles"], queryFn: () => api.get<ProfileSummary[]>("/api/profiles") });
  const [activeId, setActiveId] = useState<string | null>(null);
  useEffect(() => { try { setActiveId(localStorage.getItem(KEY)); } catch { /* private mode */ } }, []);
  const setActive = useCallback((id: string) => {
    setActiveId(id);
    try { localStorage.setItem(KEY, id); } catch { /* ignore */ }
  }, []);
  const active = data.find((p) => p.id === activeId) ?? data[0];
  const refresh = useCallback(() => { client.invalidateQueries({ queryKey: ["profiles"] }); }, [client]);
  return <ProfileContext.Provider value={{ profiles: data, active, setActive, loading: isLoading, refresh }}>{children}</ProfileContext.Provider>;
}
