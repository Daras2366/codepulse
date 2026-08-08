# CodePulse – System Architecture

## Overview

CodePulse follows a layered backend architecture that separates business logic, database access, API endpoints, and external platform integrations.

Each layer has a single responsibility, making the codebase modular, maintainable, and easy to extend.

---

# High-Level Architecture

```
                        +----------------------+
                        |      React UI        |
                        +----------+-----------+
                                   |
                             REST API (JWT)
                                   |
                                   ▼
                        +----------------------+
                        |   FastAPI Routers    |
                        +----------+-----------+
                                   |
                                   ▼
                        +----------------------+
                        |      Services        |
                        +----------+-----------+
                                   |
                 +-----------------+-----------------+
                 |                                   |
                 ▼                                   ▼
      Business Logic                    External Platform APIs
                 |                                   |
                 ▼                                   ▼
        +----------------+                 +----------------------+
        | Repositories   |                 | LeetCode            |
        +-------+--------+                 | Codeforces          |
                |                          | CodeChef            |
                ▼                          | AtCoder             |
        +----------------+                 +----------------------+
        | PostgreSQL DB  |
        +----------------+
```

---

# Project Structure

```
backend/

├── alembic/
│
├── app/
│   │
│   ├── core/
│   │      database.py
│   │      security.py
│   │
│   ├── models/
│   │
│   ├── schemas/
│   │
│   ├── repositories/
│   │
│   ├── services/
│   │
│   ├── routers/
│   │
│   ├── integrations/
│   │
│   ├── utils/
│   │
│   ├── dependencies.py
│   ├── config.py
│   └── main.py
│
├── docs/
│
└── tests/
```

---

# Layer Responsibilities

## Routers

Responsibilities

- Receive HTTP requests
- Validate input
- Call services
- Return API responses

Routers should never contain business logic.

Example

```
POST /login

↓

AuthService.login()
```

---

## Services

Services contain all business logic.

Responsibilities

- Authentication
- Analytics
- Goal tracking
- AI recommendations
- Platform synchronization

Services may call multiple repositories.

Example

```
DashboardService

↓

UserRepository
SubmissionRepository
ContestRepository

↓

Generate dashboard response
```

---

## Repositories

Repositories communicate directly with PostgreSQL.

Responsibilities

- CRUD operations
- SQL queries
- Database transactions

Repositories never contain business logic.

---

## Models

Models represent database tables.

Every table has exactly one SQLAlchemy model.

---

## Schemas

Pydantic schemas define

- Request validation
- Response serialization

Models should never be returned directly from APIs.

---

## Integrations

This module contains all communication with external platforms.

Examples

```
LeetCodeClient

CodeforcesClient

CodeChefClient

AtCoderClient
```

These services fetch user data but never interact directly with the database.

---

# Authentication Flow

```
User

↓

POST /login

↓

Router

↓

AuthService

↓

UserRepository

↓

Password Verification

↓

JWT Generation

↓

Access Token

↓

Frontend
```

---

# Dashboard Flow

```
Dashboard Request

↓

Dashboard Router

↓

Dashboard Service

↓

Repositories

↓

Aggregate Analytics

↓

Return Dashboard JSON
```

---

# Platform Synchronization Flow

```
User clicks "Sync"

↓

Platform Router

↓

Platform Service

↓

Platform Client

↓

Fetch latest data

↓

Normalize data

↓

Repositories

↓

Store in PostgreSQL

↓

Return updated statistics
```

---

# AI Coach Flow

The AI Coach does not generate recommendations from raw prompts alone.

Instead, it uses structured analytics.

```
Submissions

+

Contests

+

Topics

+

Ratings

↓

Analytics Engine

↓

Feature Extraction

↓

AI Prompt Builder

↓

LLM

↓

Recommendations
```

This separation makes recommendations more accurate and easier to improve over time.

---

# Analytics Pipeline

```
Raw Data

↓

Submissions

↓

Problems

↓

Contest History

↓

Aggregation

↓

Charts

↓

Dashboard
```

No dashboard statistics are stored permanently.

Analytics are generated from source data.

---

# Database Principles

The database stores only source-of-truth information.

Examples

Stored

- Users
- Profiles
- Problems
- Submissions
- Contests

Not Stored

- Current streak
- Rating graph
- Topic breakdown
- Heatmap
- Interview readiness

These values are calculated from stored data.

---

# Error Handling

Each service is responsible for handling expected errors.

Examples

- Invalid credentials
- Duplicate email
- Platform unavailable
- Invalid username
- Sync failure

Unexpected exceptions are handled globally by FastAPI.

---

# Security

Authentication uses JWT access tokens.

Passwords are never stored in plain text.

Protected routes require authentication.

Future improvements include

- Refresh tokens
- Rate limiting
- Audit logging

---

# Scalability

The architecture allows adding new platforms without changing the existing code structure.

Example

```
Current

LeetCode
Codeforces
CodeChef
AtCoder

↓

Future

HackerRank
SPOJ
GeeksforGeeks
Kattis
```

Only a new integration service is required.

The existing database schema remains unchanged.

---

# Design Principles

CodePulse follows these principles:

- Separation of concerns
- Single responsibility
- Dependency injection
- Platform-independent architecture
- Database normalization
- Feature-based scalability
- API-first backend design

These principles ensure that new features can be added with minimal changes to the existing codebase.