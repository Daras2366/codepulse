const API_BASE_URL = import.meta.env["VITE_API_BASE_URL"] ?? "http://127.0.0.1:8000";
const ACCESS_TOKEN_KEY = "codepulse.access_token";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Returns true when a JWT access token is present in localStorage.
 *
 * Server-side (SSR) the function intentionally returns `true` — the server has
 * no access to the browser's localStorage and therefore cannot determine auth
 * state.  Returning `false` on the server would cause every protected-route
 * `beforeLoad` guard to fire a redirect to `/auth` before the page reaches the
 * browser, even when the token is present.
 *
 * TanStack Router re-runs `beforeLoad` independently on the client after SSR
 * hydration, so unauthenticated users are still redirected correctly.
 */
export function hasAccessToken() {
  if (typeof window === "undefined") return true; // SSR: cannot read localStorage — let the client guard decide
  return Boolean(window.localStorage.getItem(ACCESS_TOKEN_KEY));
}

function getAccessToken() {
  return typeof window === "undefined" ? null : window.localStorage.getItem(ACCESS_TOKEN_KEY);
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  if (!token) {
    throw new ApiError("Sign in to view your dashboard.", 401);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError("Unable to reach CodePulse. Check your connection and try again.");
  }

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "Unable to load dashboard data.";
    throw new ApiError(detail, response.status);
  }

  return response.json() as Promise<T>;
}

export function getDashboardErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Sign in to view your dashboard.";
    if (error.status === 403) return "You do not have access to this profile.";
    if (error.status === 404) return "This profile could not be found.";
    if (error.status && error.status >= 500) return "CodePulse could not load this data right now.";
    return error.message;
  }

  return "CodePulse could not load this data right now.";
}
