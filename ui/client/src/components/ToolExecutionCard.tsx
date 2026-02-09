import { useState } from "react";
import { 
  Loader2, 
  CheckCircle, 
  XCircle, 
  ChevronDown, 
  ChevronUp,
  Terminal,
  FileText,
  Globe,
  Code
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ToolExecution } from "@/hooks/useAgentRuntime";

interface ToolExecutionCardProps {
  tool: ToolExecution;
  isCurrent?: boolean;
}

export function ToolExecutionCard({ tool, isCurrent }: ToolExecutionCardProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  
  const getToolIcon = () => {
    switch (tool.tool) {
      case "web_search":
      case "browser_navigate":
        return <Globe className="w-4 h-4" />;
      case "execute_code":
        return <Code className="w-4 h-4" />;
      case "read_file":
      case "write_file":
        return <FileText className="w-4 h-4" />;
      case "shell_command":
        return <Terminal className="w-4 h-4" />;
      default:
        return <Terminal className="w-4 h-4" />;
    }
  };
  
  const getStatusIcon = () => {
    switch (tool.status) {
      case "running":
        return <Loader2 className="w-4 h-4 animate-spin text-blue-500" />;
      case "completed":
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case "failed":
      case "cancelled":
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return null;
    }
  };

  return (
    <div className={cn(
      "border rounded-lg overflow-hidden mb-2",
      isCurrent ? "border-blue-500/50 bg-blue-500/5" : "border-border/50 bg-card/30"
    )}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-3 hover:bg-muted/30 transition-colors"
      >
        <div className="flex items-center gap-2">
          {getStatusIcon()}
          <span className="text-muted-foreground">
            {getToolIcon()}
          </span>
          <span className="font-medium text-sm">
            {tool.tool}
          </span>
          {tool.requires_approval && (
            <span className="text-xs bg-yellow-500/20 text-yellow-500 px-1.5 py-0.5 rounded">
              Approval Required
            </span>
          )}
        </div>
        <ChevronDown className={cn(
          "w-4 h-4 text-muted-foreground transition-transform",
          isExpanded && "rotate-180"
        )} />
      </button>
      
      {isExpanded && (
        <div className="px-3 pb-3 border-t border-border/30">
          {/* Parameters */}
          <div className="mt-2">
            <p className="text-xs text-muted-foreground mb-1">Parameters:</p>
            <pre className="text-xs bg-muted/50 rounded p-2 overflow-x-auto">
              {JSON.stringify(tool.params, null, 2)}
            </pre>
          </div>
          
          {/* Output */}
          {tool.output && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Output:</p>
              <div className="text-xs bg-black/50 rounded p-2 font-mono max-h-32 overflow-y-auto">
                {tool.output}
              </div>
            </div>
          )}
          
          {/* Logs */}
          {tool.logs && tool.logs.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Logs:</p>
              <div className="text-xs bg-black/50 rounded p-2 font-mono text-green-400 max-h-32 overflow-y-auto">
                {tool.logs.map((log, i) => (
                  <div key={i}>{log}</div>
                ))}
              </div>
            </div>
          )}
          
          {/* Screenshot for browser tools */}
          {tool.screenshot && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Screenshot:</p>
              <img
                src={`data:image/png;base64,${tool.screenshot}`}
                alt="Browser view"
                className="rounded border border-border/30 max-h-48 object-contain"
              />
            </div>
          )}
          
          {/* Files modified */}
          {tool.files_modified && tool.files_modified.length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-muted-foreground mb-1">Files Modified:</p>
              <div className="flex flex-wrap gap-1">
                {tool.files_modified.map((file, i) => (
                  <span key={i} className="text-xs bg-muted px-2 py-1 rounded">
                    {file}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default ToolExecutionCard;
