import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

/**
 * MarkdownRenderer - Renders markdown content with GitHub Flavored Markdown support
 * 
 * Features:
 * - Bold, italic, strikethrough text
 * - Headers (H1-H6)
 * - Lists (ordered, unordered, task lists)
 * - Code blocks with syntax highlighting
 * - Inline code
 * - Tables
 * - Links
 * - Blockquotes
 * - Horizontal rules
 */
export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn("markdown-body prose prose-sm prose-invert max-w-none", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Custom styling for code blocks
          code({ className: codeClassName, children, ...props }) {
            const match = /language-(\w+)/.exec(codeClassName || "");
            const isInline = !codeClassName?.includes("language-");
            
            if (isInline) {
              return (
                <code
                  className="px-1.5 py-0.5 rounded bg-muted/50 text-accent text-sm font-mono"
                  {...props}
                >
                  {children}
                </code>
              );
            }
            
            return (
              <div className="relative group my-3">
                {match && (
                  <div className="absolute top-0 right-0 px-2 py-1 text-xs text-muted-foreground bg-muted/50 rounded-bl">
                    {match[1]}
                  </div>
                )}
                <pre className="p-4 rounded-lg bg-muted/30 border border-border/30 overflow-x-auto">
                  <code className={cn("text-sm font-mono", codeClassName)} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            );
          },
          // Style blockquotes
          blockquote({ children }) {
            return (
              <blockquote className="border-l-4 border-primary/30 pl-4 italic text-muted-foreground my-3">
                {children}
              </blockquote>
            );
          },
          // Style links
          a({ children, href, ...props }) {
            return (
              <a
                href={href}
                className="text-accent hover:text-accent/80 underline underline-offset-2 transition-colors"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
          // Style tables
          table({ children }) {
            return (
              <div className="overflow-x-auto my-3">
                <table className="w-full border-collapse text-sm">
                  {children}
                </table>
              </div>
            );
          },
          thead({ children }) {
            return <thead className="bg-muted/50">{children}</thead>;
          },
          th({ children }) {
            return (
              <th className="border border-border/30 px-3 py-2 text-left font-semibold">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="border border-border/30 px-3 py-2">
                {children}
              </td>
            );
          },
          // Style horizontal rules
          hr() {
            return <hr className="my-4 border-border/30" />;
          },
          // Style headings
          h1({ children }) {
            return <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="text-xl font-semibold mt-5 mb-2">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>;
          },
          h4({ children }) {
            return <h4 className="text-base font-semibold mt-3 mb-1">{children}</h4>;
          },
          h5({ children }) {
            return <h5 className="text-sm font-semibold mt-2 mb-1">{children}</h5>;
          },
          h6({ children }) {
            return <h6 className="text-xs font-semibold mt-2 mb-1 text-muted-foreground">{children}</h6>;
          },
          // Style lists
          ul({ children }) {
            return <ul className="list-disc pl-6 my-2 space-y-1">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="list-decimal pl-6 my-2 space-y-1">{children}</ol>;
          },
          li({ children }) {
            return <li className="leading-relaxed">{children}</li>;
          },
          // Style paragraphs
          p({ children }) {
            return <p className="leading-relaxed mb-2 last:mb-0">{children}</p>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default MarkdownRenderer;
