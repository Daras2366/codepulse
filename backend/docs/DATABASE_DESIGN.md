# CodePulse – Database Design

## Overview

CodePulse is designed as a multi-platform competitive programming analytics platform. The database stores normalized source-of-truth information from supported coding platforms while keeping derived analytics separate from persistent storage.

The primary goals of the database design are:

- Support multiple competitive programming platforms
- Maintain data consistency
- Minimize duplication
- Enable efficient analytics
- Allow easy expansion for future platforms
- Follow Third Normal Form (3NF)

The current version supports:

- LeetCode
- Codeforces
- CodeChef
- AtCoder

The schema is platform-independent, allowing additional platforms to be integrated without modifying the database structure.

---

# Design Principles

The database follows the following principles:

- PostgreSQL relational database
- Third Normal Form (3NF)
- Source-of-truth storage
- Platform-independent architecture
- Minimal data duplication
- Foreign key integrity
- Indexed frequently queried fields
- Analytics generated from raw data

---

# Entity Relationship Diagram

```
User
│
├── PlatformProfile
│       │
│       ├── Submission
│       │       │
│       │       └── Problem
│       │               │
│       │               └── ProblemTopic
│       │                        │
│       │                        └── Topic
│       │
│       ├── ContestParticipation
│       │          │
│       │          └── Contest
│       │
│       └── RatingHistory
│
├── Goal
│
└── UserAchievement
          │
          └── Achievement
```

---

# Database Tables

---

# 1. users

## Purpose

Stores user account information and authentication details.

Platform-specific information is intentionally excluded from this table.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | User ID |
| name | VARCHAR(100) | NOT NULL | User's full name |
| email | VARCHAR(255) | UNIQUE, NOT NULL | Login email |
| password_hash | VARCHAR(255) | NOT NULL | Encrypted password |
| avatar_url | VARCHAR(500) | NULL | Profile image URL |
| country | VARCHAR(100) | NULL | Country |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

---

### Relationships

```
User

1 ---- * PlatformProfile

1 ---- * Goal

1 ---- * UserAchievement
```

---

### Indexes

- PRIMARY KEY(id)
- UNIQUE(email)

---

# 2. platform_profiles

## Purpose

Represents a connected competitive programming account.

One user may connect multiple platforms.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Profile ID |
| user_id | Integer | FK(users.id) | Owner |
| platform | VARCHAR(30) | NOT NULL | Platform name |
| username | VARCHAR(100) | NOT NULL | Platform username |
| profile_url | VARCHAR(500) | NULL | Public profile URL |
| current_rating | Integer | NULL | Current rating |
| max_rating | Integer | NULL | Highest rating achieved |
| rank | Integer | NULL | Current global rank |
| problems_solved | Integer | NULL | Problems solved |
| contests_attended | Integer | NULL | Contests participated |
| last_synced_at | TIMESTAMP | NULL | Last successful synchronization |
| is_connected | BOOLEAN | DEFAULT TRUE | Connection status |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Last update timestamp |

---

### Unique Constraint

(user_id, platform)

---

### Indexes

- user_id
- platform
- username

---

# 3. problems

## Purpose

Stores metadata for every synchronized coding problem.

A problem exists only once regardless of how many users solve it.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Internal ID |
| platform | VARCHAR(30) | NOT NULL | Platform |
| platform_problem_id | VARCHAR(100) | NOT NULL | Platform problem identifier |
| title | VARCHAR(255) | NOT NULL | Problem title |
| slug | VARCHAR(255) | NULL | URL slug |
| difficulty | VARCHAR(20) | NOT NULL | Difficulty |
| url | VARCHAR(500) | NOT NULL | Problem URL |
| acceptance_rate | DECIMAL(5,2) | NULL | Acceptance percentage |
| is_active | BOOLEAN | DEFAULT TRUE | Problem availability |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |

---

### Unique Constraint

(platform, platform_problem_id)

---

### Indexes

- platform
- difficulty
- title

---

# 4. topics

## Purpose

Master list of algorithmic topics.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Topic ID |
| name | VARCHAR(100) | UNIQUE | Topic name |

---

# 5. problem_topics

## Purpose

Many-to-many relationship between problems and topics.

---

### Columns

| Column | Type | Constraints |
|---------|------|-------------|
| problem_id | Integer | FK(problems.id) |
| topic_id | Integer | FK(topics.id) |

---

### Composite Primary Key

(problem_id, topic_id)

---

# 6. submissions

## Purpose

Stores every submission made by every user.

One submission equals one database record.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Submission ID |
| profile_id | Integer | FK(platform_profiles.id) | Platform profile |
| problem_id | Integer | FK(problems.id) | Problem |
| platform_submission_id | VARCHAR(100) | NULL | Platform submission ID |
| verdict | VARCHAR(30) | NOT NULL | Submission verdict |
| language | VARCHAR(50) | NOT NULL | Programming language |
| submitted_at | TIMESTAMP | NOT NULL | Submission timestamp |
| contest_id | Integer | FK(contests.id), NULL | Contest (if applicable) |
| created_at | TIMESTAMP | NOT NULL | Synchronization timestamp |

