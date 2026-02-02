import { useState, useRef, useEffect } from "react";
import { useAetherWebSocket } from "@/hooks/useAetherWebSocket";
import { useVoiceServices } from "@/hooks/useVoiceServices";
import { aetherAPI } from "@/lib/aether-api";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

import {
  Send,
  Paperclip,
  Settings,
  Terminal as TerminalIcon,
  Zap,
  Shield,
  Minimize2,
  Sparkles,
  Database,
  Mic,
  Check,
  Volume2,
  VolumeX,
  Brain,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

// Extended message interface with thinking support
interface DisplayMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  thinking?: string;
  timestamp: Date;
  streaming?: boolean;
}

// Component for collapsible thinking block
function ThinkingBlock({ thinking }: { thinking: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className="mt-2">
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs font-medium text-muted-foreground hover:text-foreground bg-muted/30 hover:bg-muted/50 border border-border/30 rounded-md"
        >
          <Brain className="w-3.5 h-3.5 mr-1.5 text-accent" />
          Thinking
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5 ml-1" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5 ml-1" />
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: "auto" }}
          exit={{ opacity: 0, height: 0 }}
          className="mt-2 p-3 bg-muted/20 border border-border/30 rounded-md"
        >
          <ScrollArea className="max-h-48">
            <p className="text-xs text-muted-foreground font-mono leading-relaxed whitespace-pre-wrap">
              {thinking}
            </p>
          </ScrollArea>
        </motion.div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export default function AetherPanel() {
  // Use WebSocket for real-time chat
  const { messages: wsMessages, sendMessage, isConnected, error: wsError } = useAetherWebSocket();
  
  const [input, setInput] = useState("");
  const [isAutoMode, setIsAutoMode] = useState(false);
  const [contextUsage, setContextUsage] = useState(42);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Voice services
  const {
    isRecording,
    startRecording,
    stopRecording,
    audioLevel,
    isTTSEnabled,
    toggleTTS,
    speak,
    isSpeaking,
  } = useVoiceServices({
    asrEndpoint: import.meta.env.VITE_ASR_ENDPOINT || "http://localhost:8001/asr",
    ttsEndpoint: import.meta.env.VITE_TTS_ENDPOINT || "http://localhost:8002/tts",
  });
  
  // Convert WebSocket messages to local format with thinking support
  const messages: DisplayMessage[] = wsMessages.map(msg => ({
    ...msg,
    timestamp: new Date(msg.timestamp),
  }));
  
  // Speak agent messages when TTS is enabled
  useEffect(() => {
    if (isTTSEnabled && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === "agent" && !isSpeaking) {
        speak(lastMessage.content);
      }
    }
  }, [messages, isTTSEnabled, speak, isSpeaking]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = () => {
    if (!input.trim()) return;
    
    if (!isConnected) {
      toast.error("Not connected to Aether agent");
      return;
    }

    sendMessage(input);
    setInput("");
  };
  
  // Handle voice recording
  const handleMicClick = async () => {
    if (isRecording) {
      // Stop recording and transcribe
      try {
        const transcription = await stopRecording();
        if (transcription) {
          setInput(transcription);
          toast.success("Speech transcribed");
        }
      } catch (error) {
        toast.error("Failed to transcribe speech");
        console.error(error);
      }
    } else {
      // Start recording
      try {
        await startRecording();
        toast.info("Recording... Click checkmark when done");
      } catch (error) {
        toast.error("Failed to access microphone");
        console.error(error);
      }
    }
  };
  
  // Fetch context stats periodically
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const stats = await aetherAPI.getContextStats();
        setContextUsage(Math.round(stats.usage_percent));
      } catch (err) {
        console.error("Failed to fetch context stats:", err);
      }
    };
    
    fetchStats();
    const interval = setInterval(fetchStats, 5000);
    return () => clearInterval(interval);
  }, []);
  
  // Handle mode toggle
  const handleModeToggle = async (checked: boolean) => {
    try {
      await aetherAPI.setMode(checked ? "auto" : "semi");
      setIsAutoMode(checked);
      toast.success(`Switched to ${checked ? "Autonomous" : "Semi-Autonomous"} mode`);
    } catch (err) {
      toast.error("Failed to change mode");
      console.error(err);
    }
  };
  
  // Handle context compression
  const handleCompressContext = async () => {
    try {
      await aetherAPI.compressContext();
      toast.success("Context compressed successfully");
      // Refresh stats
      const stats = await aetherAPI.getContextStats();
      setContextUsage(Math.round(stats.usage_percent));
    } catch (err) {
      toast.error("Failed to compress context");
      console.error(err);
    }
  };

  return (
    <div className="fixed inset-0 flex flex-col bg-gradient-to-b from-background to-card">
      {/* Header - Fixed at top */}
      <div className="flex-none flex items-center justify-between p-4 border-b border-border/50 backdrop-blur-xl bg-card/50">
        <div className="flex items-center gap-3">
          <div className="relative">
            <Sparkles className="w-6 h-6 text-primary" />
            <div className="absolute inset-0 blur-lg bg-primary/30 animate-pulse" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-foreground">Aether</h1>
            <p className="text-xs text-muted-foreground">AI Assistant</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className={cn(
            "text-xs",
            isConnected ? "border-primary/30 text-primary" : "border-destructive/30 text-destructive"
          )}>
            <div className={cn(
              "w-2 h-2 rounded-full mr-1.5",
              isConnected ? "bg-primary animate-pulse" : "bg-destructive"
            )} />
            {isConnected ? "Online" : "Offline"}
          </Badge>
        </div>
      </div>

      {/* Chat Messages - Scrollable middle area */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ScrollArea className="h-full p-4" ref={scrollRef}>
          <AnimatePresence>
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.25 }}
                className={cn(
                  "mb-4 flex",
                  message.role === "user" ? "justify-end" : "justify-start"
                )}
              >
                <div
                  className={cn(
                    "max-w-[85%] rounded-2xl px-4 py-3 backdrop-blur-xl",
                    message.role === "user"
                      ? "bg-primary/20 border border-primary/30 shadow-lg shadow-primary/10"
                      : "bg-card/50 border border-border/30"
                  )}
                >
                  <p className="text-sm text-foreground leading-relaxed whitespace-pre-wrap">
                    {message.content}
                  </p>
                  
                  {/* Thinking block for agent messages */}
                  {message.role === "agent" && message.thinking && (
                    <ThinkingBlock thinking={message.thinking} />
                  )}
                  
                  <p className="text-xs text-muted-foreground mt-1.5">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </ScrollArea>
      </div>

      {/* Bottom Controls - Fixed at bottom */}
      <div className="flex-none border-t border-border/50 backdrop-blur-xl bg-card/30">
        {/* Input Area */}
        <div className="p-4">
          <div className="flex items-end gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="shrink-0 hover:bg-accent/20 hover:text-accent"
            >
              <Paperclip className="w-5 h-5" />
            </Button>
            
            {/* Voice input button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={handleMicClick}
              className={cn(
                "shrink-0 relative",
                isRecording
                  ? "bg-destructive/20 hover:bg-destructive/30 text-destructive"
                  : "hover:bg-accent/20 hover:text-accent"
              )}
            >
              {isRecording ? (
                <>
                  <Check className="w-5 h-5" />
                  {/* Audio level indicator */}
                  <div
                    className="absolute inset-0 rounded-md bg-destructive/20"
                    style={{
                      opacity: audioLevel,
                      transform: `scale(${1 + audioLevel * 0.2})`,
                      transition: "all 0.1s ease-out",
                    }}
                  />
                </>
              ) : (
                <Mic className="w-5 h-5" />
              )}
            </Button>
            
            {/* TTS toggle button */}
            <Button
              variant="ghost"
              size="icon"
              onClick={toggleTTS}
              className={cn(
                "shrink-0",
                isTTSEnabled
                  ? "bg-accent/20 hover:bg-accent/30 text-accent"
                  : "hover:bg-muted/20 text-muted-foreground"
              )}
            >
              {isTTSEnabled ? (
                <Volume2 className="w-5 h-5" />
              ) : (
                <VolumeX className="w-5 h-5" />
              )}
            </Button>
            
            <div className="flex-1 relative">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder={isRecording ? "Recording..." : "Message Aether..."}
                className="pr-12 bg-input/50 border-border/50 focus:border-primary/50 focus:ring-primary/20 backdrop-blur-sm"
                disabled={isRecording}
              />
            </div>
            <Button
              onClick={handleSend}
              size="icon"
              className="shrink-0 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20"
              disabled={isRecording}
            >
              <Send className="w-5 h-5" />
            </Button>
          </div>
        </div>

        <Separator className="bg-border/30" />

        {/* Mode Selector */}
        <div className="p-4 backdrop-blur-xl bg-card/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {isAutoMode ? (
                <Zap className="w-5 h-5 text-accent" />
              ) : (
                <Shield className="w-5 h-5 text-primary" />
              )}
              <div>
                <p className="text-sm font-medium text-foreground">
                  {isAutoMode ? "Autonomous" : "Semi-Autonomous"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {isAutoMode ? "Full automation" : "Approval required"}
                </p>
              </div>
            </div>
            <Switch checked={isAutoMode} onCheckedChange={handleModeToggle} />
          </div>
        </div>

        <Separator className="bg-border/30" />

        {/* Context Gauge */}
        <div className="p-4 backdrop-blur-xl bg-card/20">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Database className="w-4 h-4 text-muted-foreground" />
              <p className="text-sm font-medium text-foreground">Context Usage</p>
            </div>
            <p className="text-sm font-mono text-muted-foreground">{contextUsage}%</p>
          </div>
          <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted/30">
            <div
              className={cn(
                "h-full transition-all duration-500",
                contextUsage > 80 ? "bg-destructive" : contextUsage > 60 ? "bg-accent" : "bg-success"
              )}
              style={{ width: `${contextUsage}%` }}
            />
          </div>
          {contextUsage > 80 && (
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-3 border-accent/30 text-accent hover:bg-accent/10"
              onClick={handleCompressContext}
            >
              Compress Context
            </Button>
          )}
        </div>

        <Separator className="bg-border/30" />

        {/* Quick Actions */}
        <div className="p-4 backdrop-blur-xl bg-card/20 flex gap-2">
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-border/50 hover:bg-accent/10 hover:border-accent/30"
            onClick={() => setTerminalOpen(!terminalOpen)}
          >
            <TerminalIcon className="w-4 h-4 mr-2" />
            Terminal
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="flex-1 border-border/50 hover:bg-primary/10 hover:border-primary/30"
            onClick={() => setSettingsOpen(!settingsOpen)}
          >
            <Settings className="w-4 h-4 mr-2" />
            Settings
          </Button>
        </div>

        {/* Terminal (Collapsible) */}
        <AnimatePresence>
          {terminalOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 200, opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.3 }}
              className="border-t border-border/50 backdrop-blur-xl bg-black/40 overflow-hidden"
            >
              <div className="p-4 h-full">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-xs font-mono text-muted-foreground">Terminal Output</p>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => setTerminalOpen(false)}
                  >
                    <Minimize2 className="w-4 h-4" />
                  </Button>
                </div>
                <ScrollArea className="h-[calc(100%-2rem)] font-mono text-xs text-green-400">
                  <div className="space-y-1">
                    <p>$ aether status</p>
                    <p className="text-muted-foreground">Agent: Running</p>
                    <p className="text-muted-foreground">Memory: 42% used</p>
                    <p className="text-muted-foreground">Mode: Semi-Autonomous</p>
                    <p className="text-green-500">✓ All systems operational</p>
                  </div>
                </ScrollArea>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
