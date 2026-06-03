"use client";

import { useState, useEffect } from "react";
import { getMemories } from "@/lib/api";
import type { Message } from "@/types";

interface RecentMemoriesProps {
  onSuggestion: (text: string) => void;
}

function relativeDate(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const mins = Math.floor(diffMs / 60000);
  const hours = Math.floor(diffMs / 3600000);
  const days = Math.floor(diffMs / 86400000);

  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export default function RecentMemories({ onSuggestion }: RecentMemoriesProps) {
  const [items, setItems] = useState<Message[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getMemories()
      .then((data) => {
        const sorted = [...data].sort((a, b) => {
          const aPinned = a.metadata?.pinned ? 1 : 0;
          const bPinned = b.metadata?.pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          return b.date.getTime() - a.date.getTime();
        });
        setItems(sorted.slice(0, 5));
        setLoading(false);
      })
      .catch(() => {
        setItems([]);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="w-full">
        <p className="font-label-md text-label-md text-outline mb-3">Recent memories</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl skeleton-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="w-full text-center py-4">
        <p className="font-body-md text-body-md text-outline">
          Nothing saved yet — tell me something to remember.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full">
      <p className="font-label-md text-label-md text-outline mb-3">Recent memories</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((m) => (
          <button
            key={m.id}
            onClick={() => onSuggestion(`What do I know about: ${m.content}?`)}
            className="text-left rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-4 hover:bg-surface-container hover:border-outline-variant transition-colors active:scale-[0.98] duration-150 elevation-1"
          >
            <p className="font-body-md text-body-md text-on-surface line-clamp-2 mb-2">
              {m.content}
            </p>
            <span className="font-metadata text-metadata text-outline">
              {relativeDate(m.date)}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
