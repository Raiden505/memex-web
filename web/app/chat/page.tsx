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
import { postChat, postChatStream } from "@/lib/api";

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
  const [pendingForget, setPendingForget] = useState<PendingForget | null>(null);
  const inputRef = useRef<ChatInputHandle>(null);

  useEffect(() => {
    const t = setTimeout(() => setBooting(false), 600);
    return () => clearTimeout(t);
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
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

    try {
      let captured: ForgetCandidate[] | null = null;

      const stream = postChatStream(text, 1, (candidates) => {
        captured = candidates;
      });
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
        const res = await postChat(text);
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
  }, [input, loading]);

  const handleSuggestion = useCallback(
    (text: string) => {
      setInput(text);
      setTimeout(() => {
        inputRef.current?.focus();
        handleSend();
      }, 0);
    },
    [handleSend]
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
    <ChatLayout>
      {booting ? (
        <SplashTransition />
      ) : messages.length === 0 ? (
        <EmptyState onSuggestion={handleSuggestion} />
      ) : (
        <MessageList messages={messages} />
      )}
      {pendingForget && (
        <div className="fixed bottom-24 left-0 right-0 z-10 px-6">
          <div className="max-w-[800px] mx-auto">
            <ForgetConfirm
              candidates={pendingForget.candidates}
              onConfirm={handleForgetConfirm}
              onCancel={handleForgetCancel}
            />
          </div>
        </div>
      )}
      <ChatInput ref={inputRef} value={input} onChange={setInput} onSend={handleSend} loading={loading} />
    </ChatLayout>
  );
}
