import ReactMarkdown from "react-markdown";

/**
 * Safe Markdown renderer for AI Coach chat responses.
 *
 * react-markdown without rehype-raw escapes raw HTML, so arbitrary markup
 * from the model can never inject executable content.
 */
export function Markdown({ content }: { content: string }) {
  return (
    <div className="text-body space-y-2">
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="whitespace-pre-wrap">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
          em: ({ children }) => <em className="italic">{children}</em>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          h1: ({ children }) => <h1 className="text-card-title pt-1">{children}</h1>,
          h2: ({ children }) => <h2 className="text-card-title pt-1">{children}</h2>,
          h3: ({ children }) => <h3 className="text-body font-semibold pt-1">{children}</h3>,
          code: ({ children }) => (
            <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-caption">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="overflow-x-auto rounded-xl bg-muted p-3 font-mono text-caption">
              {children}
            </pre>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-violet underline underline-offset-2"
            >
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border pl-3 text-muted-foreground">
              {children}
            </blockquote>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
