"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { getMemories, getDueMemories, updateMemory, deleteMemory, setPinned, getMemoryCount } from "@/lib/api";
import type { Memory, Message } from "@/types";
import Icon from "@/components/ui/Icon";

const ALL_TAGS = ["idea", "task", "person", "place", "work", "personal", "date", "misc"] as const;
type Tag = typeof ALL_TAGS[number];

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
  const diffDays = Math.ceil((due.getTime() - now.getTime()) / 86400000);

  if (diffDays < -1) return { label: `${-diffDays}d overdue`, overdue: true };
  if (diffDays <= 0) return { label: "due today", overdue: false };
  if (diffDays === 1) return { label: "due tomorrow", overdue: false };
  return { label: `due in ${diffDays}d`, overdue: false };
}

function isInTimeWindow(date: Date, window: string): boolean {
  const now = new Date();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfWeek = new Date(startOfDay);
  startOfWeek.setDate(startOfDay.getDate() - startOfDay.getDay());

  switch (window) {
    case "today":
      return date >= startOfDay;
    case "yesterday": {
      const yesterdayStart = new Date(startOfDay);
      yesterdayStart.setDate(yesterdayStart.getDate() - 1);
      return date >= yesterdayStart && date < startOfDay;
    }
    case "week":
      return date >= startOfWeek;
    case "7days": {
      const sevenDaysAgo = new Date(now);
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
      return date >= sevenDaysAgo;
    }
    case "30days": {
      const thirtyDaysAgo = new Date(now);
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      return date >= thirtyDaysAgo;
    }
    default:
      return true;
  }
}

interface MemoryRowProps {
  memory: Message;
  onUpdate: (id: string, content: string) => void;
  onDelete: (id: string) => void;
  onPinToggle: (id: string, pinned: boolean) => void;
}

function MemoryRow({ memory, onUpdate, onDelete, onPinToggle }: MemoryRowProps) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(memory.content);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const isPinned = memory.metadata?.pinned ?? false;
  const tags = memory.metadata?.tags ?? [];

  const handleSave = () => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== memory.content) {
      onUpdate(memory.id, trimmed);
    }
    setEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    }
    if (e.key === "Escape") {
      setEditValue(memory.content);
      setEditing(false);
    }
  };

  return (
    <div className="group flex flex-col sm:flex-row sm:items-start gap-3 p-4 rounded-xl border border-outline-variant/40 bg-surface-container-lowest hover:bg-surface-container transition-colors">
      <div className="flex-1 min-w-0">
        {editing ? (
          <textarea
            autoFocus
            className="w-full bg-transparent font-body-md text-body-md text-on-surface outline-none resize-none min-h-[60px]"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={handleKeyDown}
            onBlur={handleSave}
          />
        ) : (
          <p className="font-body-md text-body-md text-on-surface whitespace-pre-wrap break-words">
            {memory.content}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          <span className="font-metadata text-metadata text-outline">
            {relativeDate(memory.date)}
          </span>
          {tags.map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 rounded-md font-metadata text-metadata bg-primary-fixed/20 text-primary"
            >
              {tag}
            </span>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPinToggle(memory.id, !isPinned)}
          className={`p-2 rounded-lg transition-colors cursor-pointer ${
            isPinned
              ? "text-primary bg-primary-fixed/30"
              : "text-outline hover:text-primary hover:bg-primary-fixed/10"
          }`}
          aria-label={isPinned ? "Unpin memory" : "Pin memory"}
          title={isPinned ? "Unpin" : "Pin"}
        >
          <Icon name="pin" size={18} />
        </button>

        <button
          onClick={() => setEditing(true)}
          className="p-2 rounded-lg text-outline hover:text-on-surface hover:bg-surface-container-high transition-colors cursor-pointer"
          aria-label="Edit memory"
          title="Edit"
        >
          <Icon name="edit" size={18} />
        </button>

        {confirmDelete ? (
          <div className="flex items-center gap-1">
            <span className="font-metadata text-metadata text-error mr-1">Delete?</span>
            <button
              onClick={() => { setConfirmDelete(false); onDelete(memory.id); }}
              className="px-2 py-1 rounded-md bg-error text-on-error font-label-md text-label-md cursor-pointer"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="px-2 py-1 rounded-md bg-surface-container text-on-surface font-label-md text-label-md cursor-pointer"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="p-2 rounded-lg text-outline hover:text-error hover:bg-error/10 transition-colors cursor-pointer"
            aria-label="Delete memory"
            title="Delete"
          >
            <Icon name="delete" size={18} />
          </button>
        )}
      </div>
    </div>
  );
}

interface DueRowProps {
  memory: Memory;
  onDelete: (id: string) => void;
}

function DueRow({ memory, onDelete }: DueRowProps) {
  const [confirmDelete, setConfirmDelete] = useState(false);
  const { label, overdue } = formatDue(memory.metadata?.due ?? "");

  return (
    <div className="flex items-start gap-3 p-3 rounded-xl border border-outline-variant/40 bg-surface-container-lowest hover:bg-surface-container transition-colors">
      <div className="flex-1 min-w-0">
        <p className="font-body-md text-body-md text-on-surface break-words line-clamp-2">
          {memory.content}
        </p>
        <span
          className={`font-metadata text-metadata mt-1 block ${overdue ? "text-error" : "text-secondary"}`}
        >
          {label}
        </span>
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {confirmDelete ? (
          <div className="flex items-center gap-1">
            <span className="font-metadata text-metadata text-error mr-1">Delete?</span>
            <button
              onClick={() => { setConfirmDelete(false); onDelete(memory.id); }}
              className="px-2 py-1 rounded-md bg-error text-on-error font-label-md text-label-md cursor-pointer"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirmDelete(false)}
              className="px-2 py-1 rounded-md bg-surface-container text-on-surface font-label-md text-label-md cursor-pointer"
            >
              No
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirmDelete(true)}
            className="p-2 rounded-lg text-outline hover:text-error hover:bg-error/10 transition-colors cursor-pointer"
            aria-label="Delete memory"
            title="Delete"
          >
            <Icon name="delete" size={18} />
          </button>
        )}
      </div>
    </div>
  );
}

