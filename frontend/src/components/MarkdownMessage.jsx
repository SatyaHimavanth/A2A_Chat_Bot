import rehypeRaw from 'rehype-raw'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

export default function MarkdownMessage({ content = '' }) {
  return (
    <div className="markdown-message text-[0.95rem] break-words leading-relaxed text-slate-700 dark:text-slate-200 font-medium">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold mt-1 mb-3 text-slate-900 dark:text-slate-50">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-bold mt-1 mb-3 text-slate-900 dark:text-slate-50">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-bold mt-1 mb-2 text-slate-900 dark:text-slate-50">{children}</h3>,
          h4: ({ children }) => <h4 className="text-sm font-bold mt-1 mb-2 text-slate-900 dark:text-slate-50">{children}</h4>,
          p: ({ children }) => <p className="mb-3 last:mb-0 whitespace-pre-wrap">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          strong: ({ children }) => <strong className="font-bold text-slate-900 dark:text-slate-50">{children}</strong>,
          em: ({ children }) => <em className="italic">{children}</em>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-slate-300 dark:border-slate-600 pl-4 py-1 mb-3 text-slate-600 dark:text-slate-300">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline underline-offset-2 hover:text-primary-hover"
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto mb-3 rounded-xl border border-cardBorder">
              <table className="min-w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-100/80 dark:bg-slate-800/80">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-cardBorder last:border-b-0">{children}</tr>,
          th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-900 dark:text-slate-100">{children}</th>,
          td: ({ children }) => <td className="px-3 py-2 align-top">{children}</td>,
          code: ({ inline, children }) =>
            inline ? (
              <code className="rounded-md bg-slate-200/80 dark:bg-slate-800 px-1.5 py-0.5 text-[0.85em] font-mono">
                {children}
              </code>
            ) : (
              <code className="block overflow-x-auto rounded-xl bg-slate-900 text-slate-100 p-3 text-sm font-mono">
                {children}
              </code>
            ),
          pre: ({ children }) => <pre className="mb-3">{children}</pre>,
          hr: () => <hr className="my-4 border-slate-300 dark:border-slate-700" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
