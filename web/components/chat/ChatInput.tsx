"use client";

import { useRef, useEffect } from "react";
import Icon from "@/components/ui/Icon";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export default function ChatInput({ value, onChange, onSend, disabled }: ChatInputProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !disabled) onSend();
    }
  };

  useEffect(() => { inputRef.current?.focus(); }, []);

  const hasText = value.trim().length > 0;

  return (
    <div className="fixed bottom-0 w-full bg-gradient-to-t from-background via-background to-transparent pb-8 pt-12 z-50">
      <div className="max-w-[800px] mx-auto px-6">
        <div className="input-pill bg-surface border border-outline-variant/50 rounded-full flex items-center p-2 gap-2 focus-within:ring-2 focus-within:ring-primary/10 transition-all">
          <input
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Recall a memory or ask a question..."
            disabled={disabled}
            className="flex-1 bg-transparent border-none focus:ring-0 font-body-md text-on-surface placeholder:text-outline/70 outline-none pl-2"
          />
          <button
            onClick={() => { if (hasText && !disabled) onSend(); }}
            disabled={!hasText || disabled}
            className="p-3 bg-primary text-on-primary rounded-full transition-all active:scale-90 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
          >
            <Icon name="send" size={20} />
          </button>
        </div>
      </div>
    </div>
  );
}
