import { writeFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { downsample, encodeWav } from "./wav";

const sine = (seconds: number, rate: number) => Float32Array.from({ length: seconds * rate }, (_, i) => 0.5 * Math.sin((2 * Math.PI * 440 * i) / rate));

describe("wav", () => {
  it("writes a valid 16 kHz mono PCM header", () => {
    const bytes = encodeWav(downsample(sine(1, 48000), 48000, 16000), 16000);
    const view = new DataView(bytes.buffer);
    const ascii = (o: number) => String.fromCharCode(...bytes.slice(o, o + 4));
    expect([ascii(0), ascii(8), ascii(12), ascii(36)]).toEqual(["RIFF", "WAVE", "fmt ", "data"]);
    expect(view.getUint16(22, true)).toBe(1); // mono
    expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(34, true)).toBe(16); // bits
    expect(view.getUint32(40, true)).toBe(16000 * 2); // one second of samples
    expect(bytes.length).toBe(44 + 32000);
    if (process.env.WAV_OUT) writeFileSync(process.env.WAV_OUT, bytes); // lets a Python check read the same bytes
  });

  it("clamps loud samples instead of wrapping", () => {
    const view = new DataView(encodeWav(Float32Array.of(2, -2), 16000).buffer);
    expect([view.getInt16(44, true), view.getInt16(46, true)]).toEqual([32767, -32767]);
  });

  it("leaves audio alone when already at or below the target rate", () => {
    const input = sine(1, 8000);
    expect(downsample(input, 8000, 16000)).toBe(input);
  });
});
