"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import { cn } from "@/lib/utils";
import { useAgentRuntime, Attachment } from "@/hooks/useAgentRuntime";
import { PlanSteps } from "./PlanSteps";
import { ThinkingStream } from "./ThinkingStream";
import { ToolExecutionCard } from "./ToolExecutionCard";
import { ApprovalGate } from "./ApprovalGate";
import { ChatBubble } from "./ChatBubble";
import { TerminalPanel } from "./TerminalPanel";
import { BrowserPanel } from "./BrowserPanel";
import { FileExplorer } from "./FileExplorer";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { apiFetch } from "@/lib/api";
import {
  Loader2,
  Bot,
  Square,
  AlertCircle,
  Activity,
  Cpu,
  FileCode,
  Globe,
  Shield,
  Terminal,
  Menu,
  X,
  ChevronLeft,
  ChevronRight,
  PanelRight,
  PanelRightClose,
  Plus,
  Search,
  MessageSquare,
  Settings,
  History,
  Gauge,
  Zap,
} from "lucide-react";

interface AetherPanelProps {
  className?: string;
  sessionId?: string;
}

const generateSessionId = () => {
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
};

// Context Usage Gauge Component
function ContextGauge({ percentage }: { percentage: number }) {
  const getColor = () => {
    if (percentage < 50) return "bg-green-500";
    if (percentage < 75) return "bg-yellow-500";
    return "bg-red-500";
  };

  return (
    <div className="flex items-center gap-2">
      <Gauge className="w-4 h-4 text-muted-foreground" />
      <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
        <div
          className={cn("h-full transition-all duration-500", getColor())}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-xs text-muted-foreground w-8 text-right">
        {percentage}%
      </span>
    </div>
  );
}

