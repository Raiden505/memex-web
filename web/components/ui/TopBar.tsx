"use client";

import { createClient } from "@/lib/supabase/client";
import Icon from "@/components/ui/Icon";

export default function TopBar() {
  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    window.location.href = "/auth";
  };

  return (
    <header className="fixed top-0 w-full z-50 bg-surface/70 glass-header border-b-[0.5px] border-outline-variant/30">
      <div className="flex justify-between items-center h-16 px-6 max-w-[800px] mx-auto">
        <h1 className="font-headline-md text-headline-md font-bold tracking-tight text-primary select-none">
          Memex
        </h1>
        <button
          onClick={handleSignOut}
          className="p-2 text-on-surface-variant hover:opacity-80 transition-opacity active:scale-95 duration-200 cursor-pointer"
          aria-label="Sign out"
        >
          <Icon name="logout" size={24} />
        </button>
      </div>
    </header>
  );
}
