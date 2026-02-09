"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { 
  Loader2, 
  Terminal, 
  Globe, 
  FileCode, 
  Search, 
  Brain,
  CheckCircle2,
  XCircle,
  Clock,
  AlertCircle
} from "lucide-react";
import type { ToolExecution, PlanStep } from "@/hooks/useAgentRuntime";

interface AgentActivityProps {
  status: string;
  currentStep?: number;
  plan?: PlanStep[];
  currentThinking?: string;
  thinkingStep?: string;
  toolExecutions?: ToolExecution[];
  className?: string;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  terminal: <Terminal className="w-4 h-4" />,
  browser: <Globe className="w-4 h-4" />,
  file: <FileCode className="w-4 h-4" />,
  search: <Search className="w-4 h-4" />,
  default: <Terminal className="w-4 h-4" />,
};

const STATUS_CONFIG: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
  idle: { color: "text-gray-400", label: "Ready", icon: <Clock className="w-4 h-4" /> },
  planning: { color: "text-blue-400", label: "Planning", icon: <Brain className="w-4 h-4" /> },
  thinking: { color: "text-purple-400", label: "Thinking", icon: <Brain className="w-4 h-4 animate-pulse" /> },
  tool_calling: { color: "text-yellow-400", label: "Using Tools", icon: <Loader2 className="w-4 h-4 animate-spin" /> },
  observing: { color: "text-green-400", label: "Analyzing", icon: <Loader2 className="w-4 h-4 animate-spin" /> },
  paused: { color: "text-orange-400", label: "Waiting for Approval", icon: <AlertCircle className="w-4 h-4" /> },
};

export function AgentActivity({
  status,
  currentStep = -1,
  plan = [],
  currentThinking = "",
  thinkingStep,
  toolExecutions = [],
  className,
}: AgentActivityProps) {
  const statusConfig = STATUS_CONFIG[status] || STATUS_CONFIG.idle;
  
  // Get active/running tools
  const activeTools = toolExecutions.filter(t => t.status === "running");
  const completedTools = toolExecutions.filter(t => t.status === "completed");
  const failedTools = toolExecutions.filter(t => t.status === "failed");

  // Don't show anything if idle and no history
  if (status === "idle" && toolExecutions.length === 0) {
    return null;
  }

  return (
    <div className={cn("space-y-4", className)}>
      {/* Current Status Header */}
      <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg border border-white/10">
        <div className={cn("flex items-center justify-center w-8 h-8 rounded-full bg-white/10", statusConfig.color)}>
          {statusConfig.icon}
        </div>
        <div className="flex-1">
          <div className={cn("font-medium text-sm", statusConfig.color)}>
            {statusConfig.label}
          </div>
          {thinkingStep && (
            <div className="text-xs text-gray-500 mt-0.5">{thinkingStep}</div>
          )}
        </div>
      </div>

      {/* Plan Steps */}
      {plan.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider px-1">
            Plan
          </div>
          <div className="space-y-1">
            {plan.map((step, idx) => {
              const isActive = idx === currentStep;
              const isCompleted = idx < currentStep;
              
              return (
                <div
                  key={idx}
                  className={cn(
                    "flex items-center gap-2 p-2 rounded-lg text-sm transition-all",
                    isActive && "bg-blue-500/10 border border-blue-500/20",
                    isCompleted && "opacity-50",
                    !isActive && !isCompleted && "opacity-30"
                  )}
                >
                  <div className={cn(
                    "w-5 h-5 rounded-full flex items-center justify-center text-xs font-medium",
                    isCompleted ? "bg-green-500/20 text-green-400" :
                    isActive ? "bg-blue-500/20 text-blue-400 animate-pulse" :
                    "bg-white/10 text-gray-500"
                  )}>
                    {isCompleted ? <CheckCircle2 className="w-3 h-3" /> : (idx + 1)}
                  </div>
                  <span className={cn(
                    "flex-1",
                    isActive ? "text-blue-300" : "text-gray-400"
                  )}>
                    {step.description}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Active Tool Executions */}
      {activeTools.length > 0 && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider px-1">
            Active Tools
          </div>
          <div className="space-y-2">
            {activeTools.map((tool) => (
              <ToolExecutionCard key={tool.id} execution={tool} isActive />
            ))}
          </div>
        </div>
      )}

      {/* Current Thinking */}
      {currentThinking && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider px-1">
            Reasoning
          </div>
          <div className="p-3 bg-purple-500/5 border border-purple-500/10 rounded-lg">
            <div className="text-sm text-purple-200/80 whitespace-pre-wrap font-mono">
              {currentThinking}
            </div>
          </div>
        </div>
      )}

      {/* Completed Tools Summary */}
      {(completedTools.length > 0 || failedTools.length > 0) && (
        <div className="space-y-2">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wider px-1">
            Completed
          </div>
          <div className="space-y-1">
            {completedTools.map((tool) => (
              <ToolExecutionCard key={tool.id} execution={tool} />
            ))}
            {failedTools.map((tool) => (
              <ToolExecutionCard key={tool.id} execution={tool} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ToolExecutionCard({ 
  execution, 
  isActive = false 
}: { 
  execution: ToolExecution; 
  isActive?: boolean;
}) {
  const toolName = execution.tool.toLowerCase();
  const icon = TOOL_ICONS[toolName] || TOOL_ICONS.default;
  
  const statusColors = {
    pending: "text-gray-400",
    running: "text-yellow-400",
    completed: "text-green-400",
    failed: "text-red-400",
    cancelled: "text-gray-500",
  };

  return (
    <div className={cn(
      "p-3 rounded-lg border transition-all",
      isActive 
        ? "bg-yellow-500/5 border-yellow-500/20" 
        : "bg-white/5 border-white/10"
    )}>
      <div className="flex items-center gap-3">
        <div className={cn("p-1.5 rounded bg-white/10", statusColors[execution.status])}>
          {icon}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm text-gray-200 capitalize">
              {execution.tool}
            </span>
            {execution.status === "running" && (
              <Loader2 className="w-3 h-3 animate-spin text-yellow-400" />
            )}
            {execution.status === "completed" && (
              <CheckCircle2 className="w-3 h-3 text-green-400" />
            )}
            {execution.status === "failed" && (
              <XCircle className="w-3 h-3 text-red-400" />
            )}
          </div>
          {execution.params && Object.keys(execution.params).length > 0 && (
            <div className="text-xs text-gray-500 mt-1 truncate">
              {JSON.stringify(execution.params).slice(0, 80)}...
            </div>
          )}
        </div>
      </div>
      
      {/* Live Logs */}
      {isActive && execution.logs && execution.logs.length > 0 && (
        <div className="mt-2 p-2 bg-black/30 rounded text-xs font-mono text-gray-400 max-h-24 overflow-y-auto">
          {execution.logs.slice(-5).map((log, i) => (
            <div key={i} className="truncate">{log}</div>
          ))}
        </div>
      )}
      
      {/* Output Preview */}
      {!isActive && execution.output && (
        <div className="mt-2 text-xs text-gray-500 line-clamp-2">
          {execution.output.slice(0, 150)}...
        </div>
      )}
    </div>
  );
}

export default AgentActivity;
