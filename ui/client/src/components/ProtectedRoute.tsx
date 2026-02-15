/**
 * Protected Route Component
 * Redirects to login if user is not authenticated
 */

import React, { useEffect } from "react";
import { useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, loading } = useAuth();
  const [, setLocation] = useLocation();

  // Check if auth is disabled (for development/testing)
  const authDisabled = import.meta.env.VITE_DISABLE_AUTH === "true";

  useEffect(() => {
    // Skip auth check if disabled
    if (authDisabled) return;

    if (!loading && !isAuthenticated) {
      setLocation("/login");
    }
  }, [isAuthenticated, loading, setLocation, authDisabled]);

  // Skip loading screen if auth is disabled
  if (authDisabled) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-black/95">
        <div className="text-center space-y-4">
          <Loader2 className="w-16 h-16 mx-auto text-cyan-500 animate-spin" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null; // Will redirect via useEffect
  }

  return <>{children}</>;
}

export default ProtectedRoute;
