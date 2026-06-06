"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { flushSync } from "react-dom";
import type { ForgetCandidate, Message } from "@/types";
import ChatLayout from "@/components/chat/ChatLayout";
import MessageList from "@/components/chat/MessageList";
import ChatInput, { type ChatInputHandle } from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import ForgetConfirm from "@/components/chat/ForgetConfirm";
import SplashTransition from "@/components/ui/SplashTransition";
import CommandPalette from "@/components/ui/CommandPalette";
import { postChat, postChatStream, createMemory } from "@/lib/api";

const SAVE_ACKS = ["Got it — saved.", "Noted.", "Locked in.", "Saved that.", "Filed away.", "Remembered."];

interface PendingForget {
  loadingId: string;
  candidates: ForgetCandidate[];
  originalMsg: string;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [captureMode, setCaptureMode] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [pendingForget, setPendingForget] = useState<PendingForget | null>(null);
  const inputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    const t = setTimeout(() => setBooting(false), 600);
    return () => clearTimeout(t);
  }, []);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName ?? "";
      const inInput = tag === "INPUT" || tag === "TEXTAREA" || (e.target as HTMLElement)?.isContentEditable;

      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
        return;
      }

      if (!inInput && e.key === "c" && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        handleCapture();
        return;
      }

      if (e.key === "Escape" && captureMode) {
        setCaptureMode(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [captureMode]);

  const handleCapture = useCallback(() => {
    setCaptureMode(true);
    setPaletteOpen(false);
    setTimeout(() => inputRef.current?.focus(), 10);
  }, []);

  const sendText = useCallback(async (rawText: string, opts?: { mode?: string }) => {
    const text = rawText.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);
    setPendingForget(null);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      date: new Date(),
    };
    const loadingId = crypto.randomUUID();
    const loadingMsg: Message = {
      id: loadingId,
      role: "assistant",
      content: "",
      date: new Date(),
      pending: true,
    };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    const replaceLoading = (content: string, isError?: boolean) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingId ? { ...m, content, isError, pending: false } : m))
      );
    };

    // Quick capture: always store, no routing
    if (captureMode) {
      try {
        await createMemory(text);
        replaceLoading(SAVE_ACKS[Math.floor(Math.random() * SAVE_ACKS.length)]);
      } catch {
        replaceLoading("Couldn't save — try again.", true);
      } finally {
        setLoading(false);
        if (matchMedia("(pointer: fine)").matches) inputRef.current?.focus();
      }
      return;
    }

    try {
      let captured: ForgetCandidate[] | null = null;

      const streamOpts = opts?.mode ? { mode: opts.mode } : {};
      const stream = postChatStream(text, 1, (candidates) => {
        captured = candidates;
      }, streamOpts);
      let first = true;

      for await (const token of stream) {
        if (first) {
          flushSync(() => replaceLoading(token));
          first = false;
        } else {
          flushSync(() => {
            setMessages((prev) =>
              prev.map((m) => (m.id === loadingId ? { ...m, content: m.content + token } : m))
            );
          });
        }
      }

      if (captured && (captured as ForgetCandidate[]).length > 0) {
        setPendingForget({ loadingId, candidates: captured, originalMsg: text });
      }
    } catch (err) {
      console.error("[stream] fallback:", err);
      try {
        const res = await postChat(text, opts?.mode ? { mode: opts.mode } : {});
        replaceLoading(res.reply);
        if (res.forget_candidates && res.forget_candidates.length > 0) {
          setPendingForget({ loadingId, candidates: res.forget_candidates, originalMsg: text });
        }
      } catch {
        replaceLoading("Couldn't reach memory — try again.", true);
      }
    } finally {
      setLoading(false);
      if (matchMedia("(pointer: fine)").matches) {
        inputRef.current?.focus();
      }
    }
  }, [loading, captureMode]);

  const handleSend = useCallback(() => {
    void sendText(input);
  }, [input, sendText]);

  const handleSuggestion = useCallback(
    (text: string) => {
      void sendText(text);
    },
    [sendText]
  );

  // Memory deep-dive: a grounded, semantic-only lookup of one specific memory.
  const handleAskMemory = useCallback(
    (content: string) => {
      void sendText(`Tell me about: ${content}`, { mode: "recall" });
    },
    [sendText]
  );

  const handleForgetConfirm = useCallback(
    async (ids: string[]) => {
      if (!pendingForget) return;
      const { loadingId, originalMsg } = pendingForget;
      setPendingForget(null);
      setLoading(true);

      try {
        const res = await postChat(originalMsg, { confirmForget: ids });
        setMessages((prev) =>
          prev.map((m) => (m.id === loadingId ? { ...m, content: res.reply, pending: false } : m))
        );
      } catch {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === loadingId
              ? { ...m, content: "Couldn't complete the deletion — try again.", isError: true, pending: false }
              : m
          )
        );
      } finally {
        setLoading(false);
        if (matchMedia("(pointer: fine)").matches) inputRef.current?.focus();
      }
    },
    [pendingForget]
  );

  const handleForgetCancel = useCallback(() => {
    if (!pendingForget) return;
    const { loadingId } = pendingForget;
    setPendingForget(null);
    setMessages((prev) =>
      prev.map((m) => (m.id === loadingId ? { ...m, content: m.content + "\n\nOkay, kept them." } : m))
    );
    if (matchMedia("(pointer: fine)").matches) inputRef.current?.focus();
  }, [pendingForget]);

  return (
    <ChatLayout onCapture={handleCapture}>
      {booting ? (
        <SplashTransition />
      ) : messages.length === 0 ? (
        <EmptyState onSuggestion={handleSuggestion} onAskMemory={handleAskMemory} />
      ) : (
        <MessageList messages={messages} />
      )}
      {pendingForget && (
        <div className="fixed bottom-32 sm:bottom-36 left-0 right-0 z-[60] px-6">
          <div className="max-w-[800px] mx-auto">
            <ForgetConfirm
              candidates={pendingForget.candidates}
              onConfirm={handleForgetConfirm}
              onCancel={handleForgetCancel}
            />
          </div>
        </div>
      )}
      <ChatInput
        ref={inputRef}
        value={input}
        onChange={setInput}
        onSend={handleSend}
        loading={loading}
        captureMode={captureMode}
        onExitCapture={() => setCaptureMode(false)}
      />
      <CommandPalette
        open={paletteOpen}
        onClose={() => setPaletteOpen(false)}
        onCapture={handleCapture}
        onDigest={() => handleSuggestion("What did I save today?")}
      />
    </ChatLayout>
  );
}
