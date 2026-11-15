"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, API_BASE } from "./api";
import { useJob } from "./stream";
import type { ArtifactState } from "./types";

/** Claim check, pitch and diagram all work the same way: look up the saved copy, or run it with live progress. */
export function useArtifact<T>(pid: string | undefined, kind: string, projectId = "", enabled = true) {
  const client = useQueryClient();
  const key = ["artifact", pid, kind, projectId];
  const query = useQuery({ queryKey: key, queryFn: () => api.get<ArtifactState<T>>(`/api/profiles/${pid}/artifacts/${kind}?project_id=${projectId}`), enabled: !!pid && enabled });
  const job = useJob<ArtifactState<T>>();
  const run = async (regenerate = false) => {
    const next = await job.run(`/api/profiles/${pid}/artifacts/${kind}/run`, { project_id: projectId, regenerate });
    if (next) client.setQueryData(key, next);
    return next;
  };
  const setData = (updater: (old: ArtifactState<T>) => ArtifactState<T>) => client.setQueryData<ArtifactState<T>>(key, (old) => (old ? updater(old) : old));
  const exportHref = `${API_BASE}/api/profiles/${pid}/artifacts/${kind}/export?project_id=${projectId}`;
  return { state: query.data, loading: query.isLoading, job, run, setData, exportHref };
}
