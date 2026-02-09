"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal } from "xterm";
import { FitAddon } from "xterm-addon-fit";
import { WebLinksAddon } from "xterm-addon-web-links";
import "xterm/css/xterm.css";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Maximize2, Minimize2, Trash2, Copy, Power } from "lucide-react";

interface TerminalPanelProps {
  sessionId: string;
  className?: string;
}

export function TerminalPanel({ sessionId, className }: TerminalPanelProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const terminal = useRef<Terminal | null>(null);
  const fitAddon = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Initialize xterm
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      theme: {
        background: "#0d1117",
        foreground: "#e6edf3",
        cursor: "#e6edf3",
        selectionBackground: "#264f78",
        black: "#010409",
        red: "#ff7b72",
        green: "#3fb950",
        yellow: "#d29922",
        blue: "#58a6ff",
        magenta: "#f778ba",
        cyan: "#39c5cf",
        white: "#e6edf3",
      },
      cols: 80,
      rows: 24,
    });

    // Add addons
    const fit = new FitAddon();
    fitAddon.current = fit;
    term.loadAddon(fit);
    term.loadAddon(new WebLinksAddon());

    // Open terminal
    term.open(terminalRef.current);
    fit.fit();

    terminal.current = term;

    // Connect to WebSocket
    const wsUrl = `ws://${window.location.host}/ws/terminal/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      term.writeln("\r\n\x1b[32m✓ Connected to Aether Terminal\x1b[0m");
      term.writeln("\x1b[36mType commands to execute in sandboxed environment\x1b[0m\r\n");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "output") {
        term.write(data.data);
      } else if (data.type === "error") {
        term.writeln(`\r\n\x1b[31mError: ${data.message}\x1b[0m\r\n`);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      term.writeln("\r\n\x1b[31m✗ Terminal disconnected\x1b[0m");
    };

    ws.onerror = (err) => {
      term.writeln("\r\n\x1b[31m✗ Connection error\x1b[0m");
    };

    // Handle user input
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "input", data }));
      }
    });

    // Handle resize
    const handleResize = () => {
      fit.fit();
      if (ws.readyState === WebSocket.OPEN) {
        const { cols, rows } = term;
        ws.send(JSON.stringify({ type: "resize", cols, rows }));
      }
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      ws.close();
      term.dispose();
    };
  }, [sessionId]);

  const clearTerminal = () => {
    terminal.current?.clear();
  };

  const copyToClipboard = () => {
    const selection = terminal.current?.getSelection();
    if (selection) {
      navigator.clipboard.writeText(selection);
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col border border-border rounded-lg overflow-hidden bg-[#0d1117] transition-all duration-300",
        isExpanded ? "fixed inset-4 z-50" : "h-96",
        className
      )}
    >
      {/* Terminal Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-muted/50 border-b border-border">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "w-2 h-2 rounded-full",
              isConnected ? "bg-green-500" : "bg-red-500"
            )}
          />
          <span className="text-xs font-medium text-muted-foreground">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
          <span className="text-xs text-muted-foreground">•</span>
          <span className="text-xs text-muted-foreground">Sandboxed Terminal</span>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={copyToClipboard}
            title="Copy selection"
          >
            <Copy className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={clearTerminal}
            title="Clear terminal"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? "Minimize" : "Maximize"}
          >
            {isExpanded ? (
              <Minimize2 className="w-3.5 h-3.5" />
            ) : (
              <Maximize2 className="w-3.5 h-3.5" />
            )}
          </Button>
        </div>
      </div>

      {/* Terminal Container */}
      <div className="flex-1 p-2 overflow-hidden">
        <div ref={terminalRef} className="h-full w-full" />
      </div>

      {/* Terminal Footer */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-muted/30 border-t border-border text-[10px] text-muted-foreground">
        <span>xterm.js • Docker Sandbox</span>
        <span>Session: {sessionId.slice(0, 8)}...</span>
      </div>
    </div>
  );
}

export default TerminalPanel;
