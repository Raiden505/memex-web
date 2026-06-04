"use client";

import { useRef, useEffect, useState, forwardRef, useImperativeHandle } from "react";
import Icon from "@/components/ui/Icon";

export interface ChatInputHandle {
  focus: () => void;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  loading?: boolean;
  captureMode?: boolean;
  onExitCapture?: () => void;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const w = typeof window !== "undefined" ? (window as any) : null;
const voiceSupported = !!(w?.SpeechRecognition || w?.webkitSpeechRecognition);

const ChatInput = forwardRef<ChatInputHandle, ChatInputProps>(
  function ChatInput({ value, onChange, onSend, loading = false, captureMode = false, onExitCapture }, ref) {
    const inputRef = useRef<HTMLInputElement>(null);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const recognitionRef = useRef<any>(null);
    const [listening, setListening] = useState(false);

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

    const handleVoice = () => {
      if (!voiceSupported) return;

      if (listening) {
        recognitionRef.current?.stop();
        return;
      }

      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const recognition = new SR();
      recognition.continuous = false;
      recognition.interimResults = false;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      recognition.onresult = (e: any) => {
        const transcript = e.results[0][0].transcript;
        onChange(value + (value ? " " : "") + transcript);
      };
      recognition.onend = () => setListening(false);
      recognition.onerror = () => setListening(false);
      recognition.start();
      recognitionRef.current = recognition;
      setListening(true);
    };

    const hasText = value.trim().length > 0;

    return (
      <div className="fixed bottom-0 w-full bg-gradient-to-t from-background via-background to-transparent pb-8 pt-12 z-50">
        <div className="max-w-[800px] mx-auto px-6">
          <div className={`input-pill bg-surface border rounded-full flex items-center p-2 gap-2 focus-within:ring-2 focus-within:ring-primary/10 transition-all ${captureMode ? "border-primary/50" : "border-outline-variant/50"}`}>
            {captureMode && (
              <div className="flex items-center gap-1 pl-1 flex-shrink-0">
                <span className="font-label-md text-label-md text-primary text-xs px-2 py-0.5 rounded-full bg-primary/10">
                  Save
                </span>
                <button
                  type="button"
                  onClick={onExitCapture}
                  className="text-outline hover:text-on-surface transition-colors cursor-pointer"
                  aria-label="Exit capture mode"
                >
                  <Icon name="close" size={16} />
                </button>
              </div>
            )}
            <input
              ref={inputRef}
              type="text"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={captureMode ? "Quick save — press Enter..." : "Recall a memory or ask a question..."}
              className="flex-1 bg-transparent border-none focus:ring-0 font-body-md text-on-surface placeholder:text-outline/70 outline-none pl-2"
            />
            {voiceSupported && (
              <button
                type="button"
                onClick={handleVoice}
                className={`p-2 rounded-full transition-all cursor-pointer ${
                  listening
                    ? "text-error bg-error/10 animate-pulse"
                    : "text-outline hover:text-primary hover:bg-primary/10"
                }`}
                aria-label={listening ? "Stop recording" : "Voice input"}
              >
                <Icon name={listening ? "mic_off" : "mic"} size={20} />
              </button>
            )}
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
