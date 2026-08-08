# CodePulse – Project Overview

## Overview

CodePulse is a full-stack competitive programming analytics platform that helps programmers monitor their progress across multiple coding platforms from a single dashboard.

Instead of manually checking different websites, CodePulse aggregates coding activity, contest performance, problem-solving statistics, and learning patterns into one unified interface. The platform also generates personalized insights and AI-powered recommendations to help users improve their performance.

---

## Problem Statement

Competitive programmers typically solve problems across multiple platforms such as LeetCode, Codeforces, CodeChef, and AtCoder.

Each platform stores its own statistics independently, making it difficult to:

- Track overall progress
- Compare ratings across platforms
- Monitor long-term consistency
- Identify weak topics
- Plan future practice
- Analyze contest performance

CodePulse solves this problem by providing a centralized analytics dashboard.

---

# Objectives

- Aggregate data from multiple competitive programming platforms
- Track problem solving activity
- Visualize contest performance
- Generate detailed analytics
- Provide AI-powered recommendations
- Help users build consistent practice habits

---

# Supported Platforms (Version 1)

- LeetCode
- Codeforces
- CodeChef
- AtCoder

The architecture is designed so additional platforms can be integrated without changing the database schema.

---

# Core Features

## Authentication

- User Registration
- User Login
- JWT Authentication
- Password Encryption

---

## Platform Integration

Users can connect multiple competitive programming accounts.

Example:

- LeetCode
- Codeforces
- CodeChef
- AtCoder

Each connected profile can be synchronized independently.

---

## Dashboard

The dashboard provides a high-level overview of the user's coding activity.

Features include:

- Problems solved
- Current rating
- Daily streak
- Longest streak
- Daily goals
- Recent activity
- Platform summary
- Submission heatmap
- Topic breakdown

---

## Analytics

Detailed analytics include:

- Rating progression
- Difficulty distribution
- Topic-wise analysis
- Platform comparison
- Submission trends
- Contest performance
- Accuracy statistics

---

## Contest Tracking

Track contest history including:

- Contest rating
- Rank
- Rating changes
- Contest participation
- Historical rating graph

---

## Goal Management

Users can create personal goals such as:

- Solve 1000 problems
- Reach 1900 Codeforces rating
- Complete 60-day streak
- Finish Dynamic Programming roadmap

---

## Achievement System

Achievements reward important milestones.

Examples:

- Century Club
- Marathoner
- Graph Whisperer
- Perfect Contest

---

## AI Coach

The AI Coach analyzes user performance and provides personalized recommendations.

Examples:

- Weak topics
- Suggested problems
- Practice roadmap
- Contest preparation
- Interview readiness

---

# Technology Stack

## Frontend

- React
- TypeScript
- Vite
- TailwindCSS
- shadcn/ui
- TanStack Query

## Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Pydantic

## Authentication

- JWT
- Passlib (bcrypt)

## Future Integrations

- OpenAI API
- Redis
- Celery
- Docker

---

# Project Architecture

The backend follows a layered architecture.

```
Client
   │
   ▼
Routers
   │
   ▼
Services
   │
   ▼
Repositories
   │
   ▼
Database
```

Each layer has a single responsibility, making the application modular and maintainable.

---

# Future Scope

- More competitive programming platforms
- Friend system
- Community leaderboard
- AI mock interviews
- Resume analysis
- Company-wise preparation
- Daily email reports
- Mobile application

---

# Project Status

Current Phase:

Backend architecture and database development.