import React, { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { 
  Plus, 
  MessageSquare, 
  Trash2, 
  Search, 
  Clock,
  ChevronLeft,
  ChevronRight
} from "lucide-react";
import { aetherAPI, ChatSession } from "@/lib/aether-api";
import { formatDistanceToNow } from "@/lib/utils";
import { toast } from "sonner";

interface ChatHistoryProps {
  currentSessionId?: string;
  onSessionSelect: (sessionId: string) => void;
  onNewChat: () => void;
  isOpen: boolean;
  onToggle: () => void;
}

export function ChatHistory({
  currentSessionId,
  onSessionSelect,
  onNewChat,
  isOpen,
  onToggle,
}: ChatHistoryProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  // Load sessions on mount and when they change
  useEffect(() => {
    loadSessions();
  }, []);

  const loadSessions = async () => {
    try {
      setIsLoading(true);
      const response = await aetherAPI.listChatSessions(50, 0);
      setSessions(response.sessions);
    } catch (err) {
      console.error("Failed to load chat sessions:", err);
      // Don't show toast on initial load - might just be no sessions yet
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteSession = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await aetherAPI.deleteChatSession(sessionId);
      setSessions(sessions.filter(s => s.id !== sessionId));
      toast.success("Chat deleted");
      
      // If we deleted the current session, trigger new chat
      if (sessionId === currentSessionId) {
        onNewChat();
      }
    } catch (err) {
      toast.error("Failed to delete chat");
      console.error(err);
    }
  };

  const filteredSessions = sessions.filter(session =>
    session.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      {/* Collapsed state - just show toggle button */}
      {!isOpen && (
        <div className="flex-none w-12 border-r border-border/50 bg-card/30 backdrop-blur-xl flex flex-col items-center py-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="mb-4"
          >
            <ChevronRight className="w-5 h-5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={onNewChat}
            className="mb-4"
          >
            <Plus className="w-5 h-5" />
          </Button>
          <div className="flex-1" />
        </div>
      )}

      {/* Expanded sidebar */}
      {isOpen && (
        <div className="flex-none w-72 border-r border-border/50 bg-card/30 backdrop-blur-xl flex flex-col">
          {/* Header */}
          <div className="p-4 border-b border-border/30">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Chat History</h2>
              <Button
                variant="ghost"
                size="icon"
                onClick={onToggle}
              >
                <ChevronLeft className="w-5 h-5" />
              </Button>
            </div>
            
            <Button
              onClick={onNewChat}
              className="w-full mb-3"
              variant="default"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Chat
            </Button>

            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>

          {/* Sessions list */}
          <ScrollArea className="flex-1">
            <div className="p-2 space-y-1">
              {isLoading ? (
                <div className="text-center py-4 text-muted-foreground">
                  Loading...
                </div>
              ) : filteredSessions.length === 0 ? (
                <div className="text-center py-8 text-muted-foreground">
                  {searchQuery ? "No matching chats" : "No chat history yet"}
                </div>
              ) : (
                filteredSessions.map((session) => (
                  <div
                    key={session.id}
                    onClick={() => onSessionSelect(session.id)}
                    className={cn(
                      "group flex items-center gap-3 p-3 rounded-lg cursor-pointer",
                      "hover:bg-accent/10 transition-colors",
                      currentSessionId === session.id && "bg-accent/20 border border-accent/30"
                    )}
                  >
                    <MessageSquare className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                    
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {session.title || "Untitled Chat"}
                      </p>
                      <div className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Clock className="w-3 h-3" />
                        <span>
                          {formatDistanceToNow(new Date(session.updated_at))}
                        </span>
                        <span>•</span>
                        <span>{session.message_count} messages</span>
                      </div>
                    </div>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 h-8 w-8"
                      onClick={(e) => handleDeleteSession(e, session.id)}
                    >
                      <Trash2 className="w-4 h-4 text-muted-foreground hover:text-destructive" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </ScrollArea>

          {/* Footer */}
          <div className="p-3 border-t border-border/30 text-xs text-center text-muted-foreground">
            {sessions.length} chat{sessions.length !== 1 ? "s" : ""} saved
          </div>
        </div>
      )}
    </>
  );
}

export default ChatHistory;
