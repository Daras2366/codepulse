/**
 * Authentication API
 *
 * POST /auth/register — create a new user account
 * POST /auth/login — authenticate and receive JWT
 */

const API_BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://127.0.0.1:8000";
const ACCESS_TOKEN_KEY = "codepulse.access_token";

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  full_name?: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  full_name: string | null;
  created_at: string;
}

export class AuthError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

/**
 * Store the JWT access token in localStorage
 */
export function setAccessToken(token: string): void {
  if (typeof window === "undefined") return;
  
  window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
  
  // Dispatch custom event to notify other components
  window.dispatchEvent(new Event("codepulse-auth-change"));
}

/**
 * Remove the JWT access token from localStorage
 */
export function clearAccessToken(): void {
  if (typeof window === "undefined") return;
  
  window.localStorage.removeItem(ACCESS_TOKEN_KEY);
  
  // Dispatch custom event to notify other components
  window.dispatchEvent(new Event("codepulse-auth-change"));
}

/**
 * Register a new user account
 */
export async function register(data: RegisterRequest): Promise<UserResponse> {
  let response: Response;
  
  try {
    response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new AuthError("Unable to reach CodePulse. Check your connection and try again.");
  }

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Registration failed. Please try again.";
    throw new AuthError(detail, response.status);
  }

  return response.json() as Promise<UserResponse>;
}

/**
 * Authenticate user and receive JWT token
 */
export async function login(data: LoginRequest): Promise<TokenResponse> {
  let response: Response;
  
  try {
    response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(data),
    });
  } catch {
    throw new AuthError("Unable to reach CodePulse. Check your connection and try again.");
  }

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Login failed. Please check your credentials.";
    throw new AuthError(detail, response.status);
  }

  const tokenData = (await response.json()) as TokenResponse;
  
  // Automatically store the token
  setAccessToken(tokenData.access_token);
  
  return tokenData;
}

/**
 * Log out by clearing the stored token
 */
export function logout(): void {
  clearAccessToken();
}