export default function LibraryPage() {
  const router = useRouter();
  const [memories, setMemories] = useState<Message[] | null>(null);
  const [dueMemories, setDueMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [timeWindow, setTimeWindow] = useState("all");
  const [selectedTag, setSelectedTag] = useState<Tag | null>(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    Promise.all([getMemories(), getMemoryCount(), getDueMemories()])
      .then(([mems, count, due]) => {
        setMemories(mems);
        setTotal(count);
        setDueMemories(due);
        setLoading(false);
      })
      .catch(() => {
        setMemories([]);
        setLoading(false);
      });
  }, []);

  const tagCounts = useMemo(() => {
    if (!memories) return {} as Record<string, number>;
    const counts: Record<string, number> = {};
    for (const m of memories) {
      for (const t of m.metadata?.tags ?? []) {
        counts[t] = (counts[t] ?? 0) + 1;
      }
    }
    return counts;
  }, [memories]);

  const addedLast30d = useMemo(() => {
    if (!memories) return 0;
    const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
    return memories.filter((m) => m.date.getTime() >= cutoff).length;
  }, [memories]);

  const topTags = useMemo(() => {
    return Object.entries(tagCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 3)
      .map(([tag]) => tag);
  }, [tagCounts]);

  const filtered = useMemo(() => {
    if (!memories) return [];
    let result = [...memories];

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter((m) => m.content.toLowerCase().includes(q));
    }

    if (timeWindow !== "all") {
      result = result.filter((m) => isInTimeWindow(m.date, timeWindow));
    }

    if (selectedTag) {
      result = result.filter((m) => m.metadata?.tags?.includes(selectedTag));
    }

    result.sort((a, b) => {
      const aPinned = a.metadata?.pinned ? 1 : 0;
      const bPinned = b.metadata?.pinned ? 1 : 0;
      if (aPinned !== bPinned) return bPinned - aPinned;
      return b.date.getTime() - a.date.getTime();
    });

    return result;
  }, [memories, search, timeWindow, selectedTag]);

  const handleUpdate = useCallback(async (id: string, content: string) => {
    await updateMemory(id, content);
    setMemories((prev) => prev ? prev.map((m) => (m.id === id ? { ...m, content } : m)) : prev);
  }, []);

  const handleDelete = useCallback(async (id: string) => {
    await deleteMemory(id);
    setMemories((prev) => prev ? prev.filter((m) => m.id !== id) : prev);
    setDueMemories((prev) => prev.filter((m) => m.id !== id));
    setTotal((t) => Math.max(0, t - 1));
  }, []);

  const handlePinToggle = useCallback(async (id: string, pinned: boolean) => {
    await setPinned(id, pinned);
    setMemories((prev) =>
      prev ? prev.map((m) => m.id === id ? { ...m, metadata: { ...m.metadata, pinned } } : m) : prev
    );
  }, []);

  return (
    <div className="min-h-dvh flex flex-col bg-background">
      {/* Header */}
      <header className="fixed top-0 left-0 right-0 z-40 bg-surface/70 glass-header border-b border-outline-variant/30">
        <div className="chat-container h-16 px-6 flex items-center gap-3">
          <button
            onClick={() => router.push("/chat")}
            className="p-2 -ml-2 rounded-lg text-on-surface-variant hover:bg-surface-container transition-colors cursor-pointer"
            aria-label="Back to chat"
          >
            <Icon name="arrow_back" size={20} />
          </button>
          <h1 className="font-headline-md text-headline-md text-on-surface flex-1">Library</h1>
          <span className="font-label-md text-label-md text-outline bg-surface-container rounded-lg px-3 py-1">
            {total} {total === 1 ? "memory" : "memories"}
          </span>
        </div>
      </header>

      {/* Main content */}
      <main className="chat-container flex-1 px-6 pt-24 pb-10">

        {/* Due & Upcoming section */}
        {!loading && dueMemories.length > 0 && (
          <section className="mb-8">
            <div className="flex items-center gap-2 mb-3">
              <h2 className="font-label-md text-label-md text-on-surface">Due & Upcoming</h2>
              <span className="px-2 py-0.5 rounded-full bg-secondary-container text-on-secondary-container font-metadata text-metadata">
                {dueMemories.length}
              </span>
            </div>
            <div className="flex flex-col gap-2">
              {dueMemories.map((m) => (
                <DueRow key={m.id} memory={m} onDelete={handleDelete} />
              ))}
            </div>
          </section>
        )}

        {/* Insights bar */}
        {!loading && memories && memories.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1 mb-6 font-metadata text-metadata text-outline">
            <span>{total} memories</span>
            <span>{addedLast30d} added this month</span>
            {topTags.length > 0 && (
              <span>top tags: {topTags.join(", ")}</span>
            )}
          </div>
        )}

        {/* Search + time filter */}
        <div className="flex flex-col sm:flex-row gap-3 mb-3">
          <div className="relative flex-1">
            <Icon name="search" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search memories..."
              className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-outline-variant/50 bg-surface-container-lowest text-on-surface font-body-md text-body-md outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-outline/60"
            />
          </div>
          <select
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            className="px-4 py-2.5 rounded-xl border border-outline-variant/50 bg-surface-container-lowest text-on-surface font-body-md text-body-md outline-none focus:ring-2 focus:ring-primary/20 cursor-pointer"
          >
            <option value="all">All time</option>
            <option value="today">Today</option>
            <option value="yesterday">Yesterday</option>
            <option value="week">This week</option>
            <option value="7days">Last 7 days</option>
            <option value="30days">Last 30 days</option>
          </select>
        </div>

        {/* Tag filter chips */}
        <div className="flex flex-wrap gap-2 mb-5">
          <button
            onClick={() => setSelectedTag(null)}
            className={`px-3 py-1 rounded-full font-label-md text-label-md transition-colors cursor-pointer ${
              selectedTag === null
                ? "bg-primary text-on-primary"
                : "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
            }`}
          >
            All
          </button>
          {ALL_TAGS.map((tag) => {
            const count = tagCounts[tag] ?? 0;
            const active = selectedTag === tag;
            return (
              <button
                key={tag}
                onClick={() => setSelectedTag(active ? null : tag)}
                className={`px-3 py-1 rounded-full font-label-md text-label-md transition-colors cursor-pointer ${
                  active
                    ? "bg-primary text-on-primary"
                    : count > 0
                    ? "bg-surface-container text-on-surface-variant hover:bg-surface-container-high"
                    : "bg-surface-container text-outline opacity-50 cursor-default"
                }`}
                disabled={count === 0}
              >
                {tag}
                {count > 0 && (
                  <span className="ml-1.5 opacity-70">{count}</span>
                )}
              </button>
            );
          })}
        </div>

        {/* Results count */}
        {!loading && (
          <p className="font-metadata text-metadata text-outline mb-4">
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
            {selectedTag && <span className="ml-1">tagged <em>{selectedTag}</em></span>}
          </p>
        )}

        {/* Memory list */}
        <div className="flex flex-col gap-3">
          {loading &&
            Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-24 rounded-xl skeleton-pulse" />
            ))}

          {!loading && filtered.length === 0 && (
            <div className="text-center py-12">
              <p className="font-body-md text-body-md text-outline">
                {search.trim() || timeWindow !== "all" || selectedTag
                  ? "No memories match your filters."
                  : "Nothing saved yet — start chatting to build your library."}
              </p>
            </div>
          )}

          {!loading &&
            filtered.map((m) => (
              <MemoryRow
                key={m.id}
                memory={m}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
                onPinToggle={handlePinToggle}
              />
            ))}
        </div>
      </main>
    </div>
  );
}
