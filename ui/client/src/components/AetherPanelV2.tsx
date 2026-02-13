"use client";

import React, { useEffect, useState, useRef } from "react";
import { cn } from "@/lib/utils";
import { useAgentRuntime } from "@/hooks/useAgentRuntime";
import { apiFetch } from "@/lib/api";
import Editor from "@monaco-editor/react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import "xterm/css/xterm.css";
import {
  Bot, Menu, X, Plus, Settings, History, Search, PanelRight, PanelRightClose,
  Terminal as TerminalIcon, Globe, FileCode, Activity, Cpu, Shield, Loader2,
  ArrowUp, Paperclip, Image as ImageIcon, ChevronDown, Zap, BarChart3,
  MessageSquare, Hash, Folder, FileText, RefreshCw, Save, Trash2,
  Camera, ChevronLeft, ChevronRight, Bug, Volume2, Radio
} from "lucide-react";
import { VoiceRecorder } from "./VoiceRecorder";
import { TextToSpeech } from "./TextToSpeech";
import { AgentActivity } from "./AgentActivity";
import { ApprovalGate } from "./ApprovalGate";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/hooks/use-toast";
import { SettingsDialog } from "./SettingsDialog";

interface AetherPanelV2Props {
  className?: string;
  sessionId?: string;
}

