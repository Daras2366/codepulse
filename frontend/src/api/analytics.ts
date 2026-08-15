/**
 * Analytics API
 *
 * All endpoints require authentication and ownership verification.
 * profile_id must belong to the current user.
 */
import { apiRequest } from "@/api/client";

export interface AnalyticsSummary {
  profile_id: number;
  platform: string;
  username: string;
  total_submissions: number;
  accepted_submissions: number;
  rejected_submissions: number;
  solved_problems: number;
  contests_attended: number;
  current_rating: number | null;
  max_rating: number | null;
  rank: string | null;
  acceptance_rate: number | null;
}

export interface AnalyticsActivityDay {
  date: string;
  total_submissions: number;
  accepted_submissions: number;
  rejected_submissions: number;
}

export interface AnalyticsSubmissionActivity {
  profile_id: number;
  activity: AnalyticsActivityDay[];
}

export interface AnalyticsDifficultyBucket {
  difficulty: string;
  solved_count: number;
}

export interface AnalyticsDifficultyDistribution {
  profile_id: number;
  solved_by_difficulty: AnalyticsDifficultyBucket[];
}

export interface AnalyticsRatingPoint {
  contest_id: number | null;
  contest_name: string | null;
  date: string;
  rating: number;
  rating_change: number;
}

export interface AnalyticsRatingProgression {
  profile_id: number;
  current_rating: number | null;
  max_rating: number | null;
  history: AnalyticsRatingPoint[];
}

export interface AnalyticsContestEntry {
  contest_id: number;
  contest_name: string;
  contest_url: string;
  date: string;
  rank: number | null;
  old_rating: number | null;
  new_rating: number | null;
  rating_change: number | null;
  solved: number;
  penalty: number | null;
}

export interface AnalyticsContestPerformance {
  profile_id: number;
  contests_attended: number;
  contests: AnalyticsContestEntry[];
}

export interface AggregateRatingPoint {
  date: string;
  rating: number;
  platform: string;
}

export interface AggregateRatingSeries {
  platform: string;
  username: string;
  history: AggregateRatingPoint[];
}

export interface AggregateRatingProgression {
  series: AggregateRatingSeries[];
}

export function getAnalyticsSummary(profileId: number) {
  return apiRequest<AnalyticsSummary>(`/analytics/${profileId}/summary`);
}

export function getAnalyticsSubmissionActivity(profileId: number) {
  return apiRequest<AnalyticsSubmissionActivity>(`/analytics/${profileId}/submission-activity`);
}

export function getAnalyticsDifficultyDistribution(profileId: number) {
  return apiRequest<AnalyticsDifficultyDistribution>(
    `/analytics/${profileId}/difficulty-distribution`,
  );
}

export function getAnalyticsRatingProgression(profileId: number) {
  return apiRequest<AnalyticsRatingProgression>(`/analytics/${profileId}/rating-progression`);
}

export function getAnalyticsContestPerformance(profileId: number) {
  return apiRequest<AnalyticsContestPerformance>(`/analytics/${profileId}/contest-performance`);
}

export function getAggregateRatingProgression() {
  return apiRequest<AggregateRatingProgression>(`/analytics/aggregate/rating-progression`);
}
