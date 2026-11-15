import { describe, expect, it } from "vitest";
import { createLineParser } from "./stream";

describe("createLineParser", () => {
  it("joins a line split across chunks and skips junk", () => {
    const parse = createLineParser();
    expect(parse('{"type":"step","te')).toEqual([]);
    expect(parse('xt":"one"}\n{"type":"ping"}\nnot json\n{"type":"res')).toEqual([
      { type: "step", text: "one" },
      { type: "ping" },
    ]);
    expect(parse('ult","data":{"ok":true}}\n')).toEqual([{ type: "result", data: { ok: true } }]);
  });
});
