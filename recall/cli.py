import re as _re
import sys
from datetime import datetime

from supabase import Client
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from recall.config import Config, ConfigError, load_config
from recall import auth, embeddings, llm, router, store, temporal

_FORGET_ALL_RE = _re.compile(
    r"\bforget\s+(everything|all(\s+my)?\s+memories?|it\s+all)\b", _re.IGNORECASE
)
_FORGET_VERB_RE = _re.compile(
    r"^(forget|delete|remove)\s+"
    r"(what\s+i\s+(said|saved|told\s+(you\s+)?)(\s*about\s+)?"
    r"|the\s+memory\s+(of\s+|about\s+)?)?",
    _re.IGNORECASE,
)
_FORGET_BULK_RE = _re.compile(r"\b(everything|all|every|each)\b", _re.IGNORECASE)

# Quick win: semantic duplicate threshold (same as API).
_DUPLICATE_THRESHOLD = 0.95

console = Console()


def _show_help() -> None:
    help_text = """[bold]/add <text>[/bold]     Force-store text as a memory
[bold]/ask <text>[/bold]     Force-treat text as a question
[bold]/search <text>[/bold]  Show raw matching memories (no AI answer)
[bold]/list[/bold]           Show all stored memories with their ids
[bold]/forget <id>[/bold]    Delete a memory by id
[bold]/count[/bold]          How many memories are stored
[bold]/logout[/bold]         Sign out and exit
[bold]/help[/bold]           Show this help
[bold]/quit[/bold]           Exit

[dim]Or just type naturally — statements are stored, questions are answered automatically.[/dim]"""
    console.print(Panel(help_text, title="Commands", border_style="cyan"))


def _do_store(text: str, cfg: Config, client: Client, force: bool = False) -> dict | None:
    with console.status("[cyan]Saving...[/cyan]"):
        embedding = embeddings.embed(text, cfg, task_type="RETRIEVAL_DOCUMENT")
        if not force:
            results = store.search_memories(client, embedding, cfg.user_id, k=1)
            if results and results[0].similarity >= _DUPLICATE_THRESHOLD:
                dup = results[0]
                console.print(
                    f"[yellow]That looks very similar to something you saved on {dup.created_at[:10]}:[/yellow]"
                )
                console.print(f"[dim]{dup.content}[/dim]")
                try:
                    confirm = input("Save anyway? [y/N] ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]Cancelled.[/dim]")
                    return None
                if confirm != "y":
                    console.print("[dim]Kept the original.[/dim]")
                    return None
        due = temporal.extract_due(text)
        initial_meta = {"due": due.isoformat()} if due else None
        row = store.add_memory(client, text, embedding, cfg.user_id, metadata=initial_meta)
    console.print(f"[green]{llm.save_ack()}[/green] [dim](id: {row['id']})[/dim]")
    try:
        tags = llm.tag_memory(text, cfg)
        if tags:
            store.update_metadata(client, row["id"], cfg.user_id, {"tags": tags})
    except Exception:
        pass
    return row


def _do_query(text: str, cfg: Config, client: Client) -> str:
    now = datetime.now().astimezone()

    due_rng = temporal.extract_due_range(text, now=now)
    if due_rng:
        start, end, label = due_rng
        with console.status(f"[cyan]Checking what's due {label}...[/cyan]"):
            mems = store.list_due_in_range(client, cfg.user_id, start, end)
            answer = llm.summarize_due_window(mems, label, cfg)
        console.print(f"[bold]bot \u203a[/bold] {answer}")
        return answer

    rng = temporal.extract_range(text, now=now)
    if rng:
        start, end, label = rng
        with console.status(f"[cyan]Scanning {label}...[/cyan]"):
            mems = store.list_memories_in_range(client, cfg.user_id, start, end)
            answer = llm.summarize_window(mems, label, cfg)
        console.print(f"[bold]bot \u203a[/bold] {answer}")
        return answer

    with console.status("[cyan]Thinking...[/cyan]"):
        embedding = embeddings.embed(text, cfg, task_type="RETRIEVAL_QUERY")
        results = store.search_memories(client, embedding, cfg.user_id, cfg.top_k)
        answer = llm.synthesize_answer(text, results, cfg)
    console.print(f"[bold]bot \u203a[/bold] {answer}")
    return answer


