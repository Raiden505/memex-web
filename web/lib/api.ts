import type { Message } from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  const { createBrowserClient } = await import("@supabase/ssr");
  const supabase = createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

async function fetchApi<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = await getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed with status ${res.status}`);
  }
  return res.json();
}

export async function getMemories(): Promise<Message[]> {
  const data: { id: string; content: string; created_at: string }[] =
    await fetchApi("/memories");
  return data.map((m) => ({
    id: m.id,
    role: "user" as const,
    content: m.content,
    date: new Date(m.created_at),
  }));
}

export async function postChat(
  message: string
): Promise<{ intent: string; reply: string; id: string | null; source: string | null }> {
  return fetchApi("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
    }),
  });
}

export async function* postChatStream(
  message: string,
  retries = 1
): AsyncGenerator<string, void, unknown> {
  const token = await getToken();

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const res = await fetch(`${API_URL}/chat?stream=true`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          message,
          tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
        }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || `Request failed with status ${res.status}`);
      }

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const line = event.trim();
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6);

          try {
            const obj = JSON.parse(raw);
            if (obj.done) return;
            if (obj.error) {
              console.error("[stream] server error:", obj.error);
              throw new Error(obj.error);
            }
            if (obj.t !== undefined) {
              yield obj.t;
              await new Promise<void>((r) => setTimeout(r, 0));
            }
          } catch (err) {
            if (err instanceof SyntaxError) continue;
            throw err;
          }
        }
      }
      return;
    } catch (err) {
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
}
