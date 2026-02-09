"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  Clock,
  Shield,
  Terminal,
  Globe,
  FileCode,
  Search
} from "lucide-react";
import { Button } from "./ui/button";

interface ApprovalRequest {
  id: string;
  tool: string;
  params: Record<string, any>;
  operation_description: string;
  risk_level: "low" | "medium" | "high";
  requester_info?: {
    user_id?: string;
    session_id?: string;
    ip_address?: string;
  };
}

interface ApprovalGateProps {
  request: ApprovalRequest | null;
  onApprove: (requestId: string, trustDuration?: number) => void;
  onReject: (requestId: string, reason?: string) => void;
  className?: string;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  terminal: <Terminal className="w-5 h-5" />,
  browser: <Globe className="w-5 h-5" />,
  file: <FileCode className="w-5 h-5" />,
  search: <Search className="w-5 h-5" />,
  default: <Terminal className="w-5 h-5" />,
};

const RISK_COLORS = {
  low: "text-green-400 border-green-500/30 bg-green-500/10",
  medium: "text-yellow-400 border-yellow-500/30 bg-yellow-500/10",
  high: "text-red-400 border-red-500/30 bg-red-500/10",
};

export function ApprovalGate({ 
  request, 
  onApprove, 
  onReject,
  className 
}: ApprovalGateProps) {
  const [trustDuration, setTrustDuration] = useState<number | undefined>(undefined);
  
  if (!request) return null;

  const toolName = request.tool.toLowerCase();
  const icon = TOOL_ICONS[toolName] || TOOL_ICONS.default;
  const riskColor = RISK_COLORS[request.risk_level] || RISK_COLORS.medium;

  const handleApprove = () => {
    onApprove(request.id, trustDuration);
  };

  const handleReject = () => {
    onReject(request.id, "User rejected the operation");
  };

  return (
    <div className={cn(
      "fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm",
      className
    )}>
      <div className="w-full max-w-lg mx-4 bg-[#141414] border border-white/10 rounded-xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className={cn("px-6 py-4 border-b", riskColor)}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-white/10">
              <AlertTriangle className="w-6 h-6" />
            </div>
            <div>
              <h3 className="font-semibold text-lg">Approval Required</h3>
              <p className="text-sm opacity-80">
                The agent wants to execute a {request.risk_level}-risk operation
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {/* Tool Info */}
          <div className="flex items-start gap-4 p-4 bg-white/5 rounded-lg">
            <div className="p-2 rounded bg-white/10 text-orange-400">
              {icon}
            </div>
            <div className="flex-1">
              <div className="font-medium capitalize text-white">
                {request.tool}
              </div>
              <div className="text-sm text-gray-400 mt-1">
                {request.operation_description}
              </div>
            </div>
          </div>

          {/* Params */}
          {request.params && Object.keys(request.params).length > 0 && (
            <div className="space-y-2">
              <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">
                Parameters
              </div>
              <div className="p-3 bg-black/30 rounded-lg font-mono text-xs text-gray-300 overflow-x-auto">
                <pre>{JSON.stringify(request.params, null, 2)}</pre>
              </div>
            </div>
          )}

          {/* Trust Duration */}
          <div className="space-y-2">
            <div className="text-xs font-medium text-gray-500 uppercase tracking-wider">
              Remember my choice
            </div>
            <div className="flex gap-2">
              {[
                { label: "Just this once", value: undefined },
                { label: "5 min", value: 300 },
                { label: "30 min", value: 1800 },
                { label: "1 hour", value: 3600 },
                { label: "Always", value: -1 },
              ].map((option) => (
                <button
                  key={option.label}
                  onClick={() => setTrustDuration(option.value)}
                  className={cn(
                    "px-3 py-1.5 text-xs rounded-lg transition-all",
                    trustDuration === option.value
                      ? "bg-orange-500 text-white"
                      : "bg-white/5 text-gray-400 hover:bg-white/10"
                  )}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="px-6 py-4 bg-white/5 border-t border-white/10 flex items-center gap-3">
          <Button
            onClick={handleReject}
            variant="outline"
            className="flex-1 bg-transparent border-red-500/30 text-red-400 hover:bg-red-500/10 hover:text-red-300"
          >
            <XCircle className="w-4 h-4 mr-2" />
            Deny
          </Button>
          <Button
            onClick={handleApprove}
            className="flex-1 bg-green-600 hover:bg-green-500 text-white"
          >
            <CheckCircle2 className="w-4 h-4 mr-2" />
            Approve
          </Button>
        </div>
      </div>
    </div>
  );
}

export default ApprovalGate;