def _do_forget_natural(text: str, cfg: Config, client: Client) -> None:
    if _FORGET_ALL_RE.search(text):
        candidates = store.list_memories(client, cfg.user_id)
    elif _FORGET_BULK_RE.search(text) and (rng := temporal.extract_range(text, now=datetime.now().astimezone())):
        # Bulk delete by date only when the user explicitly says "everything/all".
        start, end, _ = rng
        candidates = store.list_memories_in_range(client, cfg.user_id, start, end)
    else:
        # Default: the single best-matching memory.
        target = _FORGET_VERB_RE.sub("", text).strip() or text
        with console.status("[cyan]Searching...[/cyan]"):
            emb = embeddings.embed(target, cfg, task_type="RETRIEVAL_QUERY")
            results = store.search_memories(client, emb, cfg.user_id, cfg.top_k)
        candidates = [results[0]] if results and results[0].similarity >= 0.6 else []

    if not candidates:
        console.print("[dim]I don't have anything saved about that.[/dim]")
        return

    n = len(candidates)
    console.print(f"[yellow]Found {n} {'memory' if n == 1 else 'memories'}:[/yellow]")
    table = Table(box=box.ROUNDED)
    table.add_column("Date", style="cyan")
    table.add_column("Content")
    for m in candidates:
        table.add_row(m.created_at[:10], m.content)
    console.print(table)

    try:
        confirm = input(f"Delete {'it' if n == 1 else 'them'}? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[dim]Cancelled.[/dim]")
        return

    if confirm != "y":
        console.print("[dim]Kept.[/dim]")
        return

    deleted = store.delete_memories(client, [m.id for m in candidates], cfg.user_id)
    console.print(f"[green]Forgotten — removed {deleted}.[/green]")


def _dispatch(line: str, cfg: Config, client: Client, history: list[dict]) -> bool:
    line = line.strip()
    if not line:
        return True

    if not line.startswith("/"):
        try:
            intent = router.route(line, cfg, history=history)
            if intent == "store":
                row = _do_store(line, cfg, client)
                if row:
                    history.append({"role": "user", "content": line})
                    history.append({"role": "assistant", "content": llm.save_ack()})
            elif intent == "general":
                with console.status("[cyan]Thinking...[/cyan]"):
                    reply = llm.chat_general(line, cfg)
                console.print(f"[bold]bot \u203a[/bold] {reply}")
                history.append({"role": "user", "content": line})
                history.append({"role": "assistant", "content": reply})
            elif intent == "forget":
                _do_forget_natural(line, cfg, client)
                # Forget is an interactive two-step dialog; don't append
                # assistant turns that would break follow-up routing.
            else:
                answer = _do_query(line, cfg, client)
                history.append({"role": "user", "content": line})
                history.append({"role": "assistant", "content": answer})
        except Exception as exc:
            console.print(f"[red]Error:[/red] {exc}")
        return True

    parts = line.split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1].strip() if len(parts) > 1 else ""

    if cmd == "/quit":
        console.print("[dim]Goodbye.[/dim]")
        return False

    if cmd == "/logout":
        auth.sign_out(client)
        console.print("[dim]Signed out. Goodbye.[/dim]")
        return False

    if cmd == "/help":
        _show_help()
        return True

    if cmd == "/add":
        if not arg:
            console.print("[dim]Usage: /add <text>[/dim]")
            return True
        try:
            _do_store(arg, cfg, client, force=True)
        except Exception as exc:
            console.print(f"[red]Error saving memory:[/red] {exc}")
        return True

    if cmd == "/ask":
        if not arg:
            console.print("[dim]Usage: /ask <question>[/dim]")
            return True
        try:
            answer = _do_query(arg, cfg, client)
            history.append({"role": "user", "content": arg})
            history.append({"role": "assistant", "content": answer})
        except Exception as exc:
            console.print(f"[red]Error answering question:[/red] {exc}")
        return True

    if cmd == "/search":
        if not arg:
            console.print("[dim]Usage: /search <text>[/dim]")
            return True
        try:
            with console.status("[cyan]Searching...[/cyan]"):
                embedding = embeddings.embed(arg, cfg, task_type="RETRIEVAL_QUERY")
                results = store.search_memories(client, embedding, cfg.user_id, cfg.top_k)
            if not results:
                console.print("[dim]No matching memories found.[/dim]")
            else:
                table = Table(box=box.ROUNDED)
                table.add_column("Score", style="cyan", justify="right")
                table.add_column("Date", style="cyan")
                table.add_column("Content")
                for r in results:
                    table.add_row(f"{r.similarity:.2f}", r.created_at[:10], r.content)
                console.print(table)
        except Exception as exc:
            console.print(f"[red]Error searching memories:[/red] {exc}")
        return True

    if cmd == "/list":
        try:
            memories = store.list_memories(client, cfg.user_id)
            if not memories:
                console.print("[dim]No memories stored yet.[/dim]")
            else:
                table = Table(box=box.ROUNDED)
                table.add_column("ID", style="dim", no_wrap=True)
                table.add_column("Date", style="cyan")
                table.add_column("Content")
                for m in memories:
                    table.add_row(m.id, m.created_at[:10], m.content)
                console.print(table)
        except Exception as exc:
            console.print(f"[red]Error listing memories:[/red] {exc}")
        return True

    if cmd == "/count":
        try:
            n = store.count_memories(client, cfg.user_id)
            console.print(f"Memories stored: [bold cyan]{n}[/bold cyan]")
        except Exception as exc:
            console.print(f"[red]Error counting memories:[/red] {exc}")
        return True

    if cmd == "/forget":
        if not arg:
            console.print("[dim]Usage: /forget <id>[/dim]")
            return True
        try:
            deleted = store.delete_memory(client, arg, cfg.user_id)
            if deleted:
                console.print("[green]Forgotten.[/green]")
            else:
                console.print(f"[dim]No memory found with id [bold]{arg}[/bold].[/dim]")
        except Exception as exc:
            console.print(f"[red]Error deleting memory:[/red] {exc}")
        return True

    console.print(f"[dim]Unknown command: {cmd}  (type /help for a list)[/dim]")
    return True