const generateSessionId = () => `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

const QUICK_ACTIONS = [
  "Explain quantum computing",
  "Write a Python function",
  "Analyze this document",
  "Help with data analysis",
];

interface FileNode {
  name: string;
  type: "file" | "directory";
  path: string;
  size?: number;
  children?: FileNode[];
  isOpen?: boolean;
}

// Debug info from LiteLLM
interface DebugInfo {
  app: string;
  provider?: string;
  model: string;
  model_group: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  spend: number;
  request_id: string;
  timestamp: string;
  headers_sent?: Record<string, string>;
  error?: string | null;
}

// Model info from API
interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  model_group: string;
  healthy: boolean;
}

interface CurrentModelInfo {
  model_id: string;
  provider: string;
}

export function AetherPanelV2({ className, sessionId: propSessionId }: AetherPanelV2Props) {
  const [sessionId] = useState(() => propSessionId || generateSessionId());
  const [leftSidebarOpen, setLeftSidebarOpen] = useState(true);
  const [rightPanelOpen, setRightPanelOpen] = useState(true);
  const [activeTab, setActiveTab] = useState<"context" | "activity" | "terminal" | "browser" | "files" | "debug">("context");
  const [inputText, setInputText] = useState("");
  const [history, setHistory] = useState<any[]>([]);
  const [tokenUsage, setTokenUsage] = useState({ used: 0, max: 128000, percent: 0 });
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [agentState, setAgentState] = useState("idle"); // idle, planning, thinking, tool_calling, observing
  const [attachments, setAttachments] = useState<{ name: string, type: string, content: string }[]>([]);
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  const { state, messages, toolExecutions, pendingApproval, isConnected, error, sendMessage, approveOperation, rejectOperation } = useAgentRuntime(sessionId);

  const selectBackendModel = async (modelId: string, silent = false) => {
    try {
      const data = await apiFetch("/api/models/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_id: modelId }),
      });
      if (!silent) {
        toast({
          title: "Model switched",
          description: `Active model: ${modelId}`,
        });
        if (data && data.healthy === false) {
          toast({
            title: "Model unhealthy",
            description: `${modelId} did not pass health check. It may still fail on requests.`,
            variant: "destructive",
          });
        }
      }
      return true;
    } catch (err: any) {
      if (!silent) {
        toast({
          title: "Model switch failed",
          description: err?.message || "Unable to switch model on backend",
          variant: "destructive",
        });
      }
      return false;
    }
  };

  // Fetch available models from API
  useEffect(() => {
    const fetchModels = async () => {
      try {
        const [data, current] = await Promise.all([
          apiFetch("/api/models"),
          apiFetch("/api/models/current").catch(() => null),
        ]);
        const currentModelId = (current as CurrentModelInfo | null)?.model_id || "";
        if (currentModelId) {
          setSelectedModel(currentModelId);
        }
        if (Array.isArray(data) && data.length > 0) {
          setModels(data);
          const currentExists = currentModelId && data.some((m: ModelInfo) => m.id === currentModelId);
          const healthy = data.find((m: ModelInfo) => m.healthy);
          const fallback = healthy?.id || data[0].id;
          const targetModel = (currentExists ? currentModelId : fallback) as string;

          setSelectedModel(targetModel);

          // If backend points to an unavailable model, realign it to an available one.
          if (!currentExists && targetModel) {
            await selectBackendModel(targetModel, true);
          }
        }
      } catch (e) { }
    };
    fetchModels();
    fetchModels();
  }, []);

  // Fetch history
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const data = await apiFetch("/api/history");
        if (data?.sessions) setHistory(data.sessions);
      } catch (e) { }
    };
    fetchHistory();
    // Refresh history occasionally
    const interval = setInterval(fetchHistory, 10000);
    return () => clearInterval(interval);
  }, []);

  // Update agent state from runtime state
  useEffect(() => {
    if (state?.status) {
      setAgentState(state.status);
    }
  }, [state]);

  // Fetch usage stats from backend
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const data = await apiFetch("/api/context/stats");
        // Use actual token counts from LiteLLM
        const used = data.total_tokens || 0;
        const max = 128000;
        const percent = Math.min(Math.round((used / max) * 100), 100);
        setTokenUsage({ used, max, percent });
      } catch (e) { }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 1500);
    return () => clearInterval(interval);
  }, []);

  // Fetch debug info from LiteLLM API
  useEffect(() => {
    const fetchDebugInfo = async () => {
      try {
        const data = await apiFetch("/api/debug/litellm");
        if (data && data.app) {
          setDebugInfo(data);
        }
      } catch (e) {
        // Fallback to placeholder if API not available
      }
    };
    fetchDebugInfo();
    const interval = setInterval(fetchDebugInfo, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (error) {
      const isConnectionError = error.toLowerCase().includes("connection");
      toast({
        title: isConnectionError ? "Connection Error" : "Runtime Error",
        description: error,
        variant: "destructive",
      });
    }
  }, [error, toast]);

  const handleSend = async () => {
    if (!inputText.trim() && attachments.length === 0) return;
    if (!isConnected) return;

    let text = inputText.trim();
    if (webSearchEnabled) {
      text += "\n\n[System: User has enabled Web Search for this request. Use the web_search tool if needed.]";
    }

    setInputText("");
    setAttachments([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    // Convert local attachments to format expected by sendMessage
    const msgAttachments = attachments.map(a => ({
      type: a.type.startsWith("image/") ? "image" : "file",
      mime_type: a.type,
      content: a.content,
      filename: a.name
    }));

    await sendMessage(text, msgAttachments);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewChat = () => {
    // Force a full navigation to root to plain URL to clear any potential session state
    window.location.href = "/";
  };

  const handleImageUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) {
      const file = e.target.files[0];
      const reader = new FileReader();
      reader.onload = (ev) => {
        if (ev.target?.result) {
          const content = ev.target.result as string;
          // Content is like "data:image/png;base64,..."
          // We want to store exactly that for display, and handle stripping prefix in send if needed 
          // (but most LLM APIs take data URL or base64. Let's keep data URL for now).
          setAttachments(prev => [...prev, {
            name: file.name,
            type: file.type,
            content: content
          }]);
          toast({ title: "File attached", description: file.name });
        }
      };
      reader.readAsDataURL(file);
    }
    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const isBusy = state.status !== "idle" && state.status !== "paused";

  return (
    <div className={cn("flex h-screen w-full bg-[#0a0a0a] text-gray-100", className)}>
      {/* Approval Gate Modal */}
      <ApprovalGate
        request={pendingApproval}
        onApprove={approveOperation}
        onReject={rejectOperation}
      />

      {/* Left Sidebar */}
      <aside className={cn("flex flex-col border-r border-white/5 bg-[#0a0a0a] transition-all duration-300", leftSidebarOpen ? "w-64" : "w-0 overflow-hidden")}>
        <div className="flex items-center gap-3 p-4 border-b border-white/5">
          <div className="w-8 h-8 rounded-lg bg-linear-to-br from-orange-500 to-red-600 flex items-center justify-center">
            <span className="text-white font-bold text-sm">A</span>
          </div>
          <span className="font-semibold text-white">AetherOS</span>
        </div>

        <div className="p-3">
          <button onClick={handleNewChat} className="w-full flex items-center justify-center gap-2 bg-orange-600 hover:bg-orange-500 text-white py-2.5 px-4 rounded-lg font-medium transition-colors">
            <Plus className="w-4 h-4" />
            New Chat
          </button>
        </div>

        <div className="px-3 pb-3">
          <select
            value={selectedModel}
            onChange={async (e) => {
              const nextModel = e.target.value;
              const previousModel = selectedModel;
              setSelectedModel(nextModel);
              const ok = await selectBackendModel(nextModel);
              if (!ok) {
                setSelectedModel(previousModel);
              }
            }}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-orange-500"
          >
            {models.length > 0 ? (
              models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))
            ) : (
              <option value="" disabled>No models available</option>
            )}
          </select>
        </div>

        <div className="flex-1 px-3">
          <div className="flex items-center gap-2 px-2 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider">
            <History className="w-3.5 h-3.5" />
            History
          </div>
          <div className="space-y-1">
            <button className="w-full text-left px-3 py-2 rounded-lg bg-white/10 text-sm text-white">Current Session</button>
            <ScrollArea className="h-48">
              {history.map((session) => (
                <button key={session.id} className="w-full text-left px-3 py-2 rounded-lg hover:bg-white/5 text-xs text-gray-400 transition-colors truncate">
                  {session.title || session.timestamp || session.id}
                </button>
              ))}
            </ScrollArea>
          </div>
        </div>

        <div className="p-3 border-t border-white/5 space-y-1">
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors">
            <Zap className="w-4 h-4" />
            <span className="text-sm">Starred</span>
          </button>
          <button className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors">
            <FileCode className="w-4 h-4" />
            <span className="text-sm">Folders</span>
          </button>
          <SettingsDialog />
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 bg-[#0a0a0a]">
        <header className="flex items-center justify-between px-4 py-3 border-b border-white/5">
          <div className="flex items-center gap-3">
            <button onClick={() => setLeftSidebarOpen(!leftSidebarOpen)} className="p-2 hover:bg-white/5 rounded-lg transition-colors">
              <Menu className="w-5 h-5 text-gray-400" />
            </button>
            <h1 className="font-semibold text-white">AetherOS</h1>
            {/* Live Agent State Badge */}
            {agentState !== "idle" && (
              <span className={cn(
                "px-2 py-0.5 rounded-full text-xs font-medium animate-pulse",
                agentState === "planning" && "bg-blue-500/20 text-blue-400",
                agentState === "thinking" && "bg-purple-500/20 text-purple-400",
                agentState === "tool_calling" && "bg-yellow-500/20 text-yellow-400",
                agentState === "observing" && "bg-green-500/20 text-green-400",
              )}>
                {agentState.replace("_", " ").toUpperCase()}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setRightPanelOpen(!rightPanelOpen)} className="p-2 hover:bg-white/5 rounded-lg transition-colors">
              {rightPanelOpen ? <PanelRightClose className="w-5 h-5 text-gray-400" /> : <PanelRight className="w-5 h-5 text-gray-400" />}
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-hidden relative">
          {/* Real-time Activity Feed - Shows when agent is working */}
          {state.status !== "idle" && (
            <div className="absolute top-0 left-0 right-0 z-10 bg-[#0a0a0a]/95 backdrop-blur border-b border-white/5 p-4 max-h-96 overflow-y-auto">
              <AgentActivity
                status={state.status}
                currentStep={state.current_step}
                plan={state.plan}
                currentThinking={state.current_thinking}
                thinkingStep={state.thinking_step}
                toolExecutions={toolExecutions}
              />
            </div>
          )}

          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full px-4">
              <div className="w-16 h-16 rounded-2xl bg-linear-to-br from-orange-500/20 to-red-600/20 flex items-center justify-center mb-6">
                <Bot className="w-8 h-8 text-orange-500" />
              </div>
              <h2 className="text-2xl font-semibold text-white mb-3">How can I help you today?</h2>
              <p className="text-gray-400 text-center max-w-md mb-8">
                Start a conversation with one of our sovereign AI models. All inference runs on your infrastructure with enterprise-grade security.
              </p>
              <div className="flex flex-wrap justify-center gap-3 max-w-2xl">
                {QUICK_ACTIONS.map((action) => (
                  <button
                    key={action}
                    onClick={() => { setInputText(action); textareaRef.current?.focus(); }}
                    className="px-4 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full text-sm text-gray-300 transition-colors"
                  >
                    {action}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <ScrollArea className="h-full">
              <div className="max-w-3xl mx-auto py-6 space-y-6">
                {messages.map((msg, idx) => (
                  <div key={idx} className={cn("flex gap-4 px-4", msg.role === "user" ? "flex-row-reverse" : "")}>
                    <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0", msg.role === "user" ? "bg-orange-600" : "bg-linear-to-br from-orange-500/20 to-red-600/20")}>
                      {msg.role === "user" ? <span className="text-white text-sm font-medium">U</span> : <Bot className="w-4 h-4 text-orange-500" />}
                    </div>
                    <div className={cn("flex-1 max-w-[85%]", msg.role === "user" ? "text-right" : "")}>
                      <div className={cn("inline-block px-4 py-3 rounded-2xl text-left group", msg.role === "user" ? "bg-orange-600 text-white" : "bg-white/5 text-gray-200")}>
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                        {msg.role === "assistant" && (
                          <div className="mt-2 pt-2 border-t border-white/10 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                            <TextToSpeech text={msg.content} />
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </ScrollArea>
          )}
        </div>

        <div className="p-4 border-t border-white/5">
          <div className="max-w-3xl mx-auto">
            <div className="relative bg-[#141414] border border-white/10 rounded-xl">
              <textarea
                ref={textareaRef}
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Message the assistant..."
                disabled={!isConnected}
                rows={1}
                className="w-full bg-transparent px-4 py-3 pr-32 text-gray-200 placeholder-gray-500 resize-none focus:outline-none min-h-32 max-h-50"
              />
              {/* Attachment Previews */}
              {attachments.length > 0 && (
                <div className="px-4 pb-2 flex gap-2 overflow-x-auto">
                  {attachments.map((att, i) => (
                    <div key={i} className="relative group flex items-center gap-2 bg-white/10 rounded-lg px-2 py-1">
                      {att.type.startsWith("image/") ? (
                        <img src={att.content} alt={att.name} className="w-8 h-8 object-cover rounded" />
                      ) : (
                        <FileCode className="w-5 h-5 text-gray-400" />
                      )}
                      <span className="text-xs text-gray-300 max-w-[100px] truncate">{att.name}</span>
                      <button
                        onClick={() => setAttachments(prev => prev.filter((_, idx) => idx !== i))}
                        className="ml-1 p-0.5 hover:bg-white/20 rounded-full text-gray-400 hover:text-white"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              <div className="absolute right-2 bottom-2 flex items-center gap-1">
                <button
                  onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                  className={cn(
                    "p-2 rounded-lg transition-colors",
                    webSearchEnabled ? "text-blue-400 bg-blue-500/10 hover:bg-blue-500/20" : "text-gray-500 hover:text-gray-300 hover:bg-white/5"
                  )}
                  title={webSearchEnabled ? "Web Search ON" : "Enable Web Search"}
                >
                  <Globe className="w-4 h-4" />
                </button>
                <div className="w-px h-4 bg-white/10 mx-1" />
                <button className="p-2 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded-lg transition-colors" title="Attach file">
                  <Paperclip className="w-4 h-4" />
                </button>
                <button onClick={handleImageUpload} className="p-2 text-gray-500 hover:text-gray-300 hover:bg-white/5 rounded-lg transition-colors" title="Upload image">
                  <ImageIcon className="w-4 h-4" />
                </button>
                <input ref={fileInputRef} type="file" className="hidden" accept="image/*" onChange={handleFileChange} />
                <VoiceRecorder
                  onTranscription={(text) => setInputText(prev => prev + (prev ? " " : "") + text)}
                  disabled={!isConnected || isBusy}
                />
                <button
                  onClick={handleSend}
                  disabled={(!inputText.trim() && attachments.length === 0) || isBusy || !isConnected}
                  className={cn("p-2 rounded-lg transition-colors", (inputText.trim() || attachments.length > 0) && isConnected ? "bg-orange-600 text-white hover:bg-orange-500" : "bg-white/5 text-gray-500 cursor-not-allowed")}
                >
                  {isBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowUp className="w-4 h-4" />}
                </button>
              </div>
            </div>
            <div className="flex items-center justify-between mt-2 px-1">
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <span className="bg-white/5 px-2 py-0.5 rounded">Press Enter to send</span>
                <span>Shift+Enter for new line</span>
              </div>
              <div className="flex items-center gap-2 text-xs">
                <Shield className="w-3 h-3 text-green-500" />
                <span className="text-gray-400">Semi-Autonomous Mode</span>
                <span className="text-gray-500">•</span>
                <span className="bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded text-[10px]">{selectedModel || "unselected"}</span>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Right Panel */}
      <aside className={cn("flex flex-col border-l border-white/5 bg-[#0a0a0a] transition-all duration-300", rightPanelOpen ? "w-96" : "w-0 overflow-hidden")}>
        <div className="flex items-center justify-between p-4 border-b border-white/5">
          <span className="font-medium text-white capitalize">{activeTab}</span>
          <button onClick={() => setRightPanelOpen(false)} className="p-1.5 hover:bg-white/5 rounded-lg transition-colors">
            <X className="w-4 h-4 text-gray-400" />
          </button>
        </div>

        <div className="flex border-b border-white/5">
          {[
            { id: "context", icon: BarChart3, label: "Context" },
            { id: "activity", icon: Radio, label: "Activity" },
            { id: "terminal", icon: TerminalIcon, label: "Terminal" },
            { id: "browser", icon: Globe, label: "Browser" },
            { id: "files", icon: FileCode, label: "Files" },
            { id: "debug", icon: Bug, label: "Debug" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors border-b-2",
                activeTab === tab.id ? "text-orange-500 border-orange-500 bg-orange-500/5" : "text-gray-500 border-transparent hover:text-gray-300 hover:bg-white/5"
              )}
            >
              <tab.icon className="w-3.5 h-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-hidden">
          {activeTab === "context" && <ContextPanel tokenUsage={tokenUsage} messages={messages} selectedModel={selectedModel} debugInfo={debugInfo} />}
          {activeTab === "activity" && (
            <ScrollArea className="h-full">
              <div className="p-4">
                <AgentActivity
                  status={state.status}
                  currentStep={state.current_step}
                  plan={state.plan}
                  currentThinking={state.current_thinking}
                  thinkingStep={state.thinking_step}
                  toolExecutions={toolExecutions}
                />
              </div>
            </ScrollArea>
          )}
          {activeTab === "terminal" && <TerminalPanel sessionId={sessionId} />}
          {activeTab === "browser" && <BrowserPanel sessionId={sessionId} />}
          {activeTab === "files" && <FilesPanel />}
          {activeTab === "debug" && <DebugPanel debugInfo={debugInfo} />}
        </div>
      </aside>
    </div>
  );
}

// Context Panel
function ContextPanel({ tokenUsage, messages, selectedModel, debugInfo }: { tokenUsage: { used: number; max: number; percent: number }; messages: any[]; selectedModel: string; debugInfo: DebugInfo | null }) {
  const activeModelName = debugInfo?.model || selectedModel || "unknown";
  // Get model group from debugInfo or infer from active model id.
  const modelGroup = debugInfo?.model_group ||
    (activeModelName.includes("vl") || activeModelName.includes("vision") ? "vision_reasoning" : "text_reasoning");

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-6">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <div className="w-4 h-4 rounded bg-linear-to-br from-blue-500 to-purple-600" />
            <span className="font-medium text-white">Token Usage</span>
            <span className="ml-auto text-xs bg-white/10 px-2 py-0.5 rounded-full">{tokenUsage.percent}%</span>
          </div>
          <div className="h-2 bg-white/5 rounded-full overflow-hidden mb-3">
            <div className={cn("h-full rounded-full transition-all", tokenUsage.percent < 50 ? "bg-green-500" : tokenUsage.percent < 80 ? "bg-yellow-500" : "bg-red-500")} style={{ width: `${Math.min(tokenUsage.percent, 100)}%` }} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-gray-400"><span>Used</span><span className="text-white">{Math.round(tokenUsage.used).toLocaleString()}</span></div>
            <div className="flex justify-between text-gray-400"><span>Max (app-estimated)</span><span className="text-white">{tokenUsage.max.toLocaleString()}</span></div>
            <div className="flex justify-between text-gray-400"><span>Remaining</span><span className="text-white">{Math.max(0, tokenUsage.max - Math.round(tokenUsage.used)).toLocaleString()}</span></div>
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-3">
            <Cpu className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-white">Model</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-400">Name</span><span className="text-white">{activeModelName}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Provider</span><span className="text-white">{debugInfo?.provider || "unknown"}</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Context Window</span><span className="text-gray-500 text-xs">app-estimated</span></div>
            <div className="flex justify-between"><span className="text-gray-400">Model Group</span><span className={cn("text-orange-400", modelGroup === "vision_reasoning" && "text-purple-400")}>{modelGroup}</span></div>
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2 mb-3">
            <MessageSquare className="w-4 h-4 text-gray-400" />
            <span className="font-medium text-white">Conversation Stats</span>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between text-gray-400"><span>Total messages</span><span className="text-white">{messages.length}</span></div>
            <div className="flex justify-between text-gray-400"><span>User messages</span><span className="text-white">{messages.filter((m: any) => m.role === "user").length}</span></div>
            <div className="flex justify-between text-gray-400"><span>Assistant messages</span><span className="text-white">{messages.filter((m: any) => m.role === "assistant").length}</span></div>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}

// Debug Panel - Shows LiteLLM metadata
function DebugPanel({ debugInfo }: { debugInfo: DebugInfo | null }) {
  if (!debugInfo) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-gray-500 p-4">
        <Bug className="w-12 h-12 mb-4 opacity-50" />
        <p className="text-sm">Send a message to see debug info</p>
        <p className="text-xs text-gray-600 mt-2">This panel shows metadata from LiteLLM</p>
      </div>
    );
  }

  return (
    <ScrollArea className="h-full">
      <div className="p-4 space-y-4">
        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <h3 className="text-xs font-medium text-gray-400 uppercase mb-3">Last Request</h3>
          <div className="space-y-2 text-sm font-mono">
            <div className="flex justify-between">
              <span className="text-gray-500">app:</span>
              <span className="text-green-400">{debugInfo.app}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">model:</span>
              <span className="text-blue-400">{debugInfo.model}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">model_group:</span>
              <span className="text-orange-400">{debugInfo.model_group}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">prompt_tokens:</span>
              <span className="text-white">{Math.round(debugInfo.prompt_tokens)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">completion_tokens:</span>
              <span className="text-white">{Math.round(debugInfo.completion_tokens)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">total_tokens:</span>
              <span className="text-white">{Math.round(debugInfo.total_tokens || 0)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">spend:</span>
              <span className="text-yellow-400">${debugInfo.spend.toFixed(6)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">request_id:</span>
              <span className="text-gray-400 text-xs truncate max-w-37.5">{debugInfo.request_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-500">timestamp:</span>
              <span className="text-gray-400 text-xs">{debugInfo.timestamp}</span>
            </div>
          </div>
          {debugInfo.error && (
            <div className="mt-3 rounded border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300">
              {debugInfo.error}
            </div>
          )}
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <h3 className="text-xs font-medium text-gray-400 uppercase mb-3">Headers Sent</h3>
          {debugInfo.headers_sent && Object.keys(debugInfo.headers_sent).length > 0 ? (
            <div className="space-y-1 text-xs font-mono text-gray-400">
              {Object.entries(debugInfo.headers_sent).map(([key, value]) => (
                <div key={key}>
                  {key}: {value}
                </div>
              ))}
              <div>Authorization: Bearer ***</div>
            </div>
          ) : (
            <div className="space-y-1 text-xs font-mono text-gray-500">
              <div>No header metadata available yet.</div>
            </div>
          )}
        </div>

        <div className="bg-white/5 rounded-lg p-3 border border-white/10">
          <h3 className="text-xs font-medium text-gray-400 uppercase mb-3">Model Badge</h3>
          <div className="flex items-center gap-2">
            {debugInfo.model_group === "vision_reasoning" && (
              <span className="px-2 py-1 bg-purple-500/20 text-purple-400 rounded text-xs">Vision</span>
            )}
            {debugInfo.model_group === "ocr_utility" && (
              <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-xs">OCR</span>
            )}
            <span className="px-2 py-1 bg-blue-500/20 text-blue-400 rounded text-xs">Text/Reasoning</span>
          </div>
        </div>
      </div>
    </ScrollArea>
  );
}

// Terminal Panel
function TerminalPanel({ sessionId }: { sessionId: string }) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!terminalRef.current) return;
    const term = new Terminal({ cursorBlink: true, fontSize: 12, fontFamily: 'Menlo, Monaco, "Courier New", monospace', theme: { background: "#0a0a0a", foreground: "#e6edf3" }, cols: 80, rows: 20 });
    const fit = new FitAddon();
    fitAddon.current = fit;
    term.loadAddon(fit);
    term.open(terminalRef.current);
    fit.fit();
    terminal.current = term;

    const wsUrl = `ws://${window.location.host}/ws/terminal/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => { setIsConnected(true); term.writeln("\r\n\x1b[32m✓ Terminal connected\x1b[0m"); };
    ws.onmessage = (event) => { const data = JSON.parse(event.data); if (data.type === "output") term.write(data.data); };
    ws.onclose = () => setIsConnected(false);
    term.onData((data) => { if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: "input", data })); });

    const handleResize = () => fit.fit();
    window.addEventListener("resize", handleResize);
    return () => { window.removeEventListener("resize", handleResize); ws.close(); term.dispose(); };
  }, [sessionId]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white/5 border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className={cn("w-2 h-2 rounded-full", isConnected ? "bg-green-500" : "bg-red-500")} />
          <span className="text-xs text-gray-400">{isConnected ? "Connected" : "Disconnected"}</span>
        </div>
        <button onClick={() => terminal.current?.clear()} className="p-1.5 hover:bg-white/5 rounded text-gray-400"><Trash2 className="w-3.5 h-3.5" /></button>
      </div>
      <div className="flex-1 p-2 overflow-hidden"><div ref={terminalRef} className="h-full w-full" /></div>
    </div>
  );
}

