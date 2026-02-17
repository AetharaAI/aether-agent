/**
 * Aether API Client
 * 
 * Client library for interacting with the Aether backend API
 */


const API_BASE_URL = import.meta.env.VITE_API_URL || "http://triad.aetherpro.tech:16380";

export interface AgentStatus {
  running: boolean;
  mode: string;
  context_usage: number;
  uptime: number;
}

export interface ContextStats {
  usage_percent: number;
  daily_logs_count: number;
  longterm_memory_size: number;
  checkpoints_count: number;
  // Byte-level breakdown
  short_term_bytes: number;
  long_term_bytes: number;
  checkpoint_bytes: number;
  total_bytes: number;
}

export interface CheckpointResponse {
  id: string;
  name: string;
  timestamp: string;
}

class AetherAPI {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!response.ok) {
      throw new Error(`API request failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Status endpoints

  async getStatus(): Promise<AgentStatus> {
    return this.request<AgentStatus>("/api/status");
  }

  async getContextStats(): Promise<ContextStats> {
    return this.request<ContextStats>("/api/context/stats");
  }

  // Context management

  async compressContext(): Promise<{ status: string; message: string }> {
    return this.request("/api/context/compress", {
      method: "POST",
    });
  }

  // Checkpoint management

  async createCheckpoint(name?: string): Promise<CheckpointResponse> {
    return this.request<CheckpointResponse>("/api/checkpoint", {
      method: "POST",
      body: JSON.stringify({ name }),
    });
  }

  // Mode control

  async setMode(mode: "semi" | "auto"): Promise<{ status: string; mode: string }> {
    return this.request(`/api/mode/${mode}`, {
      method: "POST",
    });
  }

  // File upload

  async uploadFile(file: File): Promise<{
    status: string;
    filename: string;
    path: string;
    size: number;
    mimeType: string;
  }> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await fetch(`${this.baseUrl}/api/upload`, {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`File upload failed: ${response.statusText}`);
    }

    return response.json();
  }

  // Terminal

  async executeCommand(command: string): Promise<{
    command: string;
    output: string;
    exit_code: number;
    timestamp: string;
  }> {
    return this.request("/api/terminal/execute", {
      method: "POST",
      body: JSON.stringify({ command }),
    });
  }

  // Health check

  async healthCheck(): Promise<{
    status: string;
    agent_running: boolean;
    timestamp: string;
  }> {
    return this.request("/health");
  }

  // Chat Session Management

  async listChatSessions(limit: number = 50, offset: number = 0): Promise<{
    sessions: ChatSession[];
    total: number;
  }> {
    return this.request(`/api/chat/sessions?limit=${limit}&offset=${offset}`);
  }

  async createChatSession(title?: string): Promise<{
    id: string;
    title: string;
    created_at: string;
  }> {
    return this.request("/api/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  async getChatSession(sessionId: string): Promise<ChatSession & { messages: ChatMessage[] }> {
    return this.request(`/api/chat/sessions/${sessionId}`);
  }

  async getChatMessages(sessionId: string, limit: number = 100, offset: number = 0): Promise<{
    session_id: string;
    messages: ChatMessage[];
    total: number;
  }> {
    return this.request(`/api/chat/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`);
  }

  async deleteChatSession(sessionId: string): Promise<{ status: string; message: string }> {
    return this.request(`/api/chat/sessions/${sessionId}`, {
      method: "DELETE",
    });
  }

  async searchChatHistory(query: string, limit: number = 20): Promise<{
    query: string;
    results: Array<{ session_id: string; message: ChatMessage }>;
    total: number;
  }> {
    return this.request(`/api/chat/search?query=${encodeURIComponent(query)}&limit=${limit}`);
  }
}

// Types
export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_active: boolean;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  thinking?: string;
  timestamp: string;
  attachments?: Array<{
    id: string;
    filename: string;
    size: number;
  }>;
}

export const aetherAPI = new AetherAPI();
