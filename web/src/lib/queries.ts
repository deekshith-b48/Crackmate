"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { FormLabels, ProfileRecord } from "./types";

export const useProfile = (id?: string) =>
  useQuery({ queryKey: ["profile", id], queryFn: () => api.get<ProfileRecord>(`/api/profiles/${id}`), enabled: !!id });

export const useFormLabels = () => useQuery({ queryKey: ["form-labels"], queryFn: () => api.get<FormLabels>("/api/profile-form"), staleTime: Infinity });
