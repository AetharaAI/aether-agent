/**
 * OAuth/OIDC Authentication with Passport (Keycloak)
 */

const ISSUER_URL = import.meta.env.VITE_PASSPORT_ISSUER_URL || "";
const CLIENT_ID = import.meta.env.VITE_PASSPORT_CLIENT_ID || "";
const REDIRECT_URI = import.meta.env.VITE_PASSPORT_REDIRECT_URI?.split(',')[0] || window.location.origin + "/auth/callback";
const POST_LOGOUT_REDIRECT_URI = import.meta.env.VITE_PASSPORT_POST_LOGOUT_REDIRECT_URI?.split(',')[0] || window.location.origin + "/logout";
const SCOPES = import.meta.env.VITE_PASSPORT_SCOPES || "openid profile email";

interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string;
  id_token?: string;
  scope: string;
}

interface UserInfo {
  sub: string;
  name?: string;
  email?: string;
  preferred_username?: string;
  given_name?: string;
  family_name?: string;
  picture?: string;
}

export class AuthService {
  private static readonly TOKEN_KEY = "aether_access_token";
  private static readonly REFRESH_TOKEN_KEY = "aether_refresh_token";
  private static readonly ID_TOKEN_KEY = "aether_id_token";
  private static readonly USER_INFO_KEY = "aether_user_info";
  private static readonly CODE_VERIFIER_KEY = "aether_code_verifier";

  /**
   * Generate PKCE code verifier and challenge
   */
  private static async generatePKCE(): Promise<{ verifier: string; challenge: string }> {
    const verifier = this.generateRandomString(128);
    const challengeBuffer = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(verifier)
    );
    const challenge = btoa(String.fromCharCode(...new Uint8Array(challengeBuffer)))
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

    return { verifier, challenge };
  }

  private static generateRandomString(length: number): string {
    const charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~";
    const randomValues = new Uint8Array(length);
    crypto.getRandomValues(randomValues);
    return Array.from(randomValues)
      .map((v) => charset[v % charset.length])
      .join("");
  }

  /**
   * Initiate OAuth login flow
   */
  static async login(): Promise<void> {
    const { verifier, challenge } = await this.generatePKCE();

    // Store code verifier for later use in callback
    sessionStorage.setItem(this.CODE_VERIFIER_KEY, verifier);

    // Generate state for CSRF protection
    const state = this.generateRandomString(32);
    sessionStorage.setItem("aether_oauth_state", state);

    // Build authorization URL
    const params = new URLSearchParams({
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      response_type: "code",
      scope: SCOPES,
      state,
      code_challenge: challenge,
      code_challenge_method: "S256",
    });

    const authUrl = `${ISSUER_URL}/protocol/openid-connect/auth?${params.toString()}`;

    // Redirect to authorization endpoint
    window.location.href = authUrl;
  }

  /**
   * Handle OAuth callback
   */
  static async handleCallback(code: string, state: string): Promise<boolean> {
    try {
      // Verify state
      const savedState = sessionStorage.getItem("aether_oauth_state");
      if (state !== savedState) {
        console.error("OAuth state mismatch - possible CSRF attack");
        return false;
      }

      // Retrieve code verifier
      const codeVerifier = sessionStorage.getItem(this.CODE_VERIFIER_KEY);
      if (!codeVerifier) {
        console.error("Code verifier not found");
        return false;
      }

      // Exchange code for tokens
      const tokenResponse = await fetch(`${ISSUER_URL}/protocol/openid-connect/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          grant_type: "authorization_code",
          client_id: CLIENT_ID,
          code,
          redirect_uri: REDIRECT_URI,
          code_verifier: codeVerifier,
        }),
      });

      if (!tokenResponse.ok) {
        console.error("Token exchange failed:", await tokenResponse.text());
        return false;
      }

      const tokens: TokenResponse = await tokenResponse.json();

      // Store tokens
      localStorage.setItem(this.TOKEN_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(this.REFRESH_TOKEN_KEY, tokens.refresh_token);
      }
      if (tokens.id_token) {
        localStorage.setItem(this.ID_TOKEN_KEY, tokens.id_token);
      }

      // Fetch user info
      await this.fetchUserInfo(tokens.access_token);

      // Clean up session storage
      sessionStorage.removeItem(this.CODE_VERIFIER_KEY);
      sessionStorage.removeItem("aether_oauth_state");

      return true;
    } catch (error) {
      console.error("OAuth callback error:", error);
      return false;
    }
  }

  /**
   * Fetch user information from userinfo endpoint
   */
  private static async fetchUserInfo(accessToken: string): Promise<void> {
    try {
      const response = await fetch(`${ISSUER_URL}/protocol/openid-connect/userinfo`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (response.ok) {
        const userInfo: UserInfo = await response.json();
        localStorage.setItem(this.USER_INFO_KEY, JSON.stringify(userInfo));
      }
    } catch (error) {
      console.error("Failed to fetch user info:", error);
    }
  }

  /**
   * Logout user
   */
  static async logout(): Promise<void> {
    const idToken = localStorage.getItem(this.ID_TOKEN_KEY);

    // Clear all stored data
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.REFRESH_TOKEN_KEY);
    localStorage.removeItem(this.ID_TOKEN_KEY);
    localStorage.removeItem(this.USER_INFO_KEY);

    // Redirect to Keycloak logout endpoint
    if (idToken) {
      const params = new URLSearchParams({
        id_token_hint: idToken,
        post_logout_redirect_uri: POST_LOGOUT_REDIRECT_URI,
      });
      window.location.href = `${ISSUER_URL}/protocol/openid-connect/logout?${params.toString()}`;
    } else {
      window.location.href = POST_LOGOUT_REDIRECT_URI;
    }
  }

  /**
   * Check if user is authenticated
   */
  static isAuthenticated(): boolean {
    const token = localStorage.getItem(this.TOKEN_KEY);
    if (!token) return false;

    // Check if token is expired (basic check - decode JWT)
    try {
      const payload = JSON.parse(atob(token.split(".")[1]));
      const exp = payload.exp * 1000; // Convert to milliseconds
      return Date.now() < exp;
    } catch {
      return false;
    }
  }

  /**
   * Get access token
   */
  static getAccessToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  /**
   * Get user info
   */
  static getUserInfo(): UserInfo | null {
    const userInfoStr = localStorage.getItem(this.USER_INFO_KEY);
    if (!userInfoStr) return null;
    try {
      return JSON.parse(userInfoStr);
    } catch {
      return null;
    }
  }

  /**
   * Refresh access token
   */
  static async refreshToken(): Promise<boolean> {
    const refreshToken = localStorage.getItem(this.REFRESH_TOKEN_KEY);
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${ISSUER_URL}/protocol/openid-connect/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams({
          grant_type: "refresh_token",
          client_id: CLIENT_ID,
          refresh_token: refreshToken,
        }),
      });

      if (!response.ok) return false;

      const tokens: TokenResponse = await response.json();

      // Update stored tokens
      localStorage.setItem(this.TOKEN_KEY, tokens.access_token);
      if (tokens.refresh_token) {
        localStorage.setItem(this.REFRESH_TOKEN_KEY, tokens.refresh_token);
      }
      if (tokens.id_token) {
        localStorage.setItem(this.ID_TOKEN_KEY, tokens.id_token);
      }

      return true;
    } catch (error) {
      console.error("Token refresh failed:", error);
      return false;
    }
  }

  /**
   * Get authorization header
   */
  static getAuthHeader(): Record<string, string> {
    const token = this.getAccessToken();
    if (!token) return {};
    return {
      Authorization: `Bearer ${token}`,
    };
  }
}

export default AuthService;
