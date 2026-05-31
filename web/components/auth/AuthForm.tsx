"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Icon from "@/components/ui/Icon";

export default function AuthForm() {
  const router = useRouter();
  const supabase = createClient();

  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [emailError, setEmailError] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);

  const clearErrors = () => { setEmailError(""); setPasswordError(""); setNotice(""); };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearErrors();
    setLoading(true);
    try {
      if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) {
          const msg = error.message;
          if (msg.toLowerCase().includes("email") || msg.toLowerCase().includes("user")) setEmailError(msg);
          else setPasswordError(msg);
          return;
        }
        router.push("/chat"); router.refresh();
      } else {
        const { data, error } = await supabase.auth.signUp({ email, password });
        if (error) {
          if (error.message.toLowerCase().includes("email")) setEmailError(error.message);
          else setPasswordError(error.message);
          return;
        }
        if (data.session) { router.push("/chat"); router.refresh(); }
        else setNotice("Account created. Check your email to confirm it.");
      }
    } finally { setLoading(false); }
  };

  const isLogin = mode === "login";

  return (
    <main className="w-full max-w-[440px] z-10">
      <header className="text-center mb-10">
        <h1 className="tracking-tight mb-2" style={{ fontFamily: "var(--font-manrope)", fontSize: "40px", lineHeight: "48px", letterSpacing: "-0.02em", fontWeight: 700, color: "#00236f" }}>Memex</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">Cognitive clarity for your second brain.</p>
      </header>

      <div className="glass-panel rounded-xl p-8 shadow-sm">
        <div className="flex bg-surface-container p-1 rounded-lg mb-8 relative">
          <div
            className="absolute top-1 left-1 bg-surface-container-lowest rounded-md shadow-sm mode-toggle-transition"
            style={{
              width: "calc(50% - 4px)",
              height: "calc(100% - 8px)",
              transform: isLogin ? "translateX(0)" : "translateX(100%)",
            }}
          />
          <button
            type="button"
            onClick={() => { setMode("login"); clearErrors(); }}
            className="flex-1 py-2 font-label-md text-label-md relative z-10 transition-colors cursor-pointer"
            style={{ color: isLogin ? "#00236f" : "#444651" }}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => { setMode("signup"); clearErrors(); }}
            className="flex-1 py-2 font-label-md text-label-md relative z-10 transition-colors cursor-pointer"
            style={{ color: !isLogin ? "#00236f" : "#444651" }}
          >
            Signup
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          <div
            className="space-y-2 transition-all duration-300"
            style={{ display: isLogin ? "none" : "block", opacity: isLogin ? 0 : 1 }}
          >
            <label className="block font-label-md text-label-md text-on-surface-variant" htmlFor="full-name">
              Full Name
            </label>
            <div className="relative">
              <Icon name="person" size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
              <input
                id="full-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="John Doe"
                className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-10 pr-4 py-3 font-body-md text-body-md focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="block font-label-md text-label-md text-on-surface-variant" htmlFor="email">
              Email address
            </label>
            <div className="relative">
              <Icon name="mail" size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setEmailError(""); }}
                required
                placeholder="name@domain.com"
                className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-10 pr-4 py-3 font-body-md text-body-md focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
              />
            </div>
            {emailError && <p className="text-xs text-error">{emailError}</p>}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <label className="block font-label-md text-label-md text-on-surface-variant" htmlFor="password">
                Password
              </label>
              {isLogin && (
                <a className="text-metadata font-metadata text-primary hover:underline cursor-pointer">
                  Forgot?
                </a>
              )}
            </div>
            <div className="relative">
              <Icon name="lock" size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setPasswordError(""); }}
                required
                minLength={6}
                placeholder="••••••••"
                className="w-full bg-surface-container-lowest border border-outline-variant rounded-lg pl-10 pr-12 py-3 font-body-md text-body-md focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none transition-all"
              />
              <button type="button" className="absolute right-3 top-1/2 -translate-y-1/2 text-outline hover:text-primary transition-colors cursor-pointer">
                <Icon name="visibility" size={20} />
              </button>
            </div>
            {passwordError && <p className="text-xs text-error">{passwordError}</p>}
          </div>

          {notice && <p className="text-xs text-on-surface-variant font-metadata">{notice}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-on-primary font-label-md text-label-md py-4 rounded-lg hover:opacity-90 active:scale-[0.98] transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-70"
          >
            {loading ? (
              <Icon name="progress_activity" size={20} />
            ) : (
              <>
                <span>{isLogin ? "Continue to Memex" : "Create free account"}</span>
                <Icon name="arrow_forward" size={20} />
              </>
            )}
          </button>
        </form>
      </div>
    </main>
  );
}
