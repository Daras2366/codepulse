# CodePulse – API Specification

## Overview

The CodePulse backend exposes a RESTful API built using FastAPI.

All authenticated endpoints require a valid JWT access token.

Base URL

```
/api/v1
```

---

# Authentication

## Register

POST

```
/auth/register
```

### Request

```json
{
  "name": "Daras Preet Kaur",
  "email": "daras@gmail.com",
  "password": "password123"
}
```

### Response

```json
{
  "message": "User registered successfully"
}
```

---

## Login

POST

```
/auth/login
```

### Request

```json
{
  "email": "daras@gmail.com",
  "password": "password123"
}
```

### Response

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

---

## Current User

GET

```
/users/me
```

Returns the authenticated user's profile.

---

# Platform APIs

---

## Get Connected Platforms

GET

```
/platforms
```

Returns all connected competitive programming accounts.

---

## Connect Platform

POST

```
/platforms
```

### Request

```json
{
  "platform": "leetcode",
  "username": "daras"
}
```

---

## Update Platform Username

PATCH

```
/platforms/{profile_id}
```

---

## Disconnect Platform

DELETE

```
/platforms/{profile_id}
```

---

## Sync Platform

POST

```
/platforms/{profile_id}/sync
```

Triggers synchronization with the external platform.

Returns

- latest profile
- new submissions
- contests
- ratings

---

# Dashboard APIs

---

## Dashboard Summary

GET

```
/dashboard
```

Returns

- profile summary
- ratings
- solved count
- streak
- contest summary
- goal summary
- recent activity

---

## Recent Activity

GET

```
/dashboard/activity
```

Returns latest submissions.

---

## Submission Heatmap

GET

```
/dashboard/heatmap
```

Returns contribution-style calendar data.

---

## Leaderboard

GET

```
/dashboard/leaderboard
```

Returns leaderboard ranked by rating.

---

# Submission APIs

---

## Submission History

GET

```
/submissions
```

Supports

- pagination
- platform filter
- verdict filter
- language filter
- date range

---

## Submission Details

GET

```
/submissions/{id}
```

---

# Problem APIs

---

## Problem List

GET

```
/problems
```

Supports

- platform
- difficulty
- topic

---

## Problem Details

GET

```
/problems/{id}
```

---

# Contest APIs

---

## Contest History

GET

```
/contests
```

---

## Contest Details

GET

```
/contests/{id}
```

---

## Rating History

GET

```
/ratings/history
```

Returns rating progression for all connected platforms.

---

# Analytics APIs

---

## Overview

GET

```
/analytics
```

Returns

- total solved
- language usage
- platform comparison
- difficulty split
- topic distribution

---

## Difficulty Distribution

GET

```
/analytics/difficulty
```

---

## Topic Analysis

GET

```
/analytics/topics
```

---

## Language Statistics

GET

```
/analytics/languages
```

---

## Platform Comparison

GET

```
/analytics/platforms
```

---

## Contest Analytics

GET

```
/analytics/contests
```

---

# Goal APIs

---

## Get Goals

GET

```
/goals
```

---

## Create Goal

POST

```
/goals
```

---

## Update Goal

PATCH

```
/goals/{id}
```

---

## Delete Goal

DELETE

```
/goals/{id}
```

---

## Complete Goal

PATCH

```
/goals/{id}/complete
```

---

# Achievement APIs

---

## Get Achievements

GET

```
/achievements
```

Returns all achievements with unlock status.

---

## User Achievement History

GET

```
/users/me/achievements
```

---

# User APIs

---

## Update Profile

PATCH

```
/users/me
```

---

## Upload Avatar

POST

```
/users/me/avatar
```

---

## Change Password

PATCH

```
/users/me/password
```

---

# Health Check

GET

```
/health
```

Returns

```json
{
    "status": "healthy"
}
```

---

# Authentication

Protected endpoints require

```
Authorization: Bearer <JWT_TOKEN>
```

---

# API Response Format

Successful response

```json
{
  "success": true,
  "data": {}
}
```

Error response

```json
{
  "success": false,
  "message": "Description of error"
}
```

---

# Future APIs

Version 2 may include

- AI Coach
- Friends
- Notifications
- Study Plans
- Admin Dashboard