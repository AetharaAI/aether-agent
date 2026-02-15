"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { Brain, User, Bot, ChevronDown, ChevronUp, FileText, Image } from "lucide-react";
import { MarkdownRenderer } from "./MarkdownRenderer";
import type { Attachment } from "@/hooks/useAgentRuntime";

interface ChatBubbleProps {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  timestamp?: string;
  attachments?: Attachment[];
}

export function ChatBubble({ role, content, thinking, timestamp, attachments }: ChatBubbleProps) {
  const [showThinking, setShowThinking] = useState(false);
  const isUser = role === "user";

  const formatTime = (ts: string) => {
    try {
      return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  };

  return (
    <div className={cn(
      "flex gap-4",
      isUser ? "flex-row-reverse" : "flex-row"
    )}>
      {/* Avatar */}
      <div className={cn(
        "w-8 h-8 rounded-full flex items-center justify-center shrink-0 mt-1",
        isUser ? "bg-primary text-primary-foreground" : "bg-muted border border-border"
      )}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>

      {/* Content */}
      <div className={cn(
        "flex-1 min-w-0 max-w-[85%]",
        isUser ? "items-end" : "items-start"
      )}>
        {/* Message bubble */}
        <div className={cn(
          "rounded-2xl px-4 py-3",
          isUser 
            ? "bg-primary text-primary-foreground" 
            : "bg-muted/50 border border-border/50"
        )}>
          {/* Attachments */}
          {attachments && attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {attachments.map((att, i) => (
                <AttachmentChip key={i} attachment={att} isUser={isUser} />
              ))}
            </div>
          )}

          {/* Content */}
          {isUser ? (
            <div className={cn(
              "text-sm leading-relaxed whitespace-pre-wrap",
              "text-primary-foreground"
            )}>
              {content}
            </div>
          ) : (
            <MarkdownRenderer
              content={content}
              className="text-sm text-foreground"
            />
          )}
        </div>

        {/* Thinking block (only for assistant) */}
        {!isUser && thinking && (
          <div className="mt-2">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors px-1"
            >
              <Brain className="w-3 h-3" />
              <span>Reasoning</span>
              {showThinking ? (
                <ChevronUp className="w-3 h-3" />
              ) : (
                <ChevronDown className="w-3 h-3" />
              )}
            </button>
            
            {showThinking && (
              <div className="mt-2 p-3 bg-muted/30 rounded-lg border border-border/50">
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                  {thinking}
                </pre>
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        {timestamp && (
          <span className="text-[10px] text-muted-foreground mt-1 block px-1">
            {formatTime(timestamp)}
          </span>
        )}
      </div>
    </div>
  );
}

function AttachmentChip({ attachment, isUser }: { attachment: Attachment; isUser: boolean }) {
  const isImage = attachment.mime_type?.startsWith("image/");

  return (
    <div className={cn(
      "flex items-center gap-1.5 px-2 py-1 rounded text-xs",
      isUser ? "bg-primary-foreground/20" : "bg-background/50"
    )}>
      {isImage ? (
        <Image className="w-3 h-3" />
      ) : (
        <FileText className="w-3 h-3" />
      )}
      <span className="truncate max-w-[150px]">
        {attachment.filename || "Attachment"}
      </span>
    </div>
  );
}

export default ChatBubble;
