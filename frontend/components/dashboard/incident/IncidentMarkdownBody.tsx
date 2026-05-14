"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function safeUrl(href: string): string {
  const t = href.trim();
  if (!t) {
    return "";
  }
  const lower = t.toLowerCase();
  if (lower.startsWith("javascript:") || lower.startsWith("data:")) {
    return "";
  }
  return href;
}

export function IncidentMarkdownBody({ markdown }: { markdown: string }) {
  return (
    <div className="incident-md max-w-none text-sm leading-relaxed text-slate-800 dark:text-neutral-200 [&_a]:text-orange-700 [&_a]:underline [&_a]:underline-offset-2 dark:[&_a]:text-orange-300 [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:text-xs dark:[&_code]:bg-neutral-800 [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mt-2 [&_h3]:text-sm [&_h3]:font-semibold [&_li]:my-0.5 [&_ol]:my-1 [&_ol]:list-decimal [&_ol]:pl-5 [&_p]:my-1.5 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:border-slate-200 [&_pre]:bg-slate-50 [&_pre]:p-2 [&_pre]:text-xs dark:[&_pre]:border-neutral-700 dark:[&_pre]:bg-neutral-950 [&_table]:w-full [&_table]:border-collapse [&_td]:border [&_td]:border-slate-200 [&_td]:px-2 [&_td]:py-1 dark:[&_td]:border-neutral-700 [&_th]:border [&_th]:border-slate-200 [&_th]:px-2 [&_th]:py-1 [&_th]:text-left dark:[&_th]:border-neutral-700 [&_ul]:my-1 [&_ul]:list-disc [&_ul]:pl-5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children, ...props }) => (
            <a href={safeUrl(href ?? "") || undefined} target="_blank" rel="noopener noreferrer" {...props}>
              {children}
            </a>
          ),
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
