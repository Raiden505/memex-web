"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "@/lib/theme";
import Icon from "@/components/ui/Icon";

interface SettingsMenuProps {
  email?: string | null;
}

export default function SettingsMenu({ email }: SettingsMenuProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    if (open) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [open]);

  const themes: { key: "light" | "dark" | "system"; label: string; icon: string }[] = [
    { key: "light", label: "Light", icon: "sun" },
    { key: "dark", label: "Dark", icon: "moon" },
    { key: "system", label: "System", icon: "monitor" },
  ];

  return (
    <div ref={menuRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="p-2 text-on-surface-variant hover:opacity-80 transition-opacity active:scale-95 duration-200 cursor-pointer"
        aria-label="Settings"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Icon name="settings" size={24} />
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-outline-variant/50 bg-surface-container-lowest p-2 shadow-lg elevation-3 z-50"
          role="menu"
        >
          {/* Appearance */}
          <div className="px-3 py-2">
            <p className="font-label-md text-label-md text-outline mb-2">Appearance</p>
            <div className="flex gap-1 bg-surface-container rounded-lg p-1">
              {themes.map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTheme(t.key)}
                  role="menuitem"
                  className={`flex-1 flex items-center justify-center gap-1.5 rounded-md py-1.5 font-label-md text-label-md transition-colors cursor-pointer ${
                    theme === t.key
                      ? "bg-surface-container-lowest text-primary shadow-sm"
                      : "text-on-surface-variant hover:text-on-surface"
                  }`}
                >
                  <span>{t.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="my-1 border-t border-outline-variant/30" />

          {/* Account */}
          {email && (
            <div className="px-3 py-2">
              <p className="font-metadata text-metadata text-outline mb-1">Signed in as</p>
              <p className="font-body-md text-body-md text-on-surface truncate">{email}</p>
            </div>
          )}

          <div className="my-1 border-t border-outline-variant/30" />

          {/* Actions */}
          <ul role="none">
            <li>
              <button
                role="menuitem"
                className="w-full text-left px-3 py-2 rounded-lg font-body-md text-body-md text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
                onClick={() => {
                  setOpen(false);
                  router.push("/library");
                }}
              >
                Memory Library
              </button>
            </li>
            <li>
              <button
                role="menuitem"
                className="w-full text-left px-3 py-2 rounded-lg font-body-md text-body-md text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
                onClick={() => {
                  setOpen(false);
                  alert("Export data — coming in Phase 21.");
                }}
              >
                Export my data
              </button>
            </li>
          </ul>

          <div className="my-1 border-t border-outline-variant/30" />

          {/* About */}
          <div className="px-3 py-2">
            <p className="font-metadata text-metadata text-outline">Memex v0.17</p>
            <p className="font-metadata text-metadata text-outline-variant mt-0.5">
              Your memories are stored securely. AI responses may not always be accurate.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
