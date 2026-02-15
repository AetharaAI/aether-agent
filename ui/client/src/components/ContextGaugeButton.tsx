/**
 * Context Gauge Button Component
 * Small circular button showing context usage percentage
 * Placed next to paperclip and other input buttons
 */

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { Zap } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface ContextGaugeButtonProps {
  tokenUsage: {
    used: number;
    max: number;
    percent: number;
  };
}

export function ContextGaugeButton({ tokenUsage }: ContextGaugeButtonProps) {
  const [isCompacting, setIsCompacting] = useState(false);
  const [showTooltip, setShowTooltip] = useState(false);

  const handleCompact = async () => {
    try {
      setIsCompacting(true);
      await apiFetch("/api/context/compress", {
        method: "POST",
      });
    } catch (error) {
      console.error("Compaction failed:", error);
    } finally {
      setIsCompacting(false);
    }
  };

  // Determine color based on usage
  const getColor = () => {
    if (tokenUsage.percent < 50) return "text-green-500 border-green-500/30 bg-green-500/10 hover:bg-green-500/20";
    if (tokenUsage.percent < 80) return "text-yellow-500 border-yellow-500/30 bg-yellow-500/10 hover:bg-yellow-500/20";
    return "text-red-500 border-red-500/30 bg-red-500/10 hover:bg-red-500/20";
  };

  const remaining = tokenUsage.max - tokenUsage.used;
  const remainingPercent = 100 - tokenUsage.percent;

  return (
    <div className="relative">
      <button
        onClick={handleCompact}
        disabled={isCompacting || tokenUsage.percent < 10}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        className={cn(
          "p-2 rounded-lg border transition-all",
          getColor(),
          isCompacting && "opacity-50 cursor-wait",
          tokenUsage.percent > 80 && "animate-pulse"
        )}
        title={`${tokenUsage.percent}% context used`}
      >
        <div className="relative w-4 h-4 flex items-center justify-center">
          {isCompacting ? (
            <Zap className="w-4 h-4 animate-spin" />
          ) : (
            <span className="text-[10px] font-bold leading-none">
              {tokenUsage.percent}%
            </span>
          )}
        </div>
      </button>

      {/* Hover Tooltip */}
      {showTooltip && !isCompacting && (
        <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-black border border-white/10 rounded-lg shadow-xl whitespace-nowrap text-xs z-50">
          <div className="space-y-1">
            <div className="font-medium text-white">
              {remainingPercent}% of context remaining
            </div>
            <div className="text-gray-400">
              {remaining.toLocaleString()} / {tokenUsage.max.toLocaleString()} tokens free
            </div>
            {tokenUsage.percent > 80 && (
              <div className="text-red-400 font-medium pt-1 border-t border-white/10">
                Click to compact now
              </div>
            )}
            {tokenUsage.percent <= 80 && tokenUsage.percent >= 10 && (
              <div className="text-gray-500 pt-1 border-t border-white/10">
                Click to compact
              </div>
            )}
          </div>
          {/* Tooltip arrow */}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2 -mt-px">
            <div className="border-4 border-transparent border-t-black" />
          </div>
        </div>
      )}
    </div>
  );
}

export default ContextGaugeButton;
