"use client";

import { useRef, useEffect, forwardRef, useImperativeHandle } from "react";
import Icon from "@/components/ui/Icon";

export interface ChatInputHandle {
  focus: () => void;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  loading?: boolean;
}

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  function ChatInput({ value, onChange, onSend, loading = false }, ref) {
    const inputRef = useRef<HTMLInputElement>(null);

    useImperativeHandle(ref, () => ({
      focus: () => inputRef.current?.focus(),
    }));

    const handleKeyDown = (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!loading && value.trim()) onSend();
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
              className="flex-1 bg-transparent border-none focus:ring-0 font-body-md text-on-surface placeholder:text-outline/70 outline-none pl-2"
            />
            <button
              onClick={() => { if (hasText && !loading) onSend(); }}
              disabled={!hasText || loading}
              className="p-3 bg-primary text-on-primary rounded-full transition-all active:scale-90 disabled:cursor-not-allowed disabled:opacity-40 cursor-pointer"
            >
              <Icon name="send" size={20} />
            </button>
          </div>
        </div>
      </div>
    );
  }
);

export default ChatInput;
