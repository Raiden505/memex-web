"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "@/lib/theme";
import { exportMemories, importMemories } from "@/lib/api";
import Icon from "@/components/ui/Icon";

interface SettingsMenuProps {
  email?: string | null;
}

export default function SettingsMenu({ email }: SettingsMenuProps) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [importStatus, setImportStatus] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  const handleExport = async () => {
    try {
      const data = await exportMemories();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `memex-export-${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // silent — download failure is obvious
    }
  };

  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    setImporting(true);
    setImportStatus(null);
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const items: { content: string }[] = Array.isArray(parsed)
        ? parsed.filter((x: unknown) => typeof (x as { content?: unknown }).content === "string").map((x: { content: string }) => ({ content: x.content }))
        : [];
      if (items.length === 0) {
        setImportStatus("No valid memories found in file.");
        return;
      }
      const result = await importMemories(items);
      setImportStatus(`Imported ${result.imported}, skipped ${result.skipped}.`);
    } catch {
      setImportStatus("Import failed — check the file format.");
    } finally {
      setImporting(false);
    }
  };

  const themes: { key: "light" | "dark" | "system"; label: string }[] = [
    { key: "light", label: "Light" },
    { key: "dark", label: "Dark" },
    { key: "system", label: "System" },
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
                  {t.label}
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
                onClick={() => { setOpen(false); router.push("/library"); }}
              >
                Memory Library
              </button>
            </li>
            <li>
              <button
                role="menuitem"
                className="w-full text-left px-3 py-2 rounded-lg font-body-md text-body-md text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
                onClick={handleExport}
              >
                Export my data
              </button>
            </li>
            <li>
              <button
                role="menuitem"
                disabled={importing}
                className="w-full text-left px-3 py-2 rounded-lg font-body-md text-body-md text-on-surface hover:bg-surface-container transition-colors cursor-pointer disabled:opacity-50"
                onClick={() => fileInputRef.current?.click()}
              >
                {importing ? "Importing…" : "Import memories"}
              </button>
            </li>
          </ul>

          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            className="hidden"
            onChange={handleImportFile}
          />

          {importStatus && (
            <p className="px-3 pb-1 font-metadata text-metadata text-secondary">
              {importStatus}
            </p>
          )}

          <div className="my-1 border-t border-outline-variant/30" />

          {/* About */}
          <div className="px-3 py-2">
            <p className="font-metadata text-metadata text-outline">Memex v0.21</p>
            <p className="font-metadata text-metadata text-outline-variant mt-0.5">
              Your memories are stored in Supabase (EU region). AI responses are processed by Google Gemini — on the free tier, prompts may be used to improve Google's models. No data is shared with third parties beyond Supabase and Google.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
