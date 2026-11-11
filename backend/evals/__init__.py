"""Offline evaluation harness for the AI Coach recommendation system.

Everything here runs against an in-memory SQLite database seeded with
synthetic users, problems, topics and submissions. No production data and
no external services are touched (``--mode agent`` is the only path that
calls Gemini, and only when GEMINI_API_KEY is set).
"""
