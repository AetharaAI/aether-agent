/**
 * OAuth Callback Page
 * Handles the redirect from Keycloak/Passport after authentication
 */

import React, { useEffect, useState } from "react";
import { useLocation } from "wouter";
import AuthService from "@/lib/auth";
import { Loader2 } from "lucide-react";

export function AuthCallback() {
  const [, setLocation] = useLocation();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    handleCallback();
  }, []);

  const handleCallback = async () => {
    try {
      // Parse URL parameters
      const params = new URLSearchParams(window.location.search);
      const code = params.get("code");
      const state = params.get("state");
      const oauthError = params.get("error");
      const errorDescription = params.get("error_description");

      // Check for OAuth errors
      if (oauthError) {
        setError(errorDescription || oauthError);
        setTimeout(() => setLocation("/"), 3000);
        return;
      }

      // Validate required parameters
      if (!code || !state) {
        setError("Missing authorization code or state");
        setTimeout(() => setLocation("/"), 3000);
        return;
      }

      // Exchange code for tokens
      const success = await AuthService.handleCallback(code, state);

      if (success) {
        // Redirect to home page
        setLocation("/");
      } else {
        setError("Authentication failed");
        setTimeout(() => setLocation("/"), 3000);
      }
    } catch (err: any) {
      console.error("Callback error:", err);
      setError(err.message || "An unexpected error occurred");
      setTimeout(() => setLocation("/"), 3000);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-black/95">
      <div className="text-center">
        {error ? (
          <div className="space-y-4">
            <div className="w-16 h-16 mx-auto rounded-full bg-red-500/20 flex items-center justify-center">
              <svg
                className="w-8 h-8 text-red-500"
                fill="none"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-white">Authentication Failed</h2>
            <p className="text-gray-400">{error}</p>
            <p className="text-sm text-gray-500">Redirecting to login...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <Loader2 className="w-16 h-16 mx-auto text-cyan-500 animate-spin" />
            <h2 className="text-xl font-semibold text-white">Completing Sign In...</h2>
            <p className="text-gray-400">Please wait while we authenticate you</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AuthCallback;
