"use client";

import { useState, useCallback, useRef } from "react";
import type { Message } from "@/types";
import ChatLayout from "@/components/chat/ChatLayout";
import MessageList from "@/components/chat/MessageList";
import ChatInput, { type ChatInputHandle } from "@/components/chat/ChatInput";
import EmptyState from "@/components/chat/EmptyState";
import { postChat, postChatStream } from "@/lib/api";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<ChatInputHandle>(null);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;

    setInput("");
    setLoading(true);

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: text, date: new Date() };
    const loadingId = crypto.randomUUID();
    const loadingMsg: Message = { id: loadingId, role: "assistant", content: "Retrieving memories...", date: new Date() };

    setMessages((prev) => [...prev, userMsg, loadingMsg]);

    const replaceLoading = (content: string, isError?: boolean) => {
      setMessages((prev) =>
        prev.map((m) => (m.id === loadingId ? { ...m, content, isError } : m))
      );
    };

    try {
      const stream = postChatStream(text, 1);
      let first = true;

      for await (const token of stream) {
        if (first) {
          replaceLoading(token);
          first = false;
        } else {
          setMessages((prev) =>
            prev.map((m) => (m.id === loadingId ? { ...m, content: m.content + token } : m))
          );
        }
      }
    } catch {
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
      {messages.length === 0 ? <EmptyState /> : <MessageList messages={messages} />}
      <ChatInput ref={inputRef} value={input} onChange={setInput} onSend={handleSend} loading={loading} />
    </ChatLayout>
  );
}
