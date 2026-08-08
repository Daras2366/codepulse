# CodePulse – Data Synchronization Strategy

## Overview

The core functionality of CodePulse depends on synchronizing competitive programming data from external platforms.

The synchronization process is responsible for importing, updating, and normalizing user data while preventing duplicates.

Version 1 supports:

- LeetCode
- Codeforces
- CodeChef
- AtCoder

---

# Synchronization Goals

Each synchronization should:

- Fetch latest profile data
- Import new submissions
- Import contests
- Update ratings
- Avoid duplicate records
- Preserve historical data

---

# Synchronization Flow

```
User

↓

Click Sync

↓

Platform Router

↓

Platform Service

↓

Platform Integration Client

↓

Fetch Platform Data

↓

Normalize Data

↓

Repositories

↓

PostgreSQL

↓

Dashboard Updated
```

---

# Synchronization Order

Data should always be saved in the following order.

```
1. Platform Profile

↓

2. Problems

↓

3. Topics

↓

4. Problem Topics

↓

5. Contests

↓

6. Contest Participations

↓

7. Submissions

↓

8. Rating History

↓

9. Goal Progress

↓

10. Achievement Evaluation
```

This order guarantees that all foreign key dependencies already exist.

---

# Duplicate Prevention

## Problems

Unique Key

```
(platform, platform_problem_id)
```

If a problem already exists

→ Update metadata if necessary.

Do not create a duplicate.

---

## Platform Profiles

Unique Key

```
(user_id, platform)
```

---

## Contest

Unique Key

```
(platform, platform_contest_id)
```

---

## Contest Participation

Unique Key

```
(profile_id, contest_id)
```

---

## User Achievement

Unique Key

```
(user_id, achievement_id)
```

---

## Submissions

Use

```
platform_submission_id
```

If available.

Otherwise compare

- profile
- problem
- verdict
- submission time

to prevent duplicate inserts.

---

# Synchronization Frequency

Version 1

Manual synchronization only.

User clicks

```
Sync
```

Future

Automatic scheduled synchronization every few hours.

---

# Error Handling

Possible failures

- Invalid username
- Platform unavailable
- API rate limit
- Network timeout
- Data parsing failure

The synchronization should fail gracefully.

Existing data must never be deleted because of a failed sync.

---

# Atomic Transactions

Every synchronization should execute inside a database transaction.

If any critical step fails

```
ROLLBACK
```

to prevent partial updates.

---

# Rating Synchronization

Each successful synchronization should

- update current rating
- update highest rating if necessary
- append a new rating history record if the rating changed

---

# Submission Synchronization

Only insert new submissions.

Existing submissions must not be modified.

Each submission is immutable after insertion.

---

# Contest Synchronization

For each contest

- create contest if missing
- create participation if missing
- update profile summary

---

# Problem Synchronization

When importing a submission

```
Problem exists?

YES

↓

Reuse existing problem

NO

↓

Create problem

↓

Create topic mappings
```

---

# Goal Progress Update

After synchronization

Automatically update

- solved problem goals
- contest goals
- rating goals
- streak goals

Completed goals should be marked automatically.

---

# Achievement Evaluation

After synchronization

Evaluate achievement conditions.

Examples

- 100 solved problems
- First contest
- 30-day streak
- 100 graph problems

Unlock only achievements not already earned.

---

# Future Improvements

Version 2 may introduce

- Background jobs
- Scheduled synchronization
- Webhook support
- Queue processing
- Retry mechanism
- Synchronization logs
- Incremental synchronization

---

# Design Principles

The synchronization process follows these principles:

- Never delete user data during synchronization
- Never create duplicate records
- Preserve historical information
- Normalize external platform data
- Keep synchronization idempotent
- Maintain referential integrity
- Complete dependent operations within a single transaction