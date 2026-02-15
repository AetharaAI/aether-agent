/**
 * Authentication Context Provider
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import AuthService from "@/lib/auth";

interface UserInfo {
  sub: string;
  name?: string;
  email?: string;
  preferred_username?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
}

interface AuthContextType {
  isAuthenticated: boolean;
  user: UserInfo | null;
  loading: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
  refreshAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check authentication status on mount
    checkAuth();

    // Set up auto-refresh interval (refresh 1 minute before expiry)
    const interval = setInterval(async () => {
      if (AuthService.isAuthenticated()) {
        await AuthService.refreshToken();
        checkAuth();
      }
    }, 5 * 60 * 1000); // Check every 5 minutes

    return () => clearInterval(interval);
  }, []);

  const checkAuth = () => {
    const authenticated = AuthService.isAuthenticated();
    const userInfo = AuthService.getUserInfo();

    setIsAuthenticated(authenticated);
    setUser(userInfo);
    setLoading(false);
  };

  const login = async () => {
    await AuthService.login();
  };

  const logout = async () => {
    await AuthService.logout();
  };

  const refreshAuth = async () => {
    checkAuth();
  };

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        user,
        loading,
        login,
        logout,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
