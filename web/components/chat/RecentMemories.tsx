"use client";

import { useState, useEffect } from "react";
import { getMemories, getDueMemories } from "@/lib/api";
import type { Memory, Message } from "@/types";

interface RecentMemoriesProps {
  onAskMemory: (content: string) => void;
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

function formatDue(dueIso: string): { label: string; overdue: boolean } {
  const due = new Date(dueIso + (dueIso.endsWith("Z") ? "" : "Z"));
  const now = new Date();
  // Compare calendar days in local time so "10pm today" is never "tomorrow"
  const dueDay = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const diffDays = Math.round((dueDay.getTime() - today.getTime()) / 86400000);

  if (diffDays < 0) return { label: `${-diffDays}d overdue`, overdue: true };
  if (diffDays === 0) return { label: "due today", overdue: false };
  if (diffDays === 1) return { label: "due tomorrow", overdue: false };
  return { label: `due in ${diffDays}d`, overdue: false };
}

export default function RecentMemories({ onAskMemory }: RecentMemoriesProps) {
  const [items, setItems] = useState<Message[] | null>(null);
  const [dueItems, setDueItems] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getMemories(), getDueMemories()])
      .then(([data, due]) => {
        const sorted = [...data].sort((a, b) => {
          const aPinned = a.metadata?.pinned ? 1 : 0;
          const bPinned = b.metadata?.pinned ? 1 : 0;
          if (aPinned !== bPinned) return bPinned - aPinned;
          return b.date.getTime() - a.date.getTime();
        });
        setItems(sorted.slice(0, 5));
        setDueItems(due);
        setLoading(false);
      })
      .catch(() => {
        setItems([]);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="w-full flex flex-col gap-6">
        <div>
          <p className="font-label-md text-label-md text-outline mb-3">Due soon</p>
          <div className="flex gap-3">
            {Array.from({ length: 2 }).map((_, i) => (
              <div key={i} className="h-20 w-52 flex-shrink-0 rounded-xl skeleton-pulse" />
            ))}
          </div>
        </div>
        <div>
          <p className="font-label-md text-label-md text-outline mb-3">Recent memories</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 rounded-xl skeleton-pulse" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const hasRecent = items && items.length > 0;
  const hasDue = dueItems.length > 0;

  if (!hasRecent && !hasDue) {
    return (
      <div className="w-full text-center py-4">
        <p className="font-body-md text-body-md text-outline">
          Nothing saved yet — tell me something to remember.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full flex flex-col gap-6">
      {hasDue && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <p className="font-label-md text-label-md text-outline">Due soon</p>
            <span className="px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-metadata text-metadata">
              {dueItems.length}
            </span>
          </div>
          <div className="flex gap-3 overflow-x-auto scrollbar-none pb-1">
            {dueItems.map((m) => {
              const { label, overdue } = formatDue(m.metadata?.due ?? "");
              return (
                <button
                  key={m.id}
                  onClick={() => onAskMemory(m.content)}
                  className="flex-shrink-0 w-52 text-left rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-3 hover:bg-surface-container hover:border-outline-variant transition-colors active:scale-[0.98] duration-150 elevation-1"
                >
                  <p className="font-body-md text-body-md text-on-surface line-clamp-2 mb-2">
                    {m.content}
                  </p>
                  <span className={`font-metadata text-metadata ${overdue ? "text-error" : "text-secondary"}`}>
                    {label}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {hasRecent && (
        <div>
          <p className="font-label-md text-label-md text-outline mb-3">Recent memories</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {items!.map((m) => (
              <button
                key={m.id}
                onClick={() => onAskMemory(m.content)}
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
      )}
    </div>
  );
}
