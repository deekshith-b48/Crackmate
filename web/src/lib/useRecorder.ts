"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { TARGET_RATE, downsample, encodeWav } from "./wav";

const WORKLET = `class Rec extends AudioWorkletProcessor { process(inputs) { const ch = inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; } } registerProcessor("rec", Rec);`;

export type Recording = { blob: Blob; url: string; seconds: number };

/** Records the microphone and returns a 16 kHz mono WAV. Stops by itself at maxSeconds. */
export function useRecorder(maxSeconds: number) {
  const [state, setState] = useState<"idle" | "recording">("idle");
  const [level, setLevel] = useState(0);
  const [seconds, setSeconds] = useState(0);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [error, setError] = useState("");
  const chunks = useRef<Float32Array[]>([]);
  const cleanup = useRef<() => void>(() => {});
  const rate = useRef(48000);

  const finish = useCallback(() => {
    cleanup.current();
    cleanup.current = () => {};
    setState("idle");
    setLevel(0);
    const total = chunks.current.reduce((n, c) => n + c.length, 0);
    if (!total) return;
    const joined = new Float32Array(total);
    let offset = 0;
    for (const c of chunks.current) { joined.set(c, offset); offset += c.length; }
    chunks.current = [];
    const wav = encodeWav(downsample(joined, rate.current, TARGET_RATE), Math.min(rate.current, TARGET_RATE));
    const blob = new Blob([wav.buffer as ArrayBuffer], { type: "audio/wav" });
    setRecording({ blob, url: URL.createObjectURL(blob), seconds: Math.round(total / rate.current) });
  }, []);

  const start = useCallback(async () => {
    setError("");
    setRecording(null);
    chunks.current = [];
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const context = new AudioContext();
      rate.current = context.sampleRate;
      const source = context.createMediaStreamSource(stream);
      const onChunk = (data: Float32Array) => {
        chunks.current.push(data);
        let sum = 0;
        for (const v of data) sum += v * v;
        setLevel(Math.min(1, Math.sqrt(sum / data.length) * 6));
      };
      let node: AudioNode;
      if (context.audioWorklet) {
        const url = URL.createObjectURL(new Blob([WORKLET], { type: "application/javascript" }));
        await context.audioWorklet.addModule(url);
        URL.revokeObjectURL(url);
        const worklet = new AudioWorkletNode(context, "rec");
        worklet.port.onmessage = (e) => onChunk(e.data);
        node = worklet;
      } else {
        const legacy = context.createScriptProcessor(4096, 1, 1);
        legacy.onaudioprocess = (e) => onChunk(new Float32Array(e.inputBuffer.getChannelData(0)));
        node = legacy;
      }
      source.connect(node);
      node.connect(context.destination);
      const begun = Date.now();
      const timer = setInterval(() => {
        const elapsed = Math.floor((Date.now() - begun) / 1000);
        setSeconds(elapsed);
        if (elapsed >= maxSeconds) finish();
      }, 250);
      cleanup.current = () => {
        clearInterval(timer);
        source.disconnect();
        node.disconnect();
        stream.getTracks().forEach((t) => t.stop());
        context.close();
      };
      setSeconds(0);
      setState("recording");
    } catch {
      setError("The microphone is not available. Check your browser permission, or type your answer or upload a WAV instead.");
    }
  }, [finish, maxSeconds]);

  const reset = useCallback(() => {
    if (recording) URL.revokeObjectURL(recording.url);
    setRecording(null);
  }, [recording]);

  useEffect(() => () => cleanup.current(), []);
  return { state, level, seconds, recording, error, start, stop: finish, reset };
}
