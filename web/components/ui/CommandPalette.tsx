"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "@/lib/theme";
import Icon from "@/components/ui/Icon";

interface Command {
  id: string;
  label: string;
  hint?: string;
  action: () => void;
}

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onCapture: () => void;
  onDigest: () => void;
}

export default function CommandPalette({ open, onClose, onCapture, onDigest }: CommandPaletteProps) {
  const router = useRouter();
  const { theme, setTheme } = useTheme();
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const nextTheme = theme === "light" ? "dark" : theme === "dark" ? "system" : "light";

  const commands: Command[] = [
    {
      id: "capture",
      label: "Quick save",
      hint: "C",
      action: () => { onClose(); onCapture(); },
    },
    {
      id: "library",
      label: "Open Library",
      action: () => { onClose(); router.push("/library"); },
    },
    {
      id: "digest",
      label: "Today's digest",
      action: () => { onClose(); onDigest(); },
    },
    {
      id: "theme",
      label: `Switch to ${nextTheme} mode`,
      action: () => { setTheme(nextTheme); onClose(); },
    },
  ];

  const filtered = commands.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (open) {
      setQuery("");
      setActive(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  useEffect(() => {
    setActive(0);
  }, [query]);

  const execute = useCallback(
    (cmd: Command) => { cmd.action(); },
    []
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filtered[active]) execute(filtered[active]);
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] px-4"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-background/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-2xl border border-outline-variant/50 bg-surface-container-lowest shadow-xl elevation-3 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-outline-variant/30">
          <Icon name="search" size={18} className="text-outline flex-shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command…"
            className="flex-1 bg-transparent font-body-md text-on-surface placeholder:text-outline/60 outline-none"
          />
          <kbd className="hidden sm:block font-label-md text-label-md text-outline bg-surface-container rounded px-1.5 py-0.5 text-xs flex-shrink-0">
            Esc
          </kbd>
        </div>

        {/* Command list */}
        <ul className="py-1 max-h-64 overflow-y-auto" role="listbox">
          {filtered.length === 0 && (
            <li className="px-4 py-3 font-body-md text-body-md text-outline text-center">
              No commands match.
            </li>
          )}
          {filtered.map((cmd, i) => (
            <li
              key={cmd.id}
              role="option"
              aria-selected={i === active}
              onMouseEnter={() => setActive(i)}
              onClick={() => execute(cmd)}
              className={`flex items-center justify-between px-4 py-2.5 cursor-pointer transition-colors ${
                i === active
                  ? "bg-primary/10 text-primary"
                  : "text-on-surface hover:bg-surface-container"
              }`}
            >
              <span className="font-body-md text-body-md">{cmd.label}</span>
              {cmd.hint && (
                <kbd className="font-label-md text-label-md text-outline bg-surface-container rounded px-1.5 py-0.5 text-xs">
                  {cmd.hint}
                </kbd>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
