"""
Canonical DSA topic taxonomy for CodePulse analytics.

This module is the single source of truth for converting platform-specific
problem tags (Codeforces, LeetCode, etc.) into broad, meaningful DSA
categories used by the Analytics UI.

Design goals:
- Keep analytics focused on meaningful DSA concepts.
- Merge platform-specific aliases into one canonical category.
- Ignore noisy/meta tags such as "implementation" and "brute force".
- Avoid creating dozens of tiny slices in the topic distribution chart.
- Keep the taxonomy extensible for future platforms.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Canonical categories
# ---------------------------------------------------------------------------

CANONICAL_TOPICS = [
    "Arrays",
    "Searching",
    "Sorting",
    "Recursion",
    "Hashing",
    "Linked Lists",
    "Stacks & Queues",
    "Trees",
    "Graphs",
    "Dynamic Programming",
    "Greedy",
    "Bit Manipulation",
    "Strings",
    "Math",
    "Two Pointers",
    "Sliding Window",
    "Heap / Priority Queue",
    "Backtracking",
    "Union Find / DSU",
    "Advanced Data Structures",
    "Advanced Algorithms",
]


# ---------------------------------------------------------------------------
# Ignored / non-informative tags
# ---------------------------------------------------------------------------

# These tags do not tell the user anything useful about the DSA concept
# they are practicing, so they should not appear in the analytics chart.
IGNORED_TAGS = {
    "*special",
    "brute force",
    "communication",
    "constructive algorithms",
    "data structures",
    "database",
    "enumeration",
    "expression parsing",
    "games",
    "implementation",
    "interactive",
    "schedules",
}


# ---------------------------------------------------------------------------
# Raw platform tag -> canonical category
# ---------------------------------------------------------------------------

TOPIC_ALIASES: dict[str, str] = {
    # -----------------------------------------------------------------------
    # Arrays
    # -----------------------------------------------------------------------
    "array": "Arrays",
    "arrays": "Arrays",
    "matrices": "Arrays",
    "matrix": "Arrays",

    # -----------------------------------------------------------------------
    # Searching
    # -----------------------------------------------------------------------
    "binary search": "Searching",
    "binary-search": "Searching",
    "ternary search": "Searching",
    "ternary-search": "Searching",
    "searching": "Searching",

    # -----------------------------------------------------------------------
    # Sorting
    # -----------------------------------------------------------------------
    "sorting": "Sorting",
    "sortings": "Sorting",
    "sort": "Sorting",

    # -----------------------------------------------------------------------
    # Recursion / divide and conquer
    # -----------------------------------------------------------------------
    "recursion": "Recursion",
    "recursive": "Recursion",
    "divide and conquer": "Recursion",
    "divide-and-conquer": "Recursion",

    # -----------------------------------------------------------------------
    # Hashing
    # -----------------------------------------------------------------------
    "hash table": "Hashing",
    "hashing": "Hashing",
    "hash map": "Hashing",
    "hashmap": "Hashing",
    "hashing / map": "Hashing",

    # -----------------------------------------------------------------------
    # Linked Lists
    # -----------------------------------------------------------------------
    "linked list": "Linked Lists",
    "linked lists": "Linked Lists",
    "linked-list": "Linked Lists",

    # -----------------------------------------------------------------------
    # Stacks & Queues
    # -----------------------------------------------------------------------
    "stack": "Stacks & Queues",
    "stacks": "Stacks & Queues",
    "queue": "Stacks & Queues",
    "queues": "Stacks & Queues",
    "monotonic stack": "Stacks & Queues",
    "monotonic stacks": "Stacks & Queues",

    # -----------------------------------------------------------------------
    # Trees
    # -----------------------------------------------------------------------
    "tree": "Trees",
    "trees": "Trees",
    "binary tree": "Trees",
    "binary trees": "Trees",
    "binary search tree": "Trees",
    "bst": "Trees",
    "segment tree": "Trees",
    "segment trees": "Trees",
    "fenwick tree": "Trees",
    "binary indexed tree": "Trees",
    "trie": "Trees",
    "tries": "Trees",

    # -----------------------------------------------------------------------
    # Graphs
    # -----------------------------------------------------------------------
    "graph": "Graphs",
    "graphs": "Graphs",
    "graph theory": "Graphs",
    "graph-theory": "Graphs",

    "breadth-first search": "Graphs",
    "breadth first search": "Graphs",
    "bfs": "Graphs",

    "depth-first search": "Graphs",
    "depth first search": "Graphs",
    "dfs": "Graphs",
    "dfs and similar": "Graphs",

    "bipartite graph": "Graphs",
    "bipartite graphs": "Graphs",

    "dijkstra's algorithm": "Graphs",
    "dijkstra": "Graphs",

    "bellman–ford algorithm": "Graphs",
    "bellman-ford algorithm": "Graphs",
    "bellman ford": "Graphs",

    "floyd–warshall algorithm": "Graphs",
    "floyd-warshall algorithm": "Graphs",
    "floyd warshall": "Graphs",

    "shortest path": "Graphs",
    "shortest paths": "Graphs",

    "minimum spanning tree": "Graphs",
    "minimum spanning trees": "Graphs",
    "mst": "Graphs",

    "kruskal's algorithm": "Graphs",
    "kruskal": "Graphs",

    "prim's algorithm": "Graphs",
    "prim": "Graphs",

    "borůvka's algorithm": "Graphs",
    "boruvka's algorithm": "Graphs",
    "boruvka": "Graphs",

    "topological sort": "Graphs",
    "topological sorting": "Graphs",

    "flows": "Graphs",
    "flow": "Graphs",
    "max flow": "Graphs",
    "network flow": "Graphs",

    "graph matchings": "Graphs",
    "matching": "Graphs",
    "bipartite matching": "Graphs",
    
    "dsu": "Graphs",
    "union-find": "Graphs",
    "union find": "Graphs",
    "disjoint set": "Graphs",
    "disjoint set union": "Graphs",
    
    # -----------------------------------------------------------------------
    # Dynamic Programming
    # -----------------------------------------------------------------------
    "dp": "Dynamic Programming",
    "dynamic programming": "Dynamic Programming",
    "dynamic-programming": "Dynamic Programming",
    "knapsack": "Dynamic Programming",
    "knapsack problem": "Dynamic Programming",
    "memoization": "Dynamic Programming",
    "tabulation": "Dynamic Programming",

    # -----------------------------------------------------------------------
    # Greedy
    # -----------------------------------------------------------------------
    "greedy": "Greedy",

    # -----------------------------------------------------------------------
    # Bit Manipulation
    # -----------------------------------------------------------------------
    "bit manipulation": "Bit Manipulation",
    "bit manipulation ": "Bit Manipulation",
    "bitmasks": "Bit Manipulation",
    "bitmask": "Bit Manipulation",
    "bitmask manipulation": "Bit Manipulation",

    # -----------------------------------------------------------------------
    # Strings
    # -----------------------------------------------------------------------
    "string": "Strings",
    "strings": "Strings",
    "string matching": "Strings",
    "string manipulation": "Strings",
    "string hashing": "Strings",

    # -----------------------------------------------------------------------
    # Two Pointers
    # -----------------------------------------------------------------------
    "two pointers": "Two Pointers",
    "two pointer": "Two Pointers",
    "two-pointers": "Two Pointers",

    # -----------------------------------------------------------------------
    # Sliding Window
    # -----------------------------------------------------------------------
    "sliding window": "Sliding Window",
    "sliding-window": "Sliding Window",

    # -----------------------------------------------------------------------
    # Heap / Priority Queue
    # -----------------------------------------------------------------------
    "heap": "Heap / Priority Queue",
    "heaps": "Heap / Priority Queue",
    "priority queue": "Heap / Priority Queue",
    "heap (priority queue)": "Heap / Priority Queue",

    # -----------------------------------------------------------------------
    # Backtracking
    # -----------------------------------------------------------------------
    "backtracking": "Backtracking",
    "backtrack": "Backtracking",

    # -----------------------------------------------------------------------
    # Math
    # -----------------------------------------------------------------------
    "math": "Math",
    "mathematics": "Math",
    "number theory": "Math",
    "number-theory": "Math",
    "chinese remainder theorem": "Math",
    "combinatorics": "Math",
    "probabilities": "Math",
    "probability": "Math",
    "geometry": "Math",

    # -----------------------------------------------------------------------
    # Advanced Data Structures
    # -----------------------------------------------------------------------
    "string suffix structures": "Advanced Data Structures",
    "suffix array": "Advanced Data Structures",
    "suffix tree": "Advanced Data Structures",
    "suffix automaton": "Advanced Data Structures",

    # -----------------------------------------------------------------------
    # Advanced Algorithms
    # -----------------------------------------------------------------------
    "fft": "Advanced Algorithms",
    "fast fourier transform": "Advanced Algorithms",
    "meet-in-the-middle": "Advanced Algorithms",
    "meet in the middle": "Advanced Algorithms",
    "2-sat": "Advanced Algorithms",
    "2 sat": "Advanced Algorithms",
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def normalize_raw_tag(tag: str | None) -> str:
    """
    Normalize a raw platform tag before looking it up.

    Examples:
        " Dynamic Programming " -> "dynamic programming"
        "BINARY SEARCH"         -> "binary search"
        "Graphs"                -> "graphs"
    """
    if not tag:
        return ""

    return " ".join(tag.strip().lower().split())


def canonicalize_topic(tag: str | None) -> str | None:
    """
    Convert a raw platform topic into a canonical CodePulse category.

    Returns:
        Canonical topic name if the tag is meaningful.
        None if the tag should be ignored or is unknown.
    """
    normalized = normalize_raw_tag(tag)

    if not normalized:
        return None

    if normalized in IGNORED_TAGS:
        return None

    return TOPIC_ALIASES.get(normalized)


def canonicalize_topics(tags: list[str]) -> list[str]:
    """
    Convert a list of raw tags into unique canonical categories.

    A problem with multiple tags that map to the same category is counted
    only once for that category.

    Example:
        ["graphs", "dfs and similar", "shortest paths"]
        -> ["Graphs"]
    """
    canonical_topics: set[str] = set()

    for tag in tags:
        canonical = canonicalize_topic(tag)

        if canonical is not None:
            canonical_topics.add(canonical)

    # Return in the same stable order as CANONICAL_TOPICS.
    return [
        topic
        for topic in CANONICAL_TOPICS
        if topic in canonical_topics
    ]


def is_ignored_topic(tag: str | None) -> bool:
    """Return True if a raw tag is intentionally excluded from analytics."""
    normalized = normalize_raw_tag(tag)
    return normalized in IGNORED_TAGS


def is_known_topic(tag: str | None) -> bool:
    """Return True if a raw tag maps to a canonical analytics category."""
    return canonicalize_topic(tag) is not None