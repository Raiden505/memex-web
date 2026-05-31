import TopBar from "@/components/ui/TopBar";

export default function ChatLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-dvh flex flex-col bg-background text-on-surface font-body-md">
      <TopBar />
      {children}
    </div>
  );
}
