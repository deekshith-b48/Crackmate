"use client";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";

/** Model text is untrusted: sanitised, and images are dropped so the browser never fetches remote pictures. */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="prose-lesson">
      <ReactMarkdown
        rehypePlugins={[rehypeSanitize]}
        components={{
          img: () => null,
          a: ({ href, children: label }) => <a href={href} target="_blank" rel="noreferrer noopener" className="text-brand-600 underline underline-offset-2">{label}</a>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
