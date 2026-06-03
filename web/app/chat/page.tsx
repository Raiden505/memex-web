"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { flushSync } from "react-dom";
import type { Message } from "@/types";
import ChatLayout from "@/components/chat/ChatLayout";
import MessageList from "@/components/chat/MessageList";
import ChatInput, { type ChatInputHandle } from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import SplashTransition from "@/components/ui/SplashTransition";
import { postChat, postChatStream } from "@/lib/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const inputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    const timeout = setTimeout(() => setBooting(false), 600);
    return () => clearTimeout(timeout);
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: text, date: new Date() };
    const loadingId = crypto.randomUUID();
    const loadingMsg: Message = { id: loadingId, role: "assistant", content: "", date: new Date(), pending: true };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    const replaceLoading = (content: string, isError?: boolean) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingId ? { ...m, content, isError, pending: false } : m))
      );
    };

    try {
      const stream = postChatStream(text, 1);
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
    } catch (streamErr) {
      console.error("[stream] fell back to non-streaming:", streamErr);
      try {
        const res = await postChat(text);
        replaceLoading(res.reply);
      } catch {
        replaceLoading("Couldn't reach memory — try again.", true);
      }
    } finally {
      setLoading(false);
      if (matchMedia("(pointer: fine)").matches) {
        inputRef.current?.focus();
      }
    }
  }, [input, loading]);

  return (
    <ChatLayout>
      {booting ? (
        <SplashTransition />
      ) : messages.length === 0 ? (
        <EmptyState />
      ) : (
        <MessageList messages={messages} />
      )}
      <ChatInput ref={inputRef} value={input} onChange={setInput} onSend={handleSend} loading={loading} />
    </ChatLayout>
  );
}