def _auth_flow(client: Client) -> str | None:
    """Try to restore session; if not, prompt for login or sign-up.

    Returns the authenticated user_id, or None if the user quits.
    """
    # 1. Try to restore a saved session
    restored = auth.restore_session(client)
    if restored:
        user_id, email = restored
        console.print(f"[dim]Welcome back, {email}[/dim]")
        return user_id

    # 2. No saved session — prompt for login or sign-up
    console.print("[bold cyan]Welcome to Recall[/bold cyan]")
    console.print("[dim]Sign in to access your memories, or create a new account.[/dim]\n")

    while True:
        console.print("[dim]Type [bold]1[/bold] to sign in, [bold]2[/bold] to sign up, or [bold]q[/bold] to quit.[/dim]")
        try:
            choice = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None

        if choice == "q":
            return None

        if choice == "1":
            try:
                email = input("Email: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            try:
                password = input("Password: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

            if not email or not password:
                console.print("[dim]Email and password are required.[/dim]")
                continue

            try:
                with console.status("[cyan]Signing in...[/cyan]"):
                    user_id, user_email = auth.sign_in(client, email, password)
                console.print(f"[green]Signed in as {user_email}[/green]")
                return user_id
            except Exception as exc:
                msg = str(exc).lower()
                if "invalid login" in msg or "invalid" in msg:
                    console.print("[red]Invalid email or password.[/red]")
                else:
                    console.print(f"[red]Sign-in failed:[/red] {exc}")
                continue

        if choice == "2":
            try:
                email = input("Email: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            try:
                password = input("Password: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

            if not email or not password:
                console.print("[dim]Email and password are required.[/dim]")
                continue
            if len(password) < 6:
                console.print("[dim]Password must be at least 6 characters.[/dim]")
                continue

            try:
                with console.status("[cyan]Creating account...[/cyan]"):
                    result = auth.sign_up(client, email, password)
                if result:
                    user_id, user_email = result
                    console.print(f"[green]Account created — signed in as {user_email}[/green]")
                    return user_id
                else:
                    console.print("[dim]Check your email for a confirmation link, then sign in.[/dim]")
            except Exception as exc:
                console.print(f"[red]Sign-up failed:[/red] {exc}")
                continue

        console.print("[dim]Type [bold]1[/bold], [bold]2[/bold], or [bold]q[/bold].[/dim]")


def main() -> None:
    try:
        cfg = load_config()
    except ConfigError as exc:
        console.print(f"\n[bold red]Setup required[/bold red]")
        console.print(f"[dim]{exc}[/dim]")
        sys.exit(1)

    # Phase 5: connect + auth
    try:
        client = store.get_client(cfg)
    except Exception as exc:
        console.print(f"\n[red]Could not connect to Supabase.[/red]")
        console.print(f"[dim]{exc}[/dim]")
        sys.exit(1)

    user_id = _auth_flow(client)
    if user_id is None:
        console.print("[dim]Goodbye.[/dim]")
        sys.exit(0)
    cfg.user_id = user_id

    # Count memories post-auth
    try:
        count = store.count_memories(client, cfg.user_id)
    except Exception as exc:
        console.print(f"[red]Could not fetch memories:[/red] {exc}")
        count = 0

    console.print(Panel.fit(
        "[bold cyan]Recall[/bold cyan] — your personal memory CLI",
        border_style="cyan",
    ))
    console.print(f"[dim]Memories stored: {count}[/dim]")
    console.print("[dim]Type [bold]/help[/bold] for commands or [bold]/quit[/bold] to exit.[/dim]\n")

    # Quick win: conversation history for follow-up routing.
    _history: list[dict] = []

    while True:
        try:
            line = input("you \u203a ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not _dispatch(line, cfg, client, _history):
            break
