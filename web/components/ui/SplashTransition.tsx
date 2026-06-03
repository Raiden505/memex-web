import Icon from "@/components/ui/Icon";

export default function SplashTransition() {
  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <h1
          className="tracking-tight"
          style={{ fontFamily: "var(--font-manrope)", fontSize: "32px", lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: 600, color: "var(--color-primary)" }}
        >
          Memex
        </h1>
        <Icon name="psychology" size={28} className="text-outline" />
        <div className="w-32 h-1 bg-surface-container rounded-full overflow-hidden">
          <div className="h-full bg-primary-fixed-dim rounded-full" style={{ animation: "splash-progress 1.2s ease-in-out infinite", width: "60%" }} />
        </div>
        <style>{`@keyframes splash-progress { 0% { transform: translateX(-100%); } 100% { transform: translateX(200%); } }`}</style>
      </div>
    </div>
  );
}
