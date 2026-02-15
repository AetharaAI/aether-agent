import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn("prose prose-sm dark:prose-invert max-w-none", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={{
          // Code blocks with syntax highlighting
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || "");
            const language = match ? match[1] : "";

            return !inline && language ? (
              <div className="relative group my-4">
                <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(String(children).replace(/\n$/, ""));
                    }}
                    className="px-2 py-1 text-xs bg-muted hover:bg-muted/80 rounded text-foreground"
                  >
                    Copy
                  </button>
                </div>
                <SyntaxHighlighter
                  style={oneDark}
                  language={language}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: "0.5rem",
                    fontSize: "0.875rem",
                  }}
                  {...props as any}
                >
                  {String(children).replace(/\n$/, "")}
                </SyntaxHighlighter>
              </div>
            ) : (
              <code
                className={cn(
                  "px-1.5 py-0.5 rounded bg-muted font-mono text-sm",
                  className
                )}
                {...props as any}
              >
                {children}
              </code>
            );
          },

          // Headings
          h1: ({ children }: any) => (
            <h1 className="text-2xl font-bold mt-6 mb-4">{children}</h1>
          ),
          h2: ({ children }: any) => (
            <h2 className="text-xl font-bold mt-5 mb-3">{children}</h2>
          ),
          h3: ({ children }: any) => (
            <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>
          ),

          // Lists
          ul: ({ children }: any) => (
            <ul className="list-disc list-outside ml-4 my-3 space-y-1">
              {children}
            </ul>
          ),
          ol: ({ children }: any) => (
            <ol className="list-decimal list-outside ml-4 my-3 space-y-1">
              {children}
            </ol>
          ),
          li: ({ children }: any) => <li className="leading-relaxed">{children}</li>,

          // Paragraphs
          p: ({ children }: any) => <p className="my-2 leading-relaxed">{children}</p>,

          // Links
          a: ({ href, children }: any) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              {children}
            </a>
          ),

          // Blockquotes
          blockquote: ({ children }: any) => (
            <blockquote className="border-l-4 border-primary/50 pl-4 py-1 my-3 italic text-muted-foreground">
              {children}
            </blockquote>
          ),

          // Tables
          table: ({ children }: any) => (
            <div className="my-4 overflow-x-auto">
              <table className="w-full border-collapse border border-border rounded">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }: any) => (
            <thead className="bg-muted">{children}</thead>
          ),
          tbody: ({ children }: any) => <tbody>{children}</tbody>,
          tr: ({ children }: any) => (
            <tr className="border-b border-border">{children}</tr>
          ),
          th: ({ children }: any) => (
            <th className="px-4 py-2 text-left font-semibold">{children}</th>
          ),
          td: ({ children }: any) => (
            <td className="px-4 py-2">{children}</td>
          ),

          // Horizontal rule
          hr: () => <hr className="my-6 border-border" />,

          // Strong/Bold
          strong: ({ children }: any) => <strong className="font-semibold">{children}</strong>,

          // Emphasis/Italic
          em: ({ children }: any) => <em className="italic">{children}</em>,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownRenderer;
