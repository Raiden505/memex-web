"use client";

import { useState, useEffect } from "react";
import Image from "next/image";
import { createClient } from "@/lib/supabase/client";
import RecentMemories from "./RecentMemories";

const CHIPS = [
  "Remember something for me",
  "What did I save today?",
  "What can you do?",
  "Show my recent notes",
];

interface EmptyStateProps {
  onSuggestion: (text: string) => void;
  onAskMemory: (content: string) => void;
}

export default function EmptyState({ onSuggestion, onAskMemory }: EmptyStateProps) {
  const [firstName, setFirstName] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      const full = data.user?.user_metadata?.full_name;
      if (full) setFirstName(full.split(" ")[0]);
    });
  }, []);

  return (
    <div className="flex-1 overflow-y-auto pb-28">
      <div
        className="px-6 flex flex-col mx-auto"
        style={{ maxWidth: "800px", gap: "12px", paddingTop: "96px" }}
      >
        <div className="flex flex-col items-center text-center select-none pt-8 pb-6">
          <div className="mb-5">
            <Image src="/icon.png" alt="Memex" width={56} height={56} className="rounded-2xl elevation-1" />
          </div>
          <h2 className="font-headline-md text-headline-md text-on-surface mb-2">
            {firstName ? `Welcome back, ${firstName}.` : "Welcome back."}
          </h2>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-md mb-6">
            Your extended cognitive field. Save memories, recall them naturally, and let Memex do the remembering.
          </p>
          <div className="flex flex-wrap justify-center gap-2 max-w-lg">
            {CHIPS.map((text) => (
              <button
                key={text}
                onClick={() => onSuggestion(text)}
                className="rounded-full border border-outline-variant/50 bg-surface-container-low px-4 py-2 font-label-md text-label-md text-on-surface-variant hover:bg-surface-container hover:border-outline transition-colors active:scale-95 duration-150"
              >
                {text}
              </button>
            ))}
          </div>
        </div>
        <RecentMemories onAskMemory={onAskMemory} />
      </div>
    </div>
  );
}
