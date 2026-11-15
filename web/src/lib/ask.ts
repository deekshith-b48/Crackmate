"use client";
import { useCallback, useRef, useState } from "react";
import { API_BASE } from "./api";
import { createLineParser, type StreamEvent } from "./stream";
import type { ChatMessage, Citation } from "./types";

type AskEvent = StreamEvent<unknown> | { type: "sources"; data: Citation[] } | { type: "token"; text: string } | { type: "done" };

/** Streams an answer: sources arrive first so citations can be shown, then the text token by token. */
export function useAsk(pid?: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string) => {
    if (!pid || !question.trim()) return;
    const history = messages.filter((m) => !m.error && !m.pending).slice(-8).map((m) => ({ role: m.role, text: m.text }));
    setMessages((old) => [...old, { role: "user", text: question }, { role: "assistant", text: "", pending: true }]);
    setBusy(true);
    abort.current?.abort();
    const controller = (abort.current = new AbortController());
    const patch = (fn: (m: ChatMessage) => ChatMessage) => setMessages((old) => old.map((m, i) => (i === old.length - 1 ? fn(m) : m)));
    try {
      const response = await fetch(`${API_BASE}/api/profiles/${pid}/ask`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-CrackMate": "1" }, body: JSON.stringify({ question, history }), signal: controller.signal,
      });
      if (!response.ok || !response.body) throw new Error((await response.json().catch(() => null))?.message ?? "Something went wrong. Please try again.");
      const parse = createLineParser<unknown>();
      const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        for (const event of parse(value) as AskEvent[]) {
          if (event.type === "sources") patch((m) => ({ ...m, sources: event.data }));
          if (event.type === "token") patch((m) => ({ ...m, text: m.text + event.text }));
          if (event.type === "error") throw new Error(event.message);
        }
      }
      patch((m) => ({ ...m, pending: false }));
    } catch (error) {
      if (controller.signal.aborted) return;
      patch((m) => ({ ...m, pending: false, error: error instanceof Error ? error.message : "Something went wrong." }));
    } finally {
      setBusy(false);
    }
  }, [pid, messages]);

  const stop = useCallback(() => { abort.current?.abort(); setBusy(false); setMessages((old) => old.map((m) => ({ ...m, pending: false }))); }, []);
  const clear = useCallback(() => { abort.current?.abort(); setBusy(false); setMessages([]); }, []);
  return { messages, busy, ask, stop, clear };
}
