/**
 * Canonical DSA Topics for CodePulse
 *
 * This list provides human-readable topic names and their corresponding slugs
 * for use throughout the application, particularly in goal creation.
 */

export interface TopicOption {
  name: string;
  slug: string;
}

export const TOPICS: TopicOption[] = [
  { name: "Array", slug: "array" },
  { name: "Binary Search", slug: "binary-search" },
  { name: "Bit Manipulation", slug: "bit-manipulation" },
  { name: "Brainteaser", slug: "brainteaser" },
  { name: "Combinatorics", slug: "combinatorics" },
  { name: "Data Stream", slug: "data-stream" },
  { name: "Depth-First Search", slug: "depth-first-search" },
  { name: "Divide and Conquer", slug: "divide-and-conquer" },
  { name: "Dynamic Programming", slug: "dynamic-programming" },
  { name: "Graph", slug: "graph" },
  { name: "Greedy", slug: "greedy" },
  { name: "Hash Table", slug: "hash-table" },
  { name: "Heap", slug: "heap" },
  { name: "Linked List", slug: "linked-list" },
  { name: "Math", slug: "math" },
  { name: "Matrix", slug: "matrix" },
  { name: "Prefix Sum", slug: "prefix-sum" },
  { name: "Queue", slug: "queue" },
  { name: "Recursion", slug: "recursion" },
  { name: "Segment Tree", slug: "segment-tree" },
  { name: "Sliding Window", slug: "sliding-window" },
  { name: "Sorting", slug: "sorting" },
  { name: "Stack", slug: "stack" },
  { name: "String", slug: "string" },
  { name: "Tree", slug: "tree" },
  { name: "Trie", slug: "trie" },
  { name: "Two Pointers", slug: "two-pointers" },
  { name: "Union Find", slug: "union-find" },
];

/**
 * Get topic name from slug
 */
export function getTopicName(slug: string): string | undefined {
  return TOPICS.find((t) => t.slug === slug)?.name;
}

/**
 * Get topic slug from name
 */
export function getTopicSlug(name: string): string | undefined {
  return TOPICS.find((t) => t.name === name)?.slug;
}
