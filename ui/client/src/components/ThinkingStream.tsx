import { useState, useEffect } from "react";
import { Brain, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";

interface ThinkingStreamProps {
  thinking: string;
  isThinking: boolean;
  stepDescription?: string;
}

export function ThinkingStream({ thinking, isThinking, stepDescription }: ThinkingStreamProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [displayText, setDisplayText] = useState("");
  
  // Typewriter effect for thinking text
  useEffect(() => {
    if (!thinking) {
      setDisplayText("");
      return;
    }
    
    // Animate text appearance
    let index = 0;
    const interval = setInterval(() => {
      if (index <= thinking.length) {
        setDisplayText(thinking.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
      }
    }, 10);
    
    return () => clearInterval(interval);
  }, [thinking]);

  return (
    <div className="bg-muted/30 rounded-lg border border-border/50 overflow-hidden mb-3">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-muted/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Brain className={cn(
            "w-4 h-4",
            isThinking ? "text-yellow-500 animate-pulse" : "text-muted-foreground"
          )} />
          <span className="text-sm font-medium">
            {isThinking ? "Thinking..." : "Reasoning"}
          </span>
          {stepDescription && (
            <span className="text-xs text-muted-foreground">
              • {stepDescription}
            </span>
          )}
        </div>
        {isExpanded ? (
          <ChevronUp className="w-4 h-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="w-4 h-4 text-muted-foreground" />
        )}
      </button>
      
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-border/30">
          <div className="mt-2 text-sm font-mono text-muted-foreground whitespace-pre-wrap">
            {displayText}
            {isThinking && (
              <span className="animate-pulse">▋</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ThinkingStream;