// Settings Modal Component
function SettingsModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-card border border-border rounded-lg p-6 w-96 max-w-[90vw]">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Settings</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>
        
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Autonomy Mode</label>
            <select className="w-full p-2 rounded-md border bg-background text-sm">
              <option value="semi">Semi-Autonomous (Approval Required)</option>
              <option value="auto">Fully Autonomous</option>
            </select>
          </div>
          
          <div>
            <label className="text-sm font-medium mb-2 block">Model</label>
            <select className="w-full p-2 rounded-md border bg-background text-sm">
              <option>Qwen3-VL-30B-Thinking</option>
              <option>Qwen3-VL-30B-Instruct</option>
            </select>
          </div>
          
          <div className="pt-4 border-t">
            <Button className="w-full" onClick={onClose}>Save Changes</Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AetherPanel({ className, sessionId: propSessionId }: AetherPanelProps) {
  const [sessionId] = useState(() => propSessionId || generateSessionId());
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightSidebarOpen, setRightSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workbenchTab, setWorkbenchTab] = useState<"plan" | "tools" | "terminal" | "browser" | "files">("plan");
  const [inputText, setInputText] = useState("");
  const [contextUsage, setContextUsage] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const {
    state,
    messages,
    toolExecutions,
    pendingApproval,
    isConnected,
    error,
    currentTool,
    sendMessage,
    approveOperation,
    rejectOperation,
    cancelTask,
    clearMessages,
  } = useAgentRuntime(sessionId);

  // Fetch context stats periodically
  useEffect(() => {
    const fetchContext = async () => {
      try {
        const data = await apiFetch('/api/context/stats');
        setContextUsage(Math.round(data.usage_percent || 0));
      } catch (e) {
        // Silent fail
      }
    };
    
    fetchContext();
    const interval = setInterval(fetchContext, 5000);
    return () => clearInterval(interval);
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, state.current_thinking, toolExecutions]);

  // Show connection errors
  useEffect(() => {
    if (error) {
      toast({
        title: "Connection Error",
        description: error,
        variant: "destructive",
      });
    }
  }, [error, toast]);

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
  }, []);

  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputText(e.target.value);
    adjustHeight();
  };

  const handleSend = async () => {
    if (!inputText.trim() || isLoading || !isConnected) return;
    
    const text = inputText.trim();
    setInputText("");
    
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
    
    await sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Drag and drop handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  // Get status display
  const getStatusDisplay = () => {
    switch (state.status) {
      case "idle":
        return { icon: <Bot className="w-4 h-4" />, text: "Ready", color: "text-green-500" };
      case "planning":
        return { icon: <Activity className="w-4 h-4 animate-pulse" />, text: "Planning...", color: "text-blue-500" };
      case "thinking":
        return { icon: <Cpu className="w-4 h-4 animate-pulse" />, text: "Thinking...", color: "text-yellow-500" };
      case "tool_calling":
        return { icon: <Terminal className="w-4 h-4 animate-pulse" />, text: "Executing...", color: "text-purple-500" };
      case "observing":
        return { icon: <Activity className="w-4 h-4" />, text: "Observing...", color: "text-cyan-500" };
      case "compiling":
        return { icon: <FileCode className="w-4 h-4 animate-pulse" />, text: "Compiling...", color: "text-orange-500" };
      case "paused":
        return { icon: <Shield className="w-4 h-4" />, text: "Waiting for approval", color: "text-yellow-500" };
      default:
        return { icon: <Bot className="w-4 h-4" />, text: "Unknown", color: "text-muted-foreground" };
    }
  };

  const statusDisplay = getStatusDisplay();
  const isLoading = state.status !== "idle" && state.status !== "paused";
  const isBusy = isLoading;

  return (
    <div className={cn("flex h-screen w-full bg-background overflow-hidden", className)}>
      {/* Left Sidebar - Chat History */}
      <div
        className={cn(
          "flex flex-col border-r border-border bg-card/50 transition-all duration-300",
          leftSidebarOpen ? "w-64" : "w-0 opacity-0 overflow-hidden"
        )}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-3 border-b border-border">
          <span className="font-semibold text-sm flex items-center gap-2">
            <History className="w-4 h-4" />
            Chat History
          </span>
          <Button variant="ghost" size="icon" className="h-7 w-7">
            <Plus className="w-4 h-4" />
          </Button>
        </div>

        {/* Search */}
        <div className="p-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search chats..."
              className="w-full pl-9 pr-3 py-1.5 bg-muted rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
        </div>

        {/* Chat List */}
        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            <button className="w-full text-left p-2 rounded-lg bg-primary/10 text-primary text-sm">
              <div className="font-medium truncate">Current Session</div>
              <div className="text-xs text-muted-foreground truncate">
                {messages.length} messages
              </div>
            </button>
            <button className="w-full text-left p-2 rounded-lg hover:bg-muted text-sm text-muted-foreground">
              <div className="font-medium truncate">Previous Chat</div>
              <div className="text-xs truncate">5 messages</div>
            </button>
          </div>
        </ScrollArea>

        {/* Context Usage in Sidebar */}
        <div className="p-3 border-t border-border">
          <p className="text-xs text-muted-foreground mb-2">Context Usage</p>
          <ContextGauge percentage={contextUsage} />
        </div>

        {/* Bottom Actions */}
        <div className="p-2 border-t border-border space-y-1">
          <button 
            onClick={() => setSettingsOpen(true)}
            className="w-full flex items-center gap-2 p-2 rounded-lg hover:bg-muted text-sm text-muted-foreground"
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
          <div className="flex items-center gap-2">
            {/* Left sidebar toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setLeftSidebarOpen(!leftSidebarOpen)}
            >
              {leftSidebarOpen ? (
                <ChevronLeft className="w-4 h-4" />
              ) : (
                <Menu className="w-4 h-4" />
              )}
            </Button>

            {/* Status */}
            <div className={cn("flex items-center gap-2 text-sm", statusDisplay.color)}>
              {statusDisplay.icon}
              <span className="font-medium">{statusDisplay.text}</span>
            </div>

            {!isConnected && (
              <span className="flex items-center gap-1 text-xs text-destructive animate-pulse">
                <AlertCircle className="w-3 h-3" />
                Reconnecting...
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Right sidebar toggle */}
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setRightSidebarOpen(!rightSidebarOpen)}
              title={rightSidebarOpen ? "Hide Workbench" : "Show Workbench"}
            >
              {rightSidebarOpen ? (
                <PanelRightClose className="w-4 h-4" />
              ) : (
                <PanelRight className="w-4 h-4" />
              )}
            </Button>

            {isBusy && (
              <Button
                variant="ghost"
                size="sm"
                onClick={cancelTask}
                className="text-destructive hover:text-destructive h-8"
              >
                <Square className="w-4 h-4 mr-1" />
                Stop
              </Button>
            )}
          </div>
        </div>

        {/* Messages */}
        <ScrollArea className="flex-1">
          <div className="max-w-3xl mx-auto p-4 space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-[60vh] text-muted-foreground">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                  <Bot className="w-8 h-8 text-primary" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">How can I help you today?</h2>
                <p className="text-sm text-center max-w-md">
                  I can write code, browse the web, analyze files, and more. 
                  What would you like to work on?
                </p>
              </div>
            )}

            {messages.map((msg, index) => (
              <ChatBubble
                key={index}
                role={msg.role}
                content={msg.content}
                thinking={msg.thinking}
                attachments={msg.attachments}
                timestamp={msg.timestamp}
              />
            ))}

            {/* Live thinking stream */}
            {state.current_thinking && (
              <ThinkingStream
                thinking={state.current_thinking}
                isThinking={state.status === "thinking"}
                stepDescription={state.thinking_step}
              />
            )}

            {/* Current tool execution */}
            {currentTool && (
              <div className="max-w-2xl mx-auto">
                <p className="text-xs text-muted-foreground mb-2">Current Action:</p>
                <ToolExecutionCard tool={currentTool} isCurrent />
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="p-4 border-t border-border">
          <div className="max-w-3xl mx-auto">
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              className={cn(
                "relative rounded-xl border bg-card shadow-sm transition-colors",
                isDragging && "border-primary bg-primary/5",
                !isConnected && "opacity-50"
              )}
            >
              {/* Drag overlay */}
              {isDragging && (
                <div className="absolute inset-0 bg-primary/5 border-2 border-dashed border-primary rounded-xl flex items-center justify-center z-10">
                  <p className="text-sm text-primary font-medium">Drop files here</p>
                </div>
              )}

              <div className="flex items-end gap-2 p-3">
                <textarea
                  ref={textareaRef}
                  value={inputText}
                  onChange={handleTextChange}
                  onKeyDown={handleKeyDown}
                  placeholder={isConnected ? "Message Aether..." : "Connecting..."}
                  disabled={!isConnected || state.status === "paused"}
                  rows={1}
                  className="flex-1 bg-transparent border-0 resize-none py-2 px-1 focus:outline-none focus:ring-0 min-h-[40px] max-h-[200px] text-sm"
                />

                <div className="flex items-center gap-1 shrink-0 pb-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 text-muted-foreground hover:text-foreground"
                    disabled={!isConnected}
                    title="Attach file"
                  >
                    <span className="text-lg">+</span>
                  </Button>

                  <Button
                    onClick={handleSend}
                    disabled={!inputText.trim() || isLoading || !isConnected}
                    size="icon"
                    className={cn(
                      "h-8 w-8 rounded-lg transition-all",
                      inputText.trim() && isConnected
                        ? "bg-primary text-primary-foreground hover:bg-primary/90"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {isLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <span className="text-sm">↑</span>
                    )}
                  </Button>
                </div>
              </div>

              {/* Bottom hint */}
              <div className="px-3 pb-2 text-[10px] text-muted-foreground">
                Press Enter to send, Shift+Enter for new line
              </div>
            </div>

            {/* Semi-autonomous indicator */}
            <div className="flex items-center justify-between mt-2 px-1">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Shield className="w-3 h-3" />
                <span>Semi-Autonomous Mode</span>
                <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                  Approval required
                </span>
              </div>
              <div className="text-xs text-muted-foreground">
                Context: {contextUsage}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Sidebar - Workbench */}
      <div
        className={cn(
          "flex flex-col border-l border-border bg-card/30 transition-all duration-300",
          rightSidebarOpen ? "w-[480px]" : "w-0 opacity-0 overflow-hidden"
        )}
      >
        {/* Workbench Header */}
        <div className="flex items-center justify-between p-3 border-b border-border">
          <span className="font-semibold text-sm flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Workbench
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setRightSidebarOpen(false)}
          >
            <X className="w-4 h-4" />
          </Button>
        </div>

        {/* Workbench Tabs */}
        <div className="flex border-b border-border">
          {[
            { id: "plan", label: "Plan", icon: Activity },
            { id: "tools", label: "Tools", icon: Terminal },
            { id: "terminal", label: "Terminal", icon: Terminal },
            { id: "browser", label: "Browser", icon: Globe },
            { id: "files", label: "Files", icon: FileCode },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setWorkbenchTab(tab.id as any)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-2 text-xs font-medium transition-colors",
                workbenchTab === tab.id
                  ? "bg-primary/10 text-primary border-b-2 border-primary"
                  : "text-muted-foreground hover:bg-muted/50"
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        <ScrollArea className="flex-1 p-3">
          {workbenchTab === "plan" && (
            <>
              {/* Plan Steps */}
              {state.plan.length > 0 && (
                <PlanSteps steps={state.plan} currentStep={state.current_step} />
              )}

              {/* Recent Tool Executions */}
              {toolExecutions.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-medium mb-2 text-muted-foreground">
                    Tool Executions ({toolExecutions.length})
                  </h4>
                  <div className="space-y-2">
                    {toolExecutions.slice(-5).map((tool) => (
                      <ToolExecutionCard key={tool.id} tool={tool} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {workbenchTab === "tools" && (
            <>
              {/* Active Capabilities */}
              <div className="mt-2">
                <h4 className="text-sm font-medium mb-2 text-muted-foreground">
                  Active Capabilities
                </h4>
                <div className="flex flex-wrap gap-2">
                  <CapabilityBadge icon={<Terminal className="w-3 h-3" />} label="Code" />
                  <CapabilityBadge icon={<Globe className="w-3 h-3" />} label="Web" />
                  <CapabilityBadge icon={<FileCode className="w-3 h-3" />} label="Files" />
                  <CapabilityBadge icon={<Shield className="w-3 h-3" />} label="Safe Mode" />
                </div>
              </div>

              {/* Session Info */}
              <div className="mt-6 p-3 bg-muted/50 rounded-lg text-xs text-muted-foreground space-y-1">
                <p>Session: {sessionId.slice(0, 16)}...</p>
                <p>Status: {state.status}</p>
                <p>Step: {state.current_step + 1} / {state.plan.length}</p>
              </div>
            </>
          )}

          {workbenchTab === "terminal" && (
            <div className="mt-2">
              <TerminalPanel sessionId={sessionId} />
            </div>
          )}

          {workbenchTab === "browser" && (
            <div className="mt-2">
              <BrowserPanel sessionId={sessionId} />
            </div>
          )}

          {workbenchTab === "files" && (
            <div className="mt-2">
              <FileExplorer />
            </div>
          )}
        </ScrollArea>
      </div>

      {/* Settings Modal */}
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />

      {/* Approval Dialog */}
      <ApprovalGate
        request={pendingApproval}
        onApprove={approveOperation}
        onReject={rejectOperation}
      />
    </div>
  );
}

function CapabilityBadge({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <span className="flex items-center gap-1 text-xs bg-muted px-2 py-1 rounded-md">
      {icon}
      {label}
    </span>
  );
}

export default AetherPanel;
