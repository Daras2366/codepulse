# CodePulse Insights

CodePulse is a responsive frontend dashboard for tracking competitive-programming practice across LeetCode, Codeforces, CodeChef, and AtCoder.

## Status

This repository currently contains the frontend prototype. Dashboard content is powered by sample data while API integrations are under development.

## Highlights

- Responsive dashboard with light and dark themes
- Rating trends, topic breakdown, activity heatmap, goals, and achievements
- Platform overview and contest history views
- AI-coach interface for practice recommendations

## Tech stack

- React 19 and TypeScript
- TanStack Start and TanStack Router
- Tailwind CSS
- Recharts and Lucide icons

## Run locally

Requires Node.js 22.12 or later.

bash
npm install
npm run dev


Use npm run lint to check code quality and npm run build to create a production build.

## Roadmap

- Connect platform profiles through a backend API
- Replace sample data with authenticated user data
- Add saved preferences and notifications
- Add exports and shareable progress reports