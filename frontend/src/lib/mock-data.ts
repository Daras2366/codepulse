export type PlatformKey = "leetcode" | "codeforces" | "codechef" | "atcoder";

export const platforms: {
  key: PlatformKey;
  name: string;
  short: string;
  rating: number;
  peak: number;
  solved: number;
  rank: string;
  tint: string;
  stroke: string;
  spark: number[];
}[] = [
  {
    key: "leetcode",
    name: "LeetCode",
    short: "LC",
    rating: 2148,
    peak: 2210,
    solved: 1042,
    rank: "#3,182",
    tint: "bg-yellow-soft",
    stroke: "var(--pastel-yellow)",
    spark: [1890, 1932, 1975, 1948, 2012, 2064, 2098, 2081, 2124, 2148],
  },
  {
    key: "codeforces",
    name: "Codeforces",
    short: "CF",
    rating: 1836,
    peak: 1901,
    solved: 612,
    rank: "#11,540",
    tint: "bg-blue-soft",
    stroke: "var(--pastel-blue)",
    spark: [1502, 1588, 1621, 1594, 1670, 1712, 1690, 1774, 1802, 1836],
  },
  {
    key: "codechef",
    name: "CodeChef",
    short: "CC",
    rating: 2015,
    peak: 2043,
    solved: 388,
    rank: "#1,928",
    tint: "bg-pink-soft",
    stroke: "var(--pastel-pink)",
    spark: [1740, 1782, 1830, 1812, 1875, 1902, 1948, 1966, 1990, 2015],
  },
  {
    key: "atcoder",
    name: "AtCoder",
    short: "AC",
    rating: 1462,
    peak: 1520,
    solved: 241,
    rank: "#8,004",
    tint: "bg-violet-soft",
    stroke: "var(--pastel-violet)",
    spark: [1180, 1215, 1268, 1240, 1302, 1348, 1372, 1401, 1438, 1462],
  },
];

export const ratingSeries = [
  { month: "Sep", leetcode: 1890, codeforces: 1502, codechef: 1740, atcoder: 1180 },
  { month: "Oct", leetcode: 1932, codeforces: 1588, codechef: 1782, atcoder: 1215 },
  { month: "Nov", leetcode: 1975, codeforces: 1621, codechef: 1830, atcoder: 1268 },
  { month: "Dec", leetcode: 1948, codeforces: 1594, codechef: 1812, atcoder: 1240 },
  { month: "Jan", leetcode: 2012, codeforces: 1670, codechef: 1875, atcoder: 1302 },
  { month: "Feb", leetcode: 2064, codeforces: 1712, codechef: 1902, atcoder: 1348 },
  { month: "Mar", leetcode: 2098, codeforces: 1690, codechef: 1948, atcoder: 1372 },
  { month: "Apr", leetcode: 2081, codeforces: 1774, codechef: 1966, atcoder: 1401 },
  { month: "May", leetcode: 2124, codeforces: 1802, codechef: 1990, atcoder: 1438 },
  { month: "Jun", leetcode: 2148, codeforces: 1836, codechef: 2015, atcoder: 1462 },
];

export const topics = [
  { name: "Arrays", value: 268, color: "var(--pastel-blue)" },
  { name: "Graphs", value: 154, color: "var(--pastel-violet)" },
  { name: "Trees", value: 132, color: "var(--pastel-green)" },
  { name: "DP", value: 121, color: "var(--pastel-pink)" },
  { name: "Greedy", value: 98, color: "var(--pastel-yellow)" },
  { name: "Strings", value: 86, color: "var(--success)" },
  { name: "Math", value: 74, color: "var(--warning)" },
];

export type ActivityKind = "solved" | "contest" | "milestone" | "topic";

export const activity: {
  kind: ActivityKind;
  title: string;
  meta: string;
  time: string;
}[] = [
  { kind: "solved", title: "Median of Two Sorted Arrays", meta: "LeetCode · Hard", time: "2h ago" },
  {
    kind: "contest",
    title: "Codeforces Round 987 (Div. 2)",
    meta: "Rank 842 · +34 rating",
    time: "Yesterday",
  },
  {
    kind: "milestone",
    title: "1,000 problems solved",
    meta: "Lifetime milestone",
    time: "2 days ago",
  },
  { kind: "topic", title: "Segment Trees completed", meta: "18 / 18 problems", time: "3 days ago" },
  {
    kind: "solved",
    title: "Minimum Window Substring",
    meta: "LeetCode · Hard",
    time: "4 days ago",
  },
  {
    kind: "contest",
    title: "CodeChef Starters 168",
    meta: "Rank 211 · +27 rating",
    time: "5 days ago",
  },
];

