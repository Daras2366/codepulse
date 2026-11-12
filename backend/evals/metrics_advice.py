"""advice_specificity — deterministic metric for Stage 3 agent evals.

Definition (precise):

    advice_specificity(reasons, tool_results) is the fraction of
    recommendation ``reason`` strings that cite at least one FACT that was
    actually present in that run's tool outputs.

A "fact" is either:

- a TOPIC name appearing as a value under the keys ``topic``, ``topics``,
  ``topic_name`` or ``focus_topic`` anywhere in the tool results (lists are
  flattened), or
- a VERDICT/status string appearing as a value under the keys ``status``,
  ``verdict`` or as a key of a dict under ``verdicts`` — expanded through a
  fixed alias table (e.g. ``time_limit_exceeded`` also matches the text
  "time limit" or "TLE").

Matching is case-insensitive with word boundaries; whitespace, hyphens and
underscores are treated as equivalent separators inside multi-word facts.

The metric is 0.0 when there are no reasons or when the tool outputs
contain no citable facts. It measures whether the agent's stated reasoning
is grounded in tool data — it does NOT judge whether the advice is good.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Keys whose string (or list-of-strings) values count as topic facts.
_TOPIC_KEYS = {"topic", "topics", "topic_name", "focus_topic"}

# Keys whose string values count as raw verdict/status facts.
_VERDICT_VALUE_KEYS = {"status", "verdict"}

# Keys whose dict KEYS count as verdict facts (e.g. failure_patterns output).
_VERDICT_DICT_KEYS = {"verdicts"}

# Fixed alias table: canonical verdict value -> acceptable surface forms.
# Kept deliberately small and documented — this is a deterministic matcher,
# not an NLP judgement.
_VERDICT_ALIASES: dict[str, list[str]] = {
    "accepted": ["accepted", "ac"],
    "wrong_answer": ["wrong answer", "wrong-answer", "wa"],
    "time_limit_exceeded": [
        "time limit exceeded",
        "time-limit-exceeded",
        "time limit",
        "tle",
    ],
    "memory_limit_exceeded": [
        "memory limit exceeded",
        "memory-limit-exceeded",
        "memory limit",
        "mle",
    ],
    "runtime_error": ["runtime error", "runtime-error", "re"],
    "compile_error": ["compile error", "compile-error", "ce"],
}

# Normalise raw status/verdict strings to the canonical alias keys.
_STATUS_NORMALISE = {
    "accepted": "accepted",
    "wrong_answer": "wrong_answer",
    "wrong answer": "wrong_answer",
    "time_limit_exceeded": "time_limit_exceeded",
    "time limit": "time_limit_exceeded",
    "time limit exceeded": "time_limit_exceeded",
    "tle": "time_limit_exceeded",
    "memory_limit_exceeded": "memory_limit_exceeded",
    "memory limit": "memory_limit_exceeded",
    "memory limit exceeded": "memory_limit_exceeded",
    "mle": "memory_limit_exceeded",
    "runtime_error": "runtime_error",
    "runtime error": "runtime_error",
    "re": "runtime_error",
    "compile_error": "compile_error",
    "compile error": "compile_error",
    "ce": "compile_error",
}


def _norm_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def _fact_pattern(fact: str) -> re.Pattern:
    """Word-boundary regex for a fact; separators are interchangeable."""
    words = [w for w in re.split(r"[\s_\-]+", fact.strip().lower()) if w]
    body = r"[\s_\-]+".join(re.escape(w) for w in words)
    return re.compile(r"\b" + body + r"\b")


def _iter_strings(value: Any):
    """Yield all strings inside a (possibly nested) JSON-like value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _iter_strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _iter_strings(v)


def collect_facts(tool_results: Iterable[dict]) -> set[str]:
    """Collect citable facts (topics + verdict aliases) from tool outputs.

    ``tool_results`` is the dispatcher's recorded list of
    ``{"tool": name, "result": <json-able dict>}`` entries.
    """
    topic_facts: set[str] = set()
    verdict_facts: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                k = str(key).strip().lower()
                if k in _TOPIC_KEYS:
                    for s in _iter_strings(value):
                        n = _norm_text(s)
                        if n:
                            topic_facts.add(n)
                elif k in _VERDICT_VALUE_KEYS:
                    for s in _iter_strings(value):
                        canon = _STATUS_NORMALISE.get(_norm_text(s))
                        if canon:
                            verdict_facts.add(canon)
                elif k in _VERDICT_DICT_KEYS and isinstance(value, dict):
                    for vk in value.keys():
                        canon = _STATUS_NORMALISE.get(_norm_text(str(vk)))
                        if canon:
                            verdict_facts.add(canon)
                walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    for entry in tool_results or []:
        result = entry.get("result") if isinstance(entry, dict) else entry
        walk(result)

    facts: set[str] = set(topic_facts)
    for canon in verdict_facts:
        facts.update(_VERDICT_ALIASES.get(canon, [canon]))
    return facts


def advice_specificity(
    reasons: Iterable[str], tool_results: Iterable[dict]
) -> float:
    """Fraction of reasons citing ≥1 fact present in the tool outputs.

    See module docstring for the precise definition of "fact".
    Returns 0.0 for empty reasons or when no facts were collected.
    """
    reason_list = [str(r) for r in reasons if r]
    if not reason_list:
        return 0.0

    facts = collect_facts(tool_results)
    if not facts:
        return 0.0

    patterns = [_fact_pattern(f) for f in facts]
    cited = 0
    for reason in reason_list:
        text = reason.lower()
        if any(p.search(text) for p in patterns):
            cited += 1
    return cited / len(reason_list)
