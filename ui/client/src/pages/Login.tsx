/**
 * Login Page
 * Entry point for authentication
 */

import React from "react";
import { useLocation } from "wouter";
import { useAuth } from "@/contexts/AuthContext";
import { Shield, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

export function Login() {
  const { login } = useAuth();
  const [, setLocation] = useLocation();

  const handleGuestMode = () => {
    // Bypass auth and go to home
    setLocation("/");
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-black via-gray-900 to-black">
      <div className="w-full max-w-md p-8 space-y-8">
        {/* Logo and Title */}
        <div className="text-center">
          <div className="relative mx-auto w-24 h-24 mb-6">
            <div className="absolute inset-0 bg-cyan-500/20 blur-xl rounded-full animate-pulse" />
            <img
              src="/center_icon.png"
              alt="AetherOps"
              className="w-24 h-24 object-contain relative z-10 drop-shadow-[0_0_15px_rgba(6,182,212,0.8)]"
            />
          </div>
          <h1 className="text-3xl font-bold text-white mb-2">AetherOps</h1>
          <p className="text-gray-400">Sovereign Intelligence Architecture</p>
        </div>

        {/* Login Card */}
        <div className="bg-white/5 backdrop-blur-lg border border-white/10 rounded-2xl p-8 space-y-6">
          <div className="space-y-2 text-center">
            <h2 className="text-2xl font-semibold text-white">Sign In</h2>
            <p className="text-sm text-gray-400">
              Access your autonomous agent environment
            </p>
          </div>

          {/* Features */}
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm text-gray-300">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                <Shield className="w-4 h-4 text-cyan-500" />
              </div>
              <span>Secure SSO via Passport IAM</span>
            </div>
            <div className="flex items-center gap-3 text-sm text-gray-300">
              <div className="w-8 h-8 rounded-lg bg-orange-500/20 flex items-center justify-center">
                <Zap className="w-4 h-4 text-orange-500" />
              </div>
              <span>Full Agent Control & Monitoring</span>
            </div>
          </div>

          {/* Sign In Button */}
          <Button
            onClick={login}
            className="w-full bg-gradient-to-r from-cyan-600 to-cyan-500 hover:from-cyan-500 hover:to-cyan-400 text-white font-medium py-6 text-lg"
            size="lg"
          >
            Sign in with Passport
          </Button>

          {/* Guest Mode (Development) */}
          <Button
            onClick={handleGuestMode}
            variant="outline"
            className="w-full border-white/10 hover:bg-white/5"
          >
            Continue as Guest
          </Button>

          {/* Footer */}
          <p className="text-xs text-center text-gray-500">
            Protected by AetherPro Technologies<br />
            Powered by Keycloak SSO
          </p>
        </div>

        {/* Additional Info */}
        <div className="text-center text-sm text-gray-500">
          <p>Need access? Contact your administrator</p>
        </div>
      </div>
    </div>
  );
}

export default Login;
