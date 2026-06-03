"use client";

import { useRef, useEffect } from "react";
import type { Message } from "@/types";
import MessageBubble from "./MessageBubble";
import DateDivider from "./DateDivider";

function formatDate(date: Date): string {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const d = new Date(date);
  const msgDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());

  if (msgDay.getTime() === today.getTime()) return "Today";
  if (msgDay.getTime() === yesterday.getTime()) return "Yesterday";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

function groupByDate(messages: Message[]) {
  const groups: { label: string; messages: Message[] }[] = [];
  let currentLabel = "";
  for (const msg of messages) {
    const label = formatDate(msg.date);
    if (label !== currentLabel) {
      currentLabel = label;
      groups.push({ label, messages: [] });
    }
    groups[groups.length - 1].messages.push(msg);
  }
  return groups;
}

export default function MessageList({ messages }: { messages: Message[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const groups = groupByDate(messages);

  return (
    <div className="flex-1 overflow-y-auto pb-28">
      <div
        className="px-6 flex flex-col mx-auto"
        style={{ maxWidth: "800px", gap: "12px", paddingTop: "96px" }}
      >
        {groups.map((group, gi) => (
          <div key={gi} className="flex flex-col gap-3">
            <DateDivider label={group.label} />
            {group.messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                role={msg.role}
                content={msg.content}
                isError={msg.isError}
                pending={msg.pending}
              />
            ))}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
