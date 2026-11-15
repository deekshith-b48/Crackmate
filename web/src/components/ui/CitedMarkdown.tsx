"use client";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";

/** Turns [1] markers into small buttons. The model can only cite numbers it was given, and any other number does nothing. */
export function CitedMarkdown({ children, count, onCite }: { children: string; count: number; onCite: (n: number) => void }) {
  const text = children.replace(/\[(\d{1,2})\]/g, (whole, n) => (Number(n) >= 1 && Number(n) <= count ? `[${n}](#cite-${n})` : whole));
  return (
    <div className="prose-lesson">
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          img: () => null,
          a: ({ href, children: label }) => href?.startsWith("#cite-")
            ? <button type="button" onClick={() => onCite(Number(href.slice(6)))} className="mx-0.5 inline-flex size-5 -translate-y-px items-center justify-center rounded-md bg-brand-50 align-middle text-[11px] font-semibold text-brand-700 hover:bg-brand-100" aria-label={`Show source ${label}`}>{label}</button>
            : <a href={href} target="_blank" rel="noreferrer noopener" className="text-brand-600 underline underline-offset-2">{label}</a>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
