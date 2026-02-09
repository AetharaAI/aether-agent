import { useEffect, useRef, useState, useCallback } from "react";

export interface Attachment {
  id: string;
  filename: string;
  path?: string;
  size: number;
  mimeType?: string;
}

export interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: string;
  thinking?: string | null;
  isStreaming?: boolean;
  attachments?: Attachment[];
}

interface UseAetherWebSocketReturn {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  sendMessage: (content: string, attachments?: Attachment[]) => void;
  clearMessages: () => void;
  isConnected: boolean;
  isReconnecting: boolean;
  reconnectAttempt: number;
  error: string | null;
  isStreaming: boolean;
  streamingContent: string;
}

// Use relative URL so Vite proxy can forward to backend
import { WS_BASE_URL } from "@/lib/api";

const WS_URL = `${WS_BASE_URL}/ws/chat`;

// Exponential backoff configuration
const INITIAL_RETRY_DELAY = 1000;
const MAX_RETRY_DELAY = 30000;
const BACKOFF_MULTIPLIER = 2;

// Stream parsing state machine states
type StreamState = "think" | "answer" | "raw";

interface StreamBuffer {
  think: string;
  answer: string;
  state: StreamState;
  thinkComplete: boolean;
}

/**
 * Streaming state machine for parsing <think> and <answer> tags.
 * Maintains separate buffers and routes deltas based on tag state.
 */
function createStreamBuffer(): StreamBuffer {
  return {
    think: "",
    answer: "",
    state: "raw",
    thinkComplete: false,
  };
}

/**
 * Apply a delta to the stream buffer using state machine logic.
 * Routes content into think or answer buffers based on tag detection.
 */
function applyDelta(buffer: StreamBuffer, delta: string): StreamBuffer {
  // If we've already completed the think section, everything goes to answer
  if (buffer.thinkComplete) {
    return { ...buffer, answer: buffer.answer + delta };
  }

  // Append to current accumulated content for parsing
  const combined = buffer.state === "think" ? buffer.think + delta : buffer.answer + delta;
  
  // Check for think tag opening
  if (buffer.state === "raw") {
    const thinkOpenMatch = combined.match(/<think>/);
    if (thinkOpenMatch) {
      // Found opening tag, switch to think state
      const beforeThink = combined.slice(0, thinkOpenMatch.index);
      const afterThink = combined.slice(thinkOpenMatch.index! + 7); // 7 = "<think>".length
      return {
        ...buffer,
        think: afterThink,
        answer: beforeThink, // Any content before <think> goes to answer
        state: "think",
      };
    }
    // No think tag yet, accumulate in answer (raw mode)
    return { ...buffer, answer: combined };
  }
  
  // We're in think state, look for closing tag
  if (buffer.state === "think") {
    const thinkCloseMatch = combined.match(/<\/think>/);
    if (thinkCloseMatch) {
      // Found closing tag
      const thinkContent = combined.slice(0, thinkCloseMatch.index);
      const afterClose = combined.slice(thinkCloseMatch.index! + 8); // 8 = "</think>".length
      return {
        ...buffer,
        think: thinkContent,
        answer: afterClose,
        state: "answer",
        thinkComplete: true,
      };
    }
    // Still in think section
    return { ...buffer, think: combined };
  }
  
  // In answer state (after think closed)
  return { ...buffer, answer: buffer.answer + delta };
}

