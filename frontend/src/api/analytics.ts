/**
 * Analytics API
 *
 * All endpoints require authentication and ownership verification.
 * profile_id must belong to the current user.
 */
import { apiRequest } from "@/api/client";
import type { Platform } from "@/api/dashboard";

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

export interface AggregateTopicPoint {
  topic: string;
  solved_count: number;
  percentage: number;
}

export interface PlatformSolvedCoverage {
  /** Lowercase platform name, e.g. "codeforces" or "leetcode". */
  platform: string;
  total_solved: number;
  /** Problems with ≥1 canonical DSA topic (may be 0 if platform has no topic data). */
  tagged_solved: number;
}

export interface AggregateTopicBreakdown {
  total_solved: number;
  tagged_solved: number;
  /** Sum of all topic-assignment counts. Use as donut denominator. */
  total_topic_assignments: number;
  topics: AggregateTopicPoint[];
  /**
   * Per-platform coverage.  Present when the backend has enough context to
   * break down coverage by platform.  The frontend uses this to clearly
   * communicate which platforms currently have topic data and which do not.
   */
  platform_coverage?: PlatformSolvedCoverage[];
}

export interface AggregateDifficultyPoint {
  difficulty: string;
  solved_count: number;
  percentage: number;
}

export interface AggregatePlatformDifficulty {
  platform: string;
  easy: number;
  medium: number;
  hard: number;
}

export interface AggregateDifficultyDistribution {
  total_solved: number;
  difficulties: AggregateDifficultyPoint[];
  platform_totals: AggregatePlatformDifficulty[];
}

export interface AggregateActivityDay {
  date: string;
  total_submissions: number;
  accepted_submissions: number;
}

export interface AggregateSubmissionActivity {
  total_submissions: number;
  activity: AggregateActivityDay[];
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

export function getAggregateRatingProgression(platforms?: string[]) {
  const params = new URLSearchParams();
  if (platforms && platforms.length > 0) params.append("platforms", platforms.join(","));
  const queryString = params.toString();
  return apiRequest<AggregateRatingProgression>(
    `/analytics/aggregate/rating-progression${queryString ? `?${queryString}` : ""}`,
  );
}

export function getAggregateTopicBreakdown(platforms?: string[]) {
  const params = new URLSearchParams();
  if (platforms && platforms.length > 0) params.append("platforms", platforms.join(","));
  const queryString = params.toString();
  return apiRequest<AggregateTopicBreakdown>(
    `/analytics/aggregate/topic-breakdown${queryString ? `?${queryString}` : ""}`,
  );
}

export function getAggregateDifficultyDistribution(platforms?: string[]) {
  const params = new URLSearchParams();
  if (platforms && platforms.length > 0) params.append("platforms", platforms.join(","));
  const queryString = params.toString();
  return apiRequest<AggregateDifficultyDistribution>(
    `/analytics/aggregate/difficulty-distribution${queryString ? `?${queryString}` : ""}`,
  );
}

export function getAggregateSubmissionActivity(platforms?: string[], rangeDays?: number) {
  const params = new URLSearchParams();
  if (platforms && platforms.length > 0) params.append("platforms", platforms.join(","));
  if (rangeDays) params.append("range_days", rangeDays.toString());
  const queryString = params.toString();
  return apiRequest<AggregateSubmissionActivity>(
    `/analytics/aggregate/submission-activity${queryString ? `?${queryString}` : ""}`,
  );
}
