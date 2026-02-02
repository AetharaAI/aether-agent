import { useEffect, useRef, useState, useCallback } from "react";

export interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  timestamp: string;
  thinking?: string; // Extracted thinking content for models like Qwen3
}

interface UseAetherWebSocketReturn {
  messages: Message[];
  sendMessage: (content: string) => void;
  isConnected: boolean;
  error: string | null;
}

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:16380/ws/chat";

/**
 * Parse thinking blocks from model responses
 * Models like Qwen3 wrap thinking content in <think>...</think> tags
 */
function parseThinkingBlocks(content: string): { content: string; thinking?: string } {
  // Match <think>...</think> blocks (including multiline)
  const thinkRegex = /<think>([\s\S]*?)<\/think>/g;
  const matches = [...content.matchAll(thinkRegex)];
  
  if (matches.length === 0) {
    return { content };
  }
  
  // Extract all thinking content
  const thinkingParts = matches.map(match => match[1].trim());
  
  // Remove thinking blocks from main content
  let cleanContent = content.replace(thinkRegex, "").trim();
  
  // Clean up extra whitespace from removal
  cleanContent = cleanContent.replace(/\n{3,}/g, "\n\n");
  
  return {
    content: cleanContent,
    thinking: thinkingParts.join("\n\n"),
  };
}

export function useAetherWebSocket(url: string = WS_URL): UseAetherWebSocketReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url);

      ws.onopen = () => {
        console.log("WebSocket connected");
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const rawMessage = JSON.parse(event.data);
          
          // Parse thinking blocks for models like Qwen3
          const { content, thinking } = parseThinkingBlocks(rawMessage.content || "");
          
          const message: Message = {
            ...rawMessage,
            content,
            thinking,
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

        // Attempt to reconnect after 3 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log("Attempting to reconnect...");
          connect();
        }, 3000);
      };

      wsRef.current = ws;
    } catch (err) {
      console.error("Failed to create WebSocket:", err);
      setError("Failed to connect");
    }
  }, [url]);

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

  const sendMessage = useCallback((content: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: content }));
    } else {
      console.error("WebSocket is not connected");
      setError("Not connected");
    }
  }, []);

  return {
    messages,
    sendMessage,
    isConnected,
    error,
  };
}
