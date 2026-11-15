"use client";
import { Square, Volume2 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";

/** Reads a question aloud with the browser's own voices. Stop it before you record. */
export function SpeechPlayer({ text }: { text: string }) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voice, setVoice] = useState(0);
  const [rate, setRate] = useState(1);
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => {
    const synth = window.speechSynthesis;
    if (!synth) return;
    const load = () => setVoices(synth.getVoices().filter((v) => v.lang.startsWith("en")));
    load();
    synth.addEventListener("voiceschanged", load);
    return () => { synth.removeEventListener("voiceschanged", load); synth.cancel(); };
  }, []);
  useEffect(() => { window.speechSynthesis?.cancel(); setSpeaking(false); }, [text]);

  if (typeof window !== "undefined" && !window.speechSynthesis) return <p className="text-sm text-muted">Speech is unavailable in this browser. Read the question above.</p>;
  function toggle() {
    const synth = window.speechSynthesis;
    if (speaking) { synth.cancel(); setSpeaking(false); return; }
    const utterance = new SpeechSynthesisUtterance(text);
    if (voices[voice]) utterance.voice = voices[voice];
    utterance.rate = rate;
    utterance.onend = utterance.onerror = () => setSpeaking(false);
    synth.speak(utterance);
    setSpeaking(true);
  }
  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button size="sm" onClick={toggle}>{speaking ? <><Square className="size-4" /> Stop</> : <><Volume2 className="size-4" /> Hear the question</>}</Button>
      {voices.length > 1 && <select aria-label="Voice" value={voice} onChange={(e) => setVoice(Number(e.target.value))} className="h-8 max-w-48 rounded-[var(--radius-control)] border border-line bg-surface px-2 text-xs">{voices.map((v, i) => <option key={v.name} value={i}>{v.name}</option>)}</select>}
      <label className="flex items-center gap-2 text-xs text-muted">Speed<input type="range" min={0.6} max={1.4} step={0.1} value={rate} onChange={(e) => setRate(Number(e.target.value))} className="w-24 accent-[var(--color-brand-600)]" /></label>
    </div>
  );
}