export function useAetherWebSocket(url: string = WS_URL): UseAetherWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryDelayRef = useRef(INITIAL_RETRY_DELAY);
  const streamingMessageIdRef = useRef<string | null>(null);
  const streamBufferRef = useRef<StreamBuffer | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        setIsReconnecting(false);
        setReconnectAttempt(0);
        setError(null);
        retryDelayRef.current = INITIAL_RETRY_DELAY;
      };

      ws.onmessage = (event) => {
        try {
          const rawMessage = JSON.parse(event.data);
          
          // Handle streaming deltas
          if (rawMessage.type === "delta" && rawMessage.content) {
            const delta = rawMessage.content;
            
            setStreamingContent((prev) => {
              const newContent = prev + delta;
              
              // Update the streaming message using state machine
              if (streamingMessageIdRef.current && streamBufferRef.current) {
                streamBufferRef.current = applyDelta(streamBufferRef.current, delta);
                
                setMessages((prevMessages) => {
                  const lastIndex = prevMessages.length - 1;
                  if (lastIndex >= 0 && prevMessages[lastIndex].id === streamingMessageIdRef.current) {
                    const updatedMessages = [...prevMessages];
                    updatedMessages[lastIndex] = {
                      ...updatedMessages[lastIndex],
                      content: streamBufferRef.current!.answer,
                      thinking: streamBufferRef.current!.think || null,
                    };
                    return updatedMessages;
                  }
                  return prevMessages;
                });
              }
              
              return newContent;
            });
            return;
          }
          
          // Handle streaming start
          if (rawMessage.type === "stream_start") {
            setIsStreaming(true);
            setStreamingContent("");
            streamBufferRef.current = createStreamBuffer();
            const messageId = `agent-stream-${Date.now()}`;
            streamingMessageIdRef.current = messageId;
            
            setMessages((prev) => [
              ...prev,
              {
                id: messageId,
                role: "agent",
                content: "",
                timestamp: rawMessage.timestamp || new Date().toISOString(),
                isStreaming: true,
              },
            ]);
            return;
          }
          
          // Handle streaming end
          if (rawMessage.type === "stream_end") {
            setIsStreaming(false);
            setStreamingContent("");
            streamBufferRef.current = null;
            
            if (streamingMessageIdRef.current) {
              setMessages((prevMessages) => {
                const lastIndex = prevMessages.length - 1;
                if (lastIndex >= 0 && prevMessages[lastIndex].id === streamingMessageIdRef.current) {
                  const updatedMessages = [...prevMessages];
                  updatedMessages[lastIndex] = {
                    ...updatedMessages[lastIndex],
                    isStreaming: false,
                  };
                  return updatedMessages;
                }
                return prevMessages;
              });
              streamingMessageIdRef.current = null;
            }
            return;
          }
          
          // Regular complete message (non-streaming fallback)
          const content = rawMessage.content || "";
          
          // Parse think/answer for non-streaming responses
          let answer = content;
          let thinking: string | null = null;
          
          const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/);
          const answerMatch = content.match(/<answer>([\s\S]*?)<\/answer>/);
          
          if (answerMatch) {
            answer = answerMatch[1].trim();
            thinking = thinkMatch ? thinkMatch[1].trim() : null;
          } else if (thinkMatch) {
            thinking = thinkMatch[1].trim();
            answer = content.replace(/<think>[\s\S]*?<\/think>/, "").trim();
          }
          
          const message: Message = {
            ...rawMessage,
            content: answer,
            thinking,
            isStreaming: false,
          };
          
          setMessages((prev) => [...prev, message]);
        } catch (err) {
          console.error("Failed to parse message:", err);
        }
      };

      ws.onerror = (event) => {
        console.error("WebSocket error:", event);
        setError("Connection error");
      };

      ws.onclose = () => {
        console.log("WebSocket disconnected");
        setIsConnected(false);
        wsRef.current = null;

        const nextDelay = Math.min(
          retryDelayRef.current * BACKOFF_MULTIPLIER,
          MAX_RETRY_DELAY
        );
        
        setIsReconnecting(true);
        setReconnectAttempt((prev) => prev + 1);
        
        console.log(`Reconnecting in ${retryDelayRef.current}ms (attempt ${reconnectAttempt + 1})...`);

        reconnectTimeoutRef.current = setTimeout(() => {
          retryDelayRef.current = nextDelay;
          connect();
        }, retryDelayRef.current);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error("Failed to create WebSocket:", err);
      setError("Failed to connect");
      setIsReconnecting(false);
    }
  }, [url, reconnectAttempt]);

  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect]);

  const sendMessage = useCallback((content: string, attachments?: Attachment[]) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ 
        message: content,
        attachments: attachments || [],
      }));
    } else {
      console.error("WebSocket is not connected");
      setError("Not connected");
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    streamBufferRef.current = null;
    streamingMessageIdRef.current = null;
  }, []);

  return {
    messages,
    setMessages,
    clearMessages,
    sendMessage,
    isConnected,
    isReconnecting,
    reconnectAttempt,
    error,
    isStreaming,
    streamingContent,
  };
}

export default useAetherWebSocket;
