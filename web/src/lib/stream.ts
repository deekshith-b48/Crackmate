"use client";
import { useCallback, useRef, useState } from "react";
import { API_BASE } from "./api";

export type StreamEvent<T = unknown> =
  | { type: "step"; text: string }
  | { type: "result"; data: T }
  | { type: "error"; message: string }
  | { type: "ping" };

/** Splits an NDJSON byte stream into events, even when a line arrives in several chunks. */
export function createLineParser<T = unknown>() {
  let buffer = "";
  return (chunk: string): StreamEvent<T>[] => {
    buffer += chunk;
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    return lines.filter(Boolean).flatMap((line) => {
      try {
        return [JSON.parse(line) as StreamEvent<T>];
      } catch {
        return [];
      }
    });
  };
}

export type JobState<T> = {
  status: "idle" | "running" | "done" | "error";
  steps: string[];
  result?: T;
  error?: string;
  startedAt?: number;
};

/** Runs a streaming POST and exposes its progress steps, so no one ever stares at a blank spinner. */
export function useJob<T = unknown>() {
  const [state, setState] = useState<JobState<T>>({ status: "idle", steps: [] });
  const controller = useRef<AbortController | null>(null);

  const run = useCallback(async (path: string, body: unknown = {}): Promise<T | undefined> => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setState({ status: "running", steps: [], startedAt: Date.now() });
    try {
      const response = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CrackMate": "1" },
        body: JSON.stringify(body),
        signal: abort.signal,
      });
      if (!response.ok || !response.body) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.message ?? "Something went wrong. Please try again.");
      }
      const parse = createLineParser<T>();
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      let result: T | undefined;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const event of parse(value)) {
          if (event.type === "step") setState((s) => ({ ...s, steps: [...s.steps, event.text] }));
          if (event.type === "result") result = event.data;
          if (event.type === "error") throw new Error(event.message);
        }
      }
      setState((s) => ({ ...s, status: "done", result }));
      return result;
    } catch (error) {
      if (abort.signal.aborted) return undefined;
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setState((s) => ({ ...s, status: "error", error: message }));
      return undefined;
    }
  }, []);

  const reset = useCallback(() => {
    controller.current?.abort();
    setState({ status: "idle", steps: [] });
  }, []);

  return { ...state, run, reset };
}
