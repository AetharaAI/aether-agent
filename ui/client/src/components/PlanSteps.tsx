import { CheckCircle, Circle, Loader2, Play } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PlanStep } from "@/hooks/useAgentRuntime";

interface PlanStepsProps {
  steps: PlanStep[];
  currentStep: number;
}

export function PlanSteps({ steps, currentStep }: PlanStepsProps) {
  if (steps.length === 0) return null;

  return (
    <div className="bg-muted/30 rounded-lg border border-border/50 p-4 mb-4">
      <h3 className="text-sm font-medium mb-3 flex items-center gap-2">
        <span className="text-muted-foreground">Plan</span>
        <span className="text-xs bg-muted px-2 py-0.5 rounded">
          {steps.length} steps
        </span>
      </h3>
      
      <div className="space-y-1">
        {steps.map((step, index) => {
          const isCompleted = index < currentStep;
          const isCurrent = index === currentStep;
          const isPending = index > currentStep;
          
          return (
            <div
              key={index}
              className={cn(
                "flex items-start gap-3 p-2 rounded transition-colors",
                isCurrent && "bg-blue-500/10 border border-blue-500/30",
                isCompleted && "opacity-60",
                isPending && "opacity-40"
              )}
            >
              {/* Status Icon */}
              <div className="shrink-0 mt-0.5">
                {isCompleted ? (
                  <CheckCircle className="w-4 h-4 text-green-500" />
                ) : isCurrent ? (
                  <div className="w-4 h-4 rounded-full border-2 border-blue-500 flex items-center justify-center">
                    <Loader2 className="w-3 h-3 text-blue-500 animate-spin" />
                  </div>
                ) : (
                  <Circle className="w-4 h-4 text-muted-foreground" />
                )}
              </div>
              
              {/* Step Content */}
              <div className="flex-1 min-w-0">
                <p className={cn(
                  "text-sm",
                  isCurrent ? "font-medium text-foreground" : "text-muted-foreground"
                )}>
                  {step.description}
                </p>
                
                {/* Tools indicator */}
                {step.tool_types && step.tool_types.length > 0 && (
                  <div className="flex gap-1 mt-1 flex-wrap">
                    {step.tool_types.map((tool, i) => (
                      <span
                        key={i}
                        className={cn(
                          "text-[10px] px-1.5 py-0.5 rounded",
                          isCurrent 
                            ? "bg-blue-500/20 text-blue-400" 
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                
                {/* Expected output */}
                {step.expected_output && isCurrent && (
                  <p className="text-xs text-muted-foreground mt-1">
                    Expected: {step.expected_output}
                  </p>
                )}
              </div>
              
              {/* Step Number */}
              <span className={cn(
                "text-xs font-mono",
                isCurrent ? "text-blue-500" : "text-muted-foreground"
              )}>
                {String(index + 1).padStart(2, "0")}
              </span>
            </div>
          );
        })}
      </div>
      
      {/* Progress bar */}
      <div className="mt-3 h-1 bg-muted rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-all duration-500"
          style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
        />
      </div>
    </div>
  );
}

export default PlanSteps;
