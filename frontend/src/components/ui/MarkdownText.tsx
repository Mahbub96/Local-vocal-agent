import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type MarkdownTextProps = {
  text: string;
  className?: string;
};

export function MarkdownText({ text, className = "" }: MarkdownTextProps) {
  return (
    <div className={`markdown-body text-sm leading-relaxed text-white/88 ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-2 list-disc pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-2 list-decimal pl-5">{children}</ol>,
          li: ({ children }) => <li className="mb-1">{children}</li>,
          code: ({ children, className: codeClass }) => {
            const inline = !codeClass;
            if (inline) {
              return (
                <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[0.92em]">
                  {children}
                </code>
              );
            }
            return (
              <code className="block overflow-x-auto whitespace-pre rounded-lg bg-black/35 p-3 font-mono text-[0.9em]">
                {children}
              </code>
            );
          },
          pre: ({ children }) => <pre className="mb-2">{children}</pre>,
          table: ({ children }) => (
            <div className="mb-2 overflow-x-auto">
              <table className="min-w-full border-collapse text-left text-[0.92em]">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-white/20 bg-white/8 px-2 py-1 font-semibold">{children}</th>
          ),
          td: ({ children }) => <td className="border border-white/20 px-2 py-1">{children}</td>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer" className="text-cyan-300 underline">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="mb-2 border-l-2 border-cyan-400/50 pl-3 text-white/80">
              {children}
            </blockquote>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
