"use client";

import TopBar from "@/components/ui/TopBar";

export default function ChatLayout({
  children,
  onCapture,
}: {
  children: React.ReactNode;
  onCapture?: () => void;
}) {
  return (
    <div className="h-dvh flex flex-col bg-background text-on-surface font-body-md">
      <TopBar onCapture={onCapture} />
      {children}
    </div>
  );
}
