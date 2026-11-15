"use client";
import { useEffect, useId, useRef, useState } from "react";
import { useTheme } from "@/lib/theme";

/** Renders Mermaid at its strict security level. Models sometimes write bad syntax, so errors fall back to the source. */
export function Mermaid({ source }: { source: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const id = "m" + useId().replace(/[^a-zA-Z0-9]/g, "");
  const [error, setError] = useState("");
  const { theme } = useTheme();
  useEffect(() => {
    let cancelled = false;
    setError("");
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: theme === "dark" ? "dark" : "neutral", fontFamily: "Inter Variable, system-ui, sans-serif" });
        const { svg } = await mermaid.render(id, source);
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      } catch {
        if (!cancelled) setError("This diagram could not be drawn. Open the source below to fix it or paste it into mermaid.live.");
      }
    })();
    return () => { cancelled = true; };
  }, [source, id, theme]);
  return (
    <div>
      {error ? <p role="alert" className="rounded-[var(--radius-control)] bg-warn-tint p-3 text-sm text-warn">{error}</p> : <div ref={ref} className="flex justify-center overflow-x-auto [&_svg]:h-auto [&_svg]:max-w-full" />}
    </div>
  );
}
