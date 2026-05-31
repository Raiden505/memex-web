import type { Role } from "@/types";
import Icon from "@/components/ui/Icon";

interface MessageBubbleProps {
  role: Role;
  content: string;
  isError?: boolean;
}

function fmt(date: Date) {
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export default function MessageBubble({ role, content, isError }: MessageBubbleProps) {
  const now = new Date();

  if (role === "user") {
    return (
      <div className="flex flex-col gap-2 max-w-[85%] self-end items-end message-enter">
        <div className="bg-primary text-on-primary p-4 rounded-2xl rounded-tr-none shadow-[0px_2px_4px_rgba(0,0,0,0.05)]">
          <p className="font-body-md text-body-md leading-relaxed">{content}</p>
        </div>
        <div className="flex items-center gap-1 ml-auto mr-1">
          <span className="font-metadata text-metadata text-outline">{fmt(now)}</span>
          <Icon name="check_circle" size={14} className="text-secondary" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2 max-w-[85%] message-enter">
      <div className="flex items-center gap-2 mb-1">
        <div className="w-6 h-6 rounded-lg bg-tertiary-container flex items-center justify-center">
          <Icon name="auto_awesome" size={14} className="text-on-tertiary-container" />
        </div>
        <span className="font-metadata text-metadata text-on-surface-variant">Memex AI</span>
      </div>
      <div className="ai-glow bg-white border border-outline-variant/50 p-4 rounded-2xl rounded-tl-none">
        <p
          className={`font-body-md text-body-md leading-relaxed ${isError ? "text-error" : "text-on-surface"}`}
        >
          {content}
        </p>
      </div>
      <span className="font-metadata text-metadata text-outline ml-1">{fmt(now)}</span>
    </div>
  );
}
