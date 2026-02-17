// API configuration
// In development, Vite proxy handles the forwarding
// In production (Docker), we use the build-time env vars

const isDevelopment = import.meta.env.DEV;

// Base URL for API calls
// In dev: use relative URL (Vite proxy handles it)
// In prod: use the build-time env var
export const API_BASE_URL = isDevelopment
  ? ''  // Relative URL - Vite proxy will handle it
  : (import.meta.env.VITE_API_URL || 'http://triad.aetherpro.tech:16380');

// WebSocket URL
// In dev: use relative URL with current host (Vite proxy handles it)
// In prod: use the build-time env var
export const WS_BASE_URL = isDevelopment
  ? `ws://${window.location.host}`  // Vite proxy handles WebSocket upgrade
  : (() => {
    const configured = import.meta.env.VITE_WS_URL;
    if (!configured) return "ws://triad.aetherpro.tech:16380";
    try {
      const parsed = new URL(configured);
      return `${parsed.protocol}//${parsed.host}`;
    } catch {
      return configured
        .replace(/\/ws\/chat\/?$/, "")
        .replace(/\/ws\/agent\/?.*$/, "");
    }
  })();

// Helper for API calls with auto-auth
export async function apiFetch(path: string, options?: RequestInit) {
  // Dynamically import to avoid circular deps
  const { default: AuthService } = await import("@/lib/auth");

  const url = `${API_BASE_URL}${path}`;

  // Add auth header if available
  const authHeaders = AuthService.getAuthHeader();

  const response = await fetch(url, {
    ...options,
    headers: {
      ...authHeaders,
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
