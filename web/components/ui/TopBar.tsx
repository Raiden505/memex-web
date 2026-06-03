"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import Icon from "@/components/ui/Icon";
import SettingsMenu from "@/components/ui/SettingsMenu";

export default function TopBar() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null);
    });
  }, []);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/auth";
  };

  return (
    <header className="fixed top-0 w-full z-50 bg-surface/70 glass-header border-b-[0.5px] border-outline-variant/30">
      <div className="flex justify-between items-center h-16 px-6 max-w-[800px] mx-auto">
        <div className="flex items-center gap-2 select-none">
          <h1 className="font-headline-md text-headline-md font-bold tracking-tight text-primary">
            Memex
          </h1>
          <Icon name="auto_awesome" size={16} className="text-tertiary" />
        </div>
        <div className="flex items-center gap-1">
          <SettingsMenu email={email} />
          <button
            onClick={handleSignOut}
            className="p-2 text-on-surface-variant hover:opacity-80 transition-opacity active:scale-95 duration-200 cursor-pointer"
            aria-label="Sign out"
          >
            <Icon name="logout" size={24} />
          </button>
        </div>
      </div>
    </header>
  );
}