---

### Indexes

- profile_id
- problem_id
- submitted_at
- verdict
- contest_id

---

# 7. contests

## Purpose

Stores contest metadata.

Only contests that at least one CodePulse user has participated in are stored.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Contest ID |
| platform | VARCHAR(30) | NOT NULL | Platform |
| platform_contest_id | VARCHAR(100) | NOT NULL | Platform contest ID |
| title | VARCHAR(255) | NOT NULL | Contest title |
| url | VARCHAR(500) | NULL | Contest URL |
| start_time | TIMESTAMP | NOT NULL | Contest start |
| duration_minutes | Integer | NOT NULL | Contest duration |
| created_at | TIMESTAMP | NOT NULL | Synchronization timestamp |

---

### Unique Constraint

(platform, platform_contest_id)

---

### Indexes

- platform
- start_time

---

# 8. contest_participations

## Purpose

Represents one user's participation in one contest.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Participation ID |
| profile_id | Integer | FK(platform_profiles.id) | Platform profile |
| contest_id | Integer | FK(contests.id) | Contest |
| rank | Integer | NULL | Contest rank |
| score | DECIMAL(8,2) | NULL | Contest score |
| solved_count | Integer | NULL | Problems solved |
| penalty | Integer | NULL | Contest penalty |
| rating_before | Integer | NULL | Rating before contest |
| rating_after | Integer | NULL | Rating after contest |
| rating_change | Integer | NULL | Rating difference |
| participated_at | TIMESTAMP | NOT NULL | Participation timestamp |
| created_at | TIMESTAMP | NOT NULL | Synchronization timestamp |

---

### Unique Constraint

(profile_id, contest_id)

---

### Indexes

- profile_id
- contest_id
- participated_at

---

# 9. rating_history

## Purpose

Stores historical rating snapshots for visualization and analytics.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Rating record |
| profile_id | Integer | FK(platform_profiles.id) | Platform profile |
| rating | Integer | NOT NULL | Rating |
| recorded_at | TIMESTAMP | NOT NULL | Snapshot timestamp |
| source | VARCHAR(30) | NOT NULL | contest / sync |

---

### Indexes

- profile_id
- recorded_at

---

# 10. goals

## Purpose

Stores user-created goals.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Goal ID |
| user_id | Integer | FK(users.id) | Owner |
| title | VARCHAR(255) | NOT NULL | Goal title |
| description | TEXT | NULL | Goal description |
| goal_type | VARCHAR(50) | NOT NULL | Goal category |
| target_value | Integer | NOT NULL | Target |
| current_value | Integer | DEFAULT 0 | Progress |
| status | VARCHAR(20) | DEFAULT 'active' | Goal status |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP | NOT NULL | Update timestamp |

---

### Indexes

- user_id
- status

---

# 11. achievements

## Purpose

Master table containing all achievements available in CodePulse.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Achievement ID |
| name | VARCHAR(100) | UNIQUE | Achievement name |
| description | TEXT | NOT NULL | Achievement description |
| icon | VARCHAR(255) | NULL | Icon identifier |
| category | VARCHAR(50) | NULL | Category |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |

---

# 12. user_achievements

## Purpose

Tracks achievements unlocked by users.

---

### Columns

| Column | Type | Constraints | Description |
|---------|------|-------------|-------------|
| id | Integer | Primary Key | Record ID |
| user_id | Integer | FK(users.id) | User |
| achievement_id | Integer | FK(achievements.id) | Achievement |
| earned_at | TIMESTAMP | NOT NULL | Unlock timestamp |

---

### Unique Constraint

(user_id, achievement_id)

---

# Database Naming Conventions

## Tables

Plural nouns

Examples

- users
- submissions
- contests

---

## Primary Keys

```
id
```

---

## Foreign Keys

```
user_id

profile_id

problem_id

contest_id
```

---

## Timestamps

```
created_at

updated_at

submitted_at

participated_at

recorded_at
```

---

# Index Strategy

Indexes are created on:

- email
- platform
- username
- difficulty
- title
- submitted_at
- contest_id
- recorded_at
- status

to optimize filtering, searching, sorting, and dashboard analytics.

---

# Source of Truth

The database stores only raw platform data.

Examples of stored data:

- Users
- Platform profiles
- Problems
- Submissions
- Contests
- Ratings
- Goals
- Achievements

The following are **not stored** and are computed dynamically:

- Current streak
- Longest streak
- Difficulty distribution
- Topic mastery
- Submission heatmap
- Platform comparison
- Dashboard statistics
- AI recommendations

---

# Future Expansion

The following tables may be introduced in future releases without modifying the existing schema:

- notification_preferences
- ai_insights
- leaderboard_snapshots
- friends
- friend_requests
- practice_sessions
- study_plans
- ai_conversations

The current schema has been designed to support these additions while maintaining backward compatibility.