// Browser Panel
function BrowserPanel({ sessionId }: { sessionId: string }) {
  const [url, setUrl] = useState("https://google.com");
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const wsUrl = `ws://${window.location.host}/ws/browser/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.onmessage = (event) => { const data = JSON.parse(event.data); if (data.type === "screenshot") { setScreenshot(data.data); setIsLoading(false); } };
    return () => ws.close();
  }, [sessionId]);

  const sendAction = (action: string, params: any = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) { setIsLoading(true); wsRef.current.send(JSON.stringify({ type: "action", action, params })); }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-2 bg-white/5 border-b border-white/5">
        <button onClick={() => sendAction("go_back")} className="p-1.5 hover:bg-white/5 rounded text-gray-400"><ChevronLeft className="w-4 h-4" /></button>
        <button onClick={() => sendAction("go_forward")} className="p-1.5 hover:bg-white/5 rounded text-gray-400"><ChevronRight className="w-4 h-4" /></button>
        <input value={url} onChange={(e) => setUrl(e.target.value)} onKeyDown={(e) => e.key === "Enter" && sendAction("navigate", { url })} className="flex-1 bg-white/5 border-0 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:ring-1 focus:ring-orange-500" />
        <button onClick={() => sendAction("navigate", { url })} className="px-3 py-1.5 bg-orange-600 hover:bg-orange-500 rounded text-sm text-white">Go</button>
        <button onClick={() => sendAction("screenshot")} className="p-1.5 hover:bg-white/5 rounded text-gray-400"><Camera className="w-4 h-4" /></button>
      </div>
      <div className="flex-1 bg-white/5 overflow-auto p-4">
        {screenshot ? <img src={`data:image/png;base64,${screenshot}`} alt="Browser" className="max-w-full h-auto rounded border border-white/10" /> : <div className="flex flex-col items-center justify-center h-full text-gray-500"><Globe className="w-12 h-12 mb-4 opacity-50" /><p className="text-sm">Navigate to a URL to start browsing</p></div>}
      </div>
    </div>
  );
}

// Files Panel
function FilesPanel() {
  const [files, setFiles] = useState<FileNode[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState("");

  useEffect(() => { fetchFiles(); }, []);

  const fetchFiles = async () => {
    try { const res = await fetch("/api/files/list?path=/"); if (res.ok) { const data = await res.json(); setFiles(data.files || []); } } catch (e) { }
  };

  const loadFile = async (path: string) => {
    try { const res = await fetch(`/api/files/read?path=${encodeURIComponent(path)}`); if (res.ok) { const data = await res.json(); setFileContent(data.content); setSelectedFile(path); } } catch (e) { }
  };

  const renderFileTree = (nodes: FileNode[], depth = 0) => {
    return nodes.map((node) => (
      <div key={node.path}>
        <button className={cn("w-full flex items-center gap-1 px-2 py-1.5 text-sm hover:bg-white/5 transition-colors", selectedFile === node.path && "bg-orange-500/20 text-orange-400")} style={{ paddingLeft: `${depth * 12 + 8}px` }} onClick={() => node.type === "directory" ? null : loadFile(node.path)}>
          {node.type === "directory" ? <Folder className="w-4 h-4 text-yellow-500" /> : <FileText className="w-4 h-4 text-blue-500" />}
          <span className="truncate">{node.name}</span>
        </button>
      </div>
    ));
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 bg-white/5 border-b border-white/5">
        <span className="text-xs font-medium text-gray-400">Workspace</span>
        <button onClick={fetchFiles} className="p-1.5 hover:bg-white/5 rounded text-gray-400"><RefreshCw className="w-3.5 h-3.5" /></button>
      </div>
      <ScrollArea className="flex-1">{files.length > 0 ? renderFileTree(files) : <div className="text-center text-xs text-gray-500 py-4">No files</div>}</ScrollArea>
      {selectedFile && (
        <div className="h-1/2 border-t border-white/5">
          <div className="flex items-center justify-between px-3 py-2 bg-white/5">
            <span className="text-xs text-gray-400 truncate">{selectedFile.split("/").pop()}</span>
            <button onClick={() => setSelectedFile(null)} className="p-1 hover:bg-white/5 rounded"><X className="w-3 h-3" /></button>
          </div>
          <Editor height="100%" value={fileContent} onChange={(v) => setFileContent(v || "")} theme="vs-dark" options={{ minimap: { enabled: false }, fontSize: 11, lineNumbers: "on" }} />
        </div>
      )}
    </div>
  );
}

export default AetherPanelV2;
