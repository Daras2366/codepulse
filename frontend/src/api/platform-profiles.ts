import { apiRequest } from "@/api/client";
import type { Platform } from "@/api/dashboard";

export interface PlatformProfile {
  id: number;
  user_id: number;
  platform: Platform;
  username: string;
  current_rating: number | null;
  max_rating: number | null;
  rank: string | null;
  problems_solved: number;
  contests_attended: number;
  profile_url: string | null;
  is_connected: boolean;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlatformProfileCreate {
  platform: Platform;
  username: string;
}

export function getMyPlatformProfiles() {
  return apiRequest<PlatformProfile[]>("/platform-profiles/me");
}

export function createPlatformProfile(data: PlatformProfileCreate) {
  return apiRequest<PlatformProfile>("/platform-profiles", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deletePlatformProfile(profileId: number) {
  return apiRequest<void>(`/platform-profiles/${profileId}`, {
    method: "DELETE",
  });
}
