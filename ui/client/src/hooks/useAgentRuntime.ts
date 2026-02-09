import { useState, useCallback, useRef, useEffect } from "react";
import { WS_BASE_URL } from "@/lib/api";

// Types for agent runtime events
export interface AgentEvent {
  event_type: string;
  timestamp: string;
  payload: any;
}

export interface PlanStep {
  description: string;
  tool_types?: string[];
  expected_output?: string;
}

export interface ToolExecution {
  id: string;
  tool: string;
  params: Record<string, any>;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  output?: string;
  logs?: string[];
  screenshot?: string;
  files_modified?: string[];
  started_at?: string;
  ended_at?: string;
  requires_approval?: boolean;
}

export interface ApprovalRequest {
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

export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
  thinking?: string;
  timestamp: string;
  attachments?: Attachment[];
}

export interface Attachment {
  type: string;
  filename?: string;
  mime_type?: string;
  content?: string;
  url?: string;
}

export interface AgentState {
  status: "idle" | "planning" | "thinking" | "tool_calling" | "observing" | "compiling" | "paused";
  current_step: number;
  plan: PlanStep[];
  current_thinking: string;
  thinking_step?: string;
}

export function useAgentRuntime(sessionId: string) {
  const [state, setState] = useState<AgentState>({
    status: "idle",
    current_step: -1,
    plan: [],
    current_thinking: "",
  });
  
  const [messages, setMessages] = useState<AgentMessage[]>([]);
  const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([]);
  const [pendingApproval, setPendingApproval] = useState<ApprovalRequest | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const currentAssistantMessageRef = useRef<string>("");

  // Connect to agent WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    // Use WS_BASE_URL which handles dev vs production correctly
    const wsUrl = `${WS_BASE_URL}/ws/agent/${sessionId}`;
    console.log("Connecting to Agent WebSocket:", wsUrl);
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log("Agent WebSocket connected");
      setIsConnected(true);
      setError(null);
    };
    
    ws.onmessage = (event) => {
      try {
        const data: AgentEvent = JSON.parse(event.data);
        handleEvent(data);
      } catch (err) {
        console.error("Failed to parse agent event:", err);
      }
    };
    
    ws.onclose = () => {
      console.log("Agent WebSocket closed");
      setIsConnected(false);
      
      // Reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 3000);
    };
    
    ws.onerror = (err) => {
      console.error("Agent WebSocket error:", err);
      setError("Connection error");
    };
    
    wsRef.current = ws;
  }, [sessionId]);

  // Disconnect from WebSocket
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  // Handle incoming events
  const handleEvent = useCallback((event: AgentEvent) => {
    setEvents((prev) => [...prev, event]);
    
    switch (event.event_type) {
      case "state_changed":
        setState((prev) => ({
          ...prev,
          status: event.payload.new_state,
        }));
        break;
        
      case "plan_created":
        setState((prev) => ({
          ...prev,
          plan: event.payload.steps,
          current_step: 0,
        }));
        break;
        
      case "thinking_start":
        setState((prev) => ({
          ...prev,
          current_thinking: "",
          thinking_step: event.payload.step?.description || "Reasoning...",
        }));
        break;
        
      case "thinking_chunk":
        setState((prev) => ({
          ...prev,
          current_thinking: prev.current_thinking + event.payload.chunk,
        }));
        break;
        
      case "thinking_complete":
        // Thinking is complete, will be added to messages on response_complete
        break;
        
      case "tool_call_start":
        setToolExecutions((prev) => [
          ...prev,
          {
            id: event.payload.tool_id,
            tool: event.payload.tool,
            params: event.payload.params,
            status: "running",
            started_at: event.timestamp,
            requires_approval: event.payload.requires_approval,
          },
        ]);
        break;
        
      case "tool_call_chunk":
        setToolExecutions((prev) =>
          prev.map((t) =>
            t.id === event.payload.tool_id
              ? {
                  ...t,
                  logs: [...(t.logs || []), event.payload.chunk],
                }
              : t
          )
        );
        break;
        
      case "tool_call_complete":
        setToolExecutions((prev) =>
          prev.map((t) =>
            t.id === event.payload.tool_id
              ? {
                  ...t,
                  status: "completed",
                  output: event.payload.result,
                  ended_at: event.timestamp,
                  screenshot: event.payload.screenshot,
                  files_modified: event.payload.files_modified,
                }
              : t
          )
        );
        break;
        
      case "tool_call_failed":
        setToolExecutions((prev) =>
          prev.map((t) =>
            t.id === event.payload.tool_id
              ? {
                  ...t,
                  status: "failed",
                  output: event.payload.error,
                  ended_at: event.timestamp,
                }
              : t
          )
        );
        break;
        
      case "approval_required":
        setPendingApproval(event.payload);
        setState((prev) => ({ ...prev, status: "paused" }));
        break;
        
      case "step_complete":
        setState((prev) => ({
          ...prev,
          current_step: event.payload.step_index + 1,
        }));
        break;
        
      case "response_chunk":
        currentAssistantMessageRef.current += event.payload.chunk;
        break;
        
      case "response_complete":
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: event.payload.response || currentAssistantMessageRef.current,
            thinking: state.current_thinking,
            timestamp: event.timestamp,
          },
        ]);
        currentAssistantMessageRef.current = "";
        setState((prev) => ({
          ...prev,
          current_thinking: "",
          thinking_step: undefined,
        }));
        break;
        
      case "error":
        setError(event.payload.message);
        break;
    }
  }, [state.current_thinking]);

  // Send message to agent
  const sendMessage = useCallback(
    async (content: string, attachments?: Attachment[]) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        setError("Not connected");
        return;
      }

      // Add user message to list
      const userMessage: AgentMessage = {
        role: "user",
        content,
        timestamp: new Date().toISOString(),
        attachments,
      };
      setMessages((prev) => [...prev, userMessage]);

      // Send to server
      wsRef.current.send(
        JSON.stringify({
          type: "user_input",
          message: content,
          attachments,
        })
      );
    },
    []
  );

  // Approve a pending operation
  const approveOperation = useCallback(
    (requestId: string, trustDuration?: number) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      wsRef.current.send(
        JSON.stringify({
          type: "approval_response",
          request_id: requestId,
          approved: true,
          trust_duration_seconds: trustDuration,
        })
      );

      setPendingApproval(null);
    },
    []
  );

  // Reject a pending operation
  const rejectOperation = useCallback(
    (requestId: string, reason?: string) => {
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

      wsRef.current.send(
        JSON.stringify({
          type: "approval_response",
          request_id: requestId,
          approved: false,
          reason,
        })
      );

      setPendingApproval(null);
    },
    []
  );

  // Cancel current task
  const cancelTask = useCallback(() => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    wsRef.current.send(
      JSON.stringify({
        type: "cancel_task",
      })
    );
  }, []);

  // Clear all messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    setToolExecutions([]);
    setEvents([]);
    setState({
      status: "idle",
      current_step: -1,
      plan: [],
      current_thinking: "",
    });
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Get current tool being executed
  const currentTool = toolExecutions.find((t) => t.status === "running");

  return {
    // State
    state,
    messages,
    toolExecutions,
    pendingApproval,
    events,
    isConnected,
    error,
    currentTool,

    // Actions
    sendMessage,
    approveOperation,
    rejectOperation,
    cancelTask,
    clearMessages,
    connect,
    disconnect,
  };
}

export default useAgentRuntime;
