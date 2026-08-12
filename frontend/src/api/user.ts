/**
 * Users API
 *
 * GET /users/me — returns the current authenticated user's profile.
 * The password_hash is never included in the response.
 */
import { apiRequest } from "@/api/client";

export interface CurrentUser {
  id: number;
  username: string;
  full_name: string | null;
  email: string;
  created_at: string;
}

export function getCurrentUser() {
  return apiRequest<CurrentUser>("/users/me");
}
