import { useState, useRef, useEffect } from "react";
import { ChevronDown, Search } from "lucide-react";

import { TOPICS, type TopicOption } from "@/lib/topics";

interface TopicSelectorProps {
  value: string; // topic slug
  onChange: (slug: string, name: string) => void;
  platform?: string | undefined;
}

export function TopicSelector({ value, onChange, platform }: TopicSelectorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Get selected topic name from slug
  const selectedTopic = TOPICS.find((t) => t.slug === value);
  const displayText = selectedTopic?.name || "Select topic";

  // Filter topics based on search query
  const filteredTopics = TOPICS.filter((topic) =>
    topic.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setSearchQuery("");
      }
    };

    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      // Focus search input when dropdown opens
      setTimeout(() => searchInputRef.current?.focus(), 0);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isOpen]);

  const handleSelect = (topic: TopicOption) => {
    onChange(topic.slug, topic.name);
    setIsOpen(false);
    setSearchQuery("");
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="mt-1 flex h-10 w-full items-center justify-between rounded-2xl border border-border bg-background px-4 text-caption outline-none transition-colors hover:border-violet focus:border-violet"
      >
        <span className={selectedTopic ? "text-foreground" : "text-subtle"}>{displayText}</span>
        <ChevronDown
          className={`h-4 w-4 text-subtle transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-50 mt-2 w-full rounded-2xl border border-border bg-card shadow-lg">
          {/* Search input */}
          <div className="border-b border-border p-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-subtle" />
              <input
                ref={searchInputRef}
                type="text"
                placeholder="Search topics..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-9 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-caption outline-none focus:border-violet"
              />
            </div>
          </div>

          {/* Options list */}
          <div className="max-h-64 overflow-y-auto p-2">
            {filteredTopics.length > 0 ? (
              filteredTopics.map((topic) => (
                <button
                  key={topic.slug}
                  type="button"
                  onClick={() => handleSelect(topic)}
                  className={`w-full rounded-xl px-3 py-2 text-left text-caption transition-colors hover:bg-muted ${
                    topic.slug === value ? "bg-muted font-medium text-violet" : "text-foreground"
                  }`}
                >
                  {topic.name}
                </button>
              ))
            ) : (
              <div className="px-3 py-6 text-center text-caption text-subtle">No topics found</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