export const contests = [
  {
    name: "Codeforces Round 987 (Div. 2)",
    platform: "Codeforces",
    date: "Jun 21, 2026",
    rank: 842,
    delta: 34,
    status: "Rated",
  },
  {
    name: "LeetCode Weekly 452",
    platform: "LeetCode",
    date: "Jun 15, 2026",
    rank: 318,
    delta: 24,
    status: "Rated",
  },
  {
    name: "CodeChef Starters 168",
    platform: "CodeChef",
    date: "Jun 11, 2026",
    rank: 211,
    delta: 27,
    status: "Rated",
  },
  {
    name: "AtCoder Beginner 402",
    platform: "AtCoder",
    date: "Jun 8, 2026",
    rank: 1104,
    delta: -12,
    status: "Rated",
  },
  {
    name: "LeetCode Biweekly 138",
    platform: "LeetCode",
    date: "Jun 1, 2026",
    rank: 96,
    delta: 41,
    status: "Rated",
  },
  {
    name: "Codeforces Educational 178",
    platform: "Codeforces",
    date: "May 27, 2026",
    rank: 2380,
    delta: 0,
    status: "Unrated",
  },
];

export const leaderboard = [
  {
    name: "Aarav Mehta",
    handle: "@aarav",
    rating: 2871,
    growth: 62,
    country: "India",
    tint: "bg-pink-soft",
  },
  {
    name: "Sofia Almeida",
    handle: "@sofia_a",
    rating: 2764,
    growth: 48,
    country: "Brazil",
    tint: "bg-blue-soft",
  },
  {
    name: "Kenji Watanabe",
    handle: "@kenjiw",
    rating: 2698,
    growth: 31,
    country: "Japan",
    tint: "bg-violet-soft",
  },
  {
    name: "Nora Lindqvist",
    handle: "@noral",
    rating: 2610,
    growth: -14,
    country: "Sweden",
    tint: "bg-green-soft",
  },
  {
    name: "Demo User",
    handle: "@demo_user",
    rating: 2148,
    growth: 34,
    country: "India",
    tint: "bg-yellow-soft",
  },
];

export const goals = [
  {
    title: "Solve 1,200 problems",
    current: 1042,
    target: 1200,
    tint: "bg-blue-soft",
    bar: "var(--pastel-blue)",
    note: "158 to go · on pace",
  },
  {
    title: "Reach 1900 on Codeforces",
    current: 1836,
    target: 1900,
    tint: "bg-violet-soft",
    bar: "var(--pastel-violet)",
    note: "64 rating away",
  },
  {
    title: "60-day streak",
    current: 47,
    target: 60,
    tint: "bg-green-soft",
    bar: "var(--pastel-green)",
    note: "13 days remaining",
  },
  {
    title: "Finish DP roadmap",
    current: 121,
    target: 160,
    tint: "bg-pink-soft",
    bar: "var(--pastel-pink)",
    note: "39 problems left",
  },
  {
    title: "Interview readiness 90%",
    current: 78,
    target: 90,
    tint: "bg-yellow-soft",
    bar: "var(--pastel-yellow)",
    note: "Mock rounds pending",
  },
];

export const achievements = [
  {
    title: "Century Club",
    desc: "100 problems in a single month",
    tint: "bg-yellow-soft",
    unlocked: true,
  },
  {
    title: "Graph Whisperer",
    desc: "150 graph problems solved",
    tint: "bg-violet-soft",
    unlocked: true,
  },
  {
    title: "Ice Cold",
    desc: "Solved a Hard in under 12 minutes",
    tint: "bg-blue-soft",
    unlocked: true,
  },
  { title: "Marathoner", desc: "45-day unbroken streak", tint: "bg-green-soft", unlocked: true },
  { title: "Div 1 Debut", desc: "Cross 1900 on Codeforces", tint: "bg-pink-soft", unlocked: false },
  {
    title: "Perfect Contest",
    desc: "Full score in a rated contest",
    tint: "bg-yellow-soft",
    unlocked: false,
  },
];

