import React from "react";
import { Brain, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface ThinkingBlockProps {
  thinking: string;
  defaultOpen?: boolean;
}

/**
 * ThinkingBlock - Collapsible component for displaying model reasoning
 * 
 * Uses shadcn Collapsible component for smooth expand/collapse animations.
 * Shows reasoning/thinking content from models like Qwen3 that use <think> tags.
 */
export function ThinkingBlock({ thinking, defaultOpen = false }: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  if (!thinking || thinking.trim().length === 0) {
    return null;
  }

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className="mb-3">
      <div className="rounded-lg border border-border/50 bg-muted/30 overflow-hidden">
        <CollapsibleTrigger asChild>
          <button
            className={cn(
              "flex w-full items-center justify-between px-3 py-2 text-xs",
              "hover:bg-muted/50 transition-colors",
              "focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            )}
          >
            <div className="flex items-center gap-2 text-muted-foreground">
              <Brain className="h-3.5 w-3.5 text-accent" />
              <span>Model reasoning</span>
              <span className="text-[10px] opacity-60">
                ({isOpen ? "click to collapse" : "click to expand"})
              </span>
            </div>
            <ChevronDown
              className={cn(
                "h-4 w-4 text-muted-foreground transition-transform duration-200",
                isOpen && "rotate-180"
              )}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent className="CollapsibleContent">
          <div className="border-t border-border/30 bg-black/20">
            <div className="max-h-48 overflow-y-auto p-3">
              <pre className="text-xs font-mono leading-relaxed text-accent/80 whitespace-pre-wrap break-words">
                {thinking}
              </pre>
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
}

export default ThinkingBlock;
