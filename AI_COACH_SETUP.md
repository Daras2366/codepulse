# CodePulse AI Coach Setup Guide

## Overview

The CodePulse AI Coach provides personalized DSA practice recommendations and an interactive chat interface powered by Google's Gemini API. It analyzes your actual performance data from Codeforces, LeetCode, and other platforms to provide actionable advice.

## Architecture

### Backend Components

1. **PerformanceAnalyzer** (`backend/app/services/performance_analyzer.py`)
   - Analyzes user performance from stored data
   - Calculates topic strength, difficulty coverage, consistency, contest performance
   - Returns structured PerformanceProfile

2. **RecommendationService** (`backend/app/services/recommendation_service.py`)
   - Generates prioritized recommendations from PerformanceProfile
   - Identifies weak topics, difficulty gaps, consistency issues
   - All calculations are deterministic, no LLM involvement

3. **GeminiService** (`backend/app/services/gemini_service.py`)
   - Wrapper for Google Gemini API
   - Generates conversational responses based on performance context
   - Includes safety constraints and input validation

4. **Recommendations Router** (`backend/app/routers/recommendations.py`)
   - `GET /recommendations` - Returns personalized recommendations
   - `POST /ai-coach/chat` - Chat with AI Coach
   - All endpoints require JWT authentication

### Frontend Components

1. **Recommendations API** (`frontend/src/api/recommendations.ts`)
   - TypeScript interfaces for recommendation and chat responses
   - API client functions using existing authentication

2. **AI Coach Route** (`frontend/src/routes/ai-coach.tsx`)
   - Displays personalized recommendations
   - Interactive chat interface with conversation history
   - Loading, error, and insufficient-data states

## Environment Configuration

### Required Environment Variables

Add these to your backend environment (`.env` file in the `backend/` directory):

```bash
# Gemini AI Coach Configuration
# Get your API key from: https://makersuite.google.com/app/apikey
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-flash
```

### How to Get a Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key
5. Add it to your backend `.env` file as `GEMINI_API_KEY`

### Available Models

- `gemini-1.5-flash` - Fast, cost-effective (recommended for chat)
- `gemini-1.5-pro` - Higher quality, slower, more expensive

## Starting the Project

### Backend

```bash
cd backend
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
# Install dependencies (if not already installed)
npm install

# Start the development server
npm run dev
```

## Verification

1. Sign in to CodePulse
2. Sync at least one platform (Codeforces or LeetCode)
3. Navigate to the AI Coach page (`/ai-coach`)
4. You should see:
   - Personalized recommendations based on your performance
   - Strength and weakness indicators
   - AI Coach chat interface

### Testing the AI Coach Chat

1. With `GEMINI_API_KEY` configured:
   - Type a question like "What should I practice today?"
   - You should receive a personalized response based on your data

2. Without `GEMINI_API_KEY`:
   - The chat will show a message indicating AI Coach is not configured
   - Recommendations will still work (they don't require the API key)

## API Endpoints

### GET /recommendations

Returns personalized recommendations based on performance analysis.

**Response:**
```json
{
  "recommendations": [
    {
      "category": "topic",
      "title": "Practice Dynamic Programming problems",
      "reason": "Your DP performance is relatively weak...",
      "priority": "high",
      "suggested_activity": "Solve 10 DP problems",
      "target_metric": "10 problems solved",
      "difficulty_suggestion": "medium"
    }
  ],
  "data_quality": {
    "has_topic_data": true,
    "has_submission_data": true,
    "has_contest_data": false,
    "profile_reported_solved": 150,
    "locally_tagged_solved": 120,
    "historical_coverage_days": 90,
    "platform_coverage": ["codeforces", "leetcode"]
  },
  "has_sufficient_data": true
}
```

### POST /ai-coach/chat

Chat with the AI Coach about your performance.

**Request:**
```json
{
  "message": "What should I practice today?",
  "conversation_history": [
    {"role": "user", "content": "How has my performance changed?"},
    {"role": "assistant", "content": "Your rating has been improving..."}
  ]
}
```

**Response:**
```json
{
  "response": "Based on your performance data, I recommend focusing on...",
  "is_configured": true
}
```

## Limitations and Known Issues

### API Key Not Configured
- Chat functionality will be disabled
- Recommendations will still work (deterministic, no LLM required)
- Clear error message shown to user

### Insufficient Data
- If user has no synced platforms or very little activity
- Shows "Insufficient Data" state with guidance to sync platforms
- No fake data or fabricated statistics

### Provider Quota
- Gemini API has free tier limits
- If quota exhausted, chat returns 503 error
- User sees "AI Coach unavailable" message

### Conversation History
- Limited to 10 messages per request
- Limited to 1000 characters per message
- Not persisted (session-only for MVP)

## Security Considerations

1. **API Key Security**
   - Never commit `.env` file with real API key
   - API key is loaded via environment variables only
   - Never exposed to frontend

2. **User Isolation**
   - All queries scoped to authenticated user ID
   - User ID derived from JWT, not client input
   - Cannot access another user's data

3. **Input Validation**
   - Message length limited to 1000 characters
   - Conversation history limited to 10 messages
   - Sanitized before sending to LLM

4. **LLM Context**
   - Only compact summaries sent to LLM
   - No raw database dumps or complete history
   - System instructions prevent override

## Testing

### Backend Tests

```bash
cd backend
pytest tests/test_recommendations.py -v
```

### Frontend Build

```bash
cd frontend
npm run build
```

## Troubleshooting

### "AI Coach is not configured"
- Add `GEMINI_API_KEY` to backend `.env`
- Restart backend server
- Refresh the page

### "Insufficient Data"
- Sync at least one platform (Codeforces or LeetCode)
- Solve some problems to generate meaningful recommendations
- Refresh the AI Coach page

### Chat returns 503 error
- Check Gemini API key is valid
- Check API quota (free tier limits)
- Check network connectivity to Google API

### Recommendations seem incorrect
- Verify platform sync is up to date
- Check that problems have topic tags (for topic recommendations)
- Ensure sufficient historical data (30+ problems recommended)

## Future Enhancements

Potential improvements for future versions:

1. Persistent conversation history
2. Study plan generation and tracking
3. Problem-specific recommendations with links
4. Rating prediction with confidence intervals
5. Contest preparation schedules
6. Multi-language support
7. Alternative LLM providers (OpenAI, Anthropic)