export const recommended = [
  {
    title: "Sliding Window Maximum",
    platform: "LeetCode",
    difficulty: "Hard",
    topic: "Deque",
    why: "Shores up your weakest pattern",
  },
  {
    title: "Dijkstra on Grid",
    platform: "Codeforces",
    difficulty: "Div2 D",
    topic: "Graphs",
    why: "Appears in 62% of your contests",
  },
  {
    title: "Digit DP Basics",
    platform: "AtCoder",
    difficulty: "ABC E",
    topic: "DP",
    why: "Unlocks the DP roadmap tail",
  },
  {
    title: "Tree Rerooting",
    platform: "CodeChef",
    difficulty: "Div2 C",
    topic: "Trees",
    why: "Next step after segment trees",
  },
];

export const strengths = [
  { label: "Array & two-pointer patterns", score: 92 },
  { label: "Binary search on answer", score: 88 },
  { label: "Tree traversal & LCA", score: 84 },
];

export const weaknesses = [
  { label: "Digit / bitmask DP", score: 41 },
  { label: "Flow & matching", score: 36 },
  { label: "Geometry", score: 29 },
];

export function buildHeatmap() {
  const weeks: { level: number; count: number; label: string }[][] = [];
  let seed = 42;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  const today = new Date(Date.UTC(2026, 7, 4));
  const start = new Date(today);
  start.setUTCDate(start.getUTCDate() - 52 * 7 - today.getUTCDay());

  for (let w = 0; w < 53; w++) {
    const week: { level: number; count: number; label: string }[] = [];
    for (let d = 0; d < 7; d++) {
      const date = new Date(start);
      date.setUTCDate(start.getUTCDate() + w * 7 + d);
      const r = rand();
      const weekendDip = d === 0 || d === 6 ? 0.35 : 0;
      const count = date > today ? 0 : Math.max(0, Math.round((r - weekendDip) * 11));
      const level = count === 0 ? 0 : count < 3 ? 1 : count < 6 ? 2 : count < 9 ? 3 : 4;
      week.push({
        level,
        count,
        label: date.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          timeZone: "UTC",
        }),
      });
    }
    weeks.push(week);
  }
  return weeks;
}

export const platformAccounts: Record<
  PlatformKey,
  { username: string; lastSync: string; status: "connected" }
> = {
  leetcode: { username: "demo_user", lastSync: "2 hours ago", status: "connected" },
  codeforces: { username: "demo_user", lastSync: "35 minutes ago", status: "connected" },
  codechef: { username: "demo_user", lastSync: "5 hours ago", status: "connected" },
  atcoder: { username: "demo_user", lastSync: "yesterday", status: "connected" },
};

export const comingSoonPlatforms = [
  {
    name: "GitHub",
    short: "GH",
    tint: "bg-violet-soft",
    note: "Commits, streaks and repo activity",
  },
  {
    name: "GeeksforGeeks",
    short: "GG",
    tint: "bg-green-soft",
    note: "Practice tracks and POTD streaks",
  },
  {
    name: "HackerRank",
    short: "HR",
    tint: "bg-blue-soft",
    note: "Skill certificates and contests",
  },
  {
    name: "HackerEarth",
    short: "HE",
    tint: "bg-yellow-soft",
    note: "Hiring challenges and ratings",
  },
  { name: "SPOJ", short: "SP", tint: "bg-pink-soft", note: "Classical problem archive" },
];

export const studyPlan = {
  topic: "Digit & bitmask DP",
  durationMinutes: 75,
  dailyTarget: 5,
  dailyDone: 3,
  upcomingContest: {
    name: "Codeforces Round 988 (Div. 2)",
    startsIn: "1d 4h",
    date: "Aug 5, 2026 · 20:05 IST",
  },
  problems: [
    {
      title: "Count Numbers with Unique Digits",
      platform: "LeetCode",
      difficulty: "Medium",
      minutes: 20,
    },
    { title: "Bitmask Assignment", platform: "Codeforces", difficulty: "Div2 D", minutes: 30 },
    { title: "Digit Sum Ranges", platform: "AtCoder", difficulty: "ABC E", minutes: 25 },
  ],
};
