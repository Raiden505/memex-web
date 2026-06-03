import type { AuthError } from "@supabase/supabase-js";

export function isDuplicateSignup(error: AuthError | null, data: { user?: { identities?: Array<unknown> } | null } | null): boolean {
  if (error) {
    const msg = error.message.toLowerCase();
    if (msg.includes("already registered") || msg.includes("already exists") || msg.includes("already been registered")) {
      return true;
    }
  }
  if (data?.user && (data.user.identities?.length ?? 0) === 0) {
    return true;
  }
  return false;
}

export function mapAuthError(message: string): string {
  const msg = message.toLowerCase();

  if (msg.includes("invalid login credentials") || msg.includes("invalid email or password")) {
    return "Email or password is incorrect.";
  }
  if (msg.includes("email not confirmed") || msg.includes("email not verified")) {
    return "Please confirm your email first — check your inbox.";
  }
  if (msg.includes("rate limit") || msg.includes("too many") || msg.includes("429")) {
    return "Too many attempts. Wait a minute and try again.";
  }
  if (
    msg.includes("network") ||
    msg.includes("fetch") ||
    msg.includes("timeout") ||
    msg.includes("connection") ||
    msg.includes("abort") ||
    msg.includes("failed to fetch")
  ) {
    return "Can't reach the server. Check your connection.";
  }
  if (msg.includes("password") && msg.includes("weak")) {
    return "Password is too weak. Use at least 6 characters.";
  }

  return "Something went wrong. Try again.";
}
