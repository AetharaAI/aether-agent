"use client";

import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  RefreshCw,
  MousePointerClick,
  Type,
  Camera,
  ChevronLeft,
  ChevronRight,
  Maximize2,
  Minimize2,
  Globe,
  Loader2,
} from "lucide-react";

interface BrowserPanelProps {
  sessionId: string;
  className?: string;
}

interface BrowserState {
  url: string;
  title: string;
  screenshot: string | null;
  isLoading: boolean;
  logs: string[];
}

export function BrowserPanel({ sessionId, className }: BrowserPanelProps) {
  const [state, setState] = useState<BrowserState>({
    url: "",
    title: "",
    screenshot: null,
    isLoading: false,
    logs: [],
  });
  const [navigateUrl, setNavigateUrl] = useState("https://google.com");
  const [isExpanded, setIsExpanded] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const screenshotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const wsUrl = `ws://${window.location.host}/ws/browser/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      addLog("Connected to browser session");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case "screenshot":
          setState((prev) => ({
            ...prev,
            screenshot: data.data,
            isLoading: false,
          }));
          break;
        case "page_info":
          setState((prev) => ({
            ...prev,
            url: data.url,
            title: data.title,
          }));
          break;
        case "action_complete":
          addLog(`Action completed: ${data.action}`);
          break;
        case "error":
          addLog(`Error: ${data.message}`);
          setState((prev) => ({ ...prev, isLoading: false }));
          break;
        case "log":
          addLog(data.message);
          break;
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      addLog("Disconnected from browser");
    };

    ws.onerror = (err) => {
      addLog("Connection error");
    };

    return () => {
      ws.close();
    };
  }, [sessionId]);

  const addLog = (message: string) => {
    setState((prev) => ({
      ...prev,
      logs: [...prev.logs.slice(-50), `[${new Date().toLocaleTimeString()}] ${message}`],
    }));
  };

  const sendAction = (action: string, params: any = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setState((prev) => ({ ...prev, isLoading: true }));
      wsRef.current.send(JSON.stringify({ type: "action", action, params }));
    }
  };

  const handleNavigate = () => {
    if (navigateUrl) {
      sendAction("navigate", { url: navigateUrl });
    }
  };

  const handleScreenshot = () => {
    sendAction("screenshot");
  };

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!screenshotRef.current || state.isLoading) return;
    
    const rect = screenshotRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    
    sendAction("click", { x: Math.round(x), y: Math.round(y) });
  };

  const handleGoBack = () => sendAction("go_back");
  const handleGoForward = () => sendAction("go_forward");
  const handleRefresh = () => sendAction("refresh");

  return (
    <div
      className={cn(
        "flex flex-col border border-border rounded-lg overflow-hidden bg-background transition-all duration-300",
        isExpanded ? "fixed inset-4 z-50" : "h-[500px]",
        className
      )}
    >
      {/* Browser Header */}
      <div className="flex items-center gap-2 px-3 py-2 bg-muted/50 border-b border-border">
        {/* Navigation */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleGoBack}
            disabled={state.isLoading}
          >
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleGoForward}
            disabled={state.isLoading}
          >
            <ChevronRight className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleRefresh}
            disabled={state.isLoading}
          >
            <RefreshCw className={cn("w-4 h-4", state.isLoading && "animate-spin")} />
          </Button>
        </div>

        {/* URL Bar */}
        <div className="flex-1 flex items-center gap-2">
          <Globe className="w-4 h-4 text-muted-foreground" />
          <Input
            value={navigateUrl}
            onChange={(e) => setNavigateUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleNavigate()}
            placeholder="Enter URL..."
            className="h-7 text-sm"
          />
          <Button
            size="sm"
            className="h-7"
            onClick={handleNavigate}
            disabled={state.isLoading}
          >
            Go
          </Button>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={handleScreenshot}
            disabled={state.isLoading}
            title="Take screenshot"
          >
            <Camera className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? "Minimize" : "Maximize"}
          >
            {isExpanded ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>

      {/* Browser Content */}
      <div className="flex-1 flex min-h-0">
        {/* Screenshot View */}
        <div className="flex-1 relative bg-muted/30 overflow-auto">
          {state.screenshot ? (
            <div
              ref={screenshotRef}
              className="relative inline-block cursor-crosshair"
              onClick={handleClick}
            >
              <img
                src={`data:image/png;base64,${state.screenshot}`}
                alt="Browser screenshot"
                className="max-w-full h-auto"
              />
              {state.isLoading && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                  <Loader2 className="w-8 h-8 animate-spin text-white" />
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <Globe className="w-12 h-12 mb-4 opacity-50" />
              <p className="text-sm">Navigate to a URL to start browsing</p>
              {state.isLoading && <Loader2 className="w-6 h-6 animate-spin mt-4" />}
            </div>
          )}
        </div>

        {/* Logs Panel */}
        <div className="w-48 border-l border-border bg-muted/20 flex flex-col">
          <div className="px-2 py-1.5 text-xs font-medium text-muted-foreground border-b border-border">
            Browser Logs
          </div>
          <div className="flex-1 overflow-auto p-2 space-y-1">
            {state.logs.map((log, i) => (
              <div key={i} className="text-[10px] text-muted-foreground font-mono leading-tight">
                {log}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Browser Footer */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/30 border-t border-border text-[10px] text-muted-foreground">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              isConnected ? "bg-green-500" : "bg-red-500"
            )}
          />
          <span>{isConnected ? "Connected" : "Disconnected"}</span>
        </div>
        <div className="truncate max-w-[50%]">
          {state.title || state.url || "No page loaded"}
        </div>
      </div>
    </div>
  );
}

export default BrowserPanel;
