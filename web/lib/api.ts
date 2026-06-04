import type { ForgetCandidate, Memory, MemoryMetadata, Message } from "@/types";

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

export async function createMemory(content: string): Promise<{ id: string; created_at: string }> {
  return fetchApi("/memories", {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export async function getMemories(): Promise<Message[]> {
  const data: { id: string; content: string; created_at: string; metadata?: MemoryMetadata | null }[] =
    await fetchApi("/memories");
  return data.map((m) => ({
    id: m.id,
    role: "user" as const,
    content: m.content,
    date: new Date(m.created_at),
    metadata: m.metadata,
  }));
}

export async function exportMemories(): Promise<{ content: string; created_at: string; metadata?: MemoryMetadata | null }[]> {
  return fetchApi("/memories/export");
}

export async function importMemories(
  items: { content: string }[]
): Promise<{ imported: number; skipped: number }> {
  return fetchApi("/memories/import", {
    method: "POST",
    body: JSON.stringify({ items }),
  });
}

export async function getStats(): Promise<{
  total: number;
  added_last_30d: number;
  top_tags: { tag: string; count: number }[];
}> {
  return fetchApi("/memories/stats");
}

export async function getDueMemories(): Promise<Memory[]> {
  const data: { id: string; content: string; created_at: string; metadata?: MemoryMetadata | null }[] =
    await fetchApi("/memories/due");
  return data;
}

export async function getMemoryCount(): Promise<number> {
  const data: { total: number } = await fetchApi("/memories/count");
  return data.total;
}

export async function updateMemory(id: string, content: string): Promise<{ id: string; updated: boolean }> {
  return fetchApi(`/memories/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ content }),
  });
}

export async function deleteMemory(id: string): Promise<{ deleted: boolean }> {
  return fetchApi(`/memories/${id}`, { method: "DELETE" });
}

export async function setPinned(id: string, pinned: boolean): Promise<{ id: string; pinned: boolean }> {
  return fetchApi(`/memories/${id}/pin`, {
    method: "POST",
    body: JSON.stringify({ pinned }),
  });
}

export async function postChat(
  message: string,
  opts: { confirmForget?: string[] } = {}
): Promise<{ intent: string; reply: string; id: string | null; source: string | null; forget_candidates?: ForgetCandidate[] }> {
  return fetchApi("/chat", {
    method: "POST",
    body: JSON.stringify({
      message,
      tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      ...(opts.confirmForget !== undefined ? { confirm_forget: opts.confirmForget } : {}),
    }),
  });
}

export async function* postChatStream(
  message: string,
  retries = 1,
  onForgetCandidates?: (candidates: ForgetCandidate[]) => void
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
            if (obj.fc && onForgetCandidates) {
              onForgetCandidates(obj.fc as ForgetCandidate[]);
              continue;
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
