"""Inspect or prune one local LangGraph session thread."""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.checkpoint import (  # noqa: E402
    checkpoint_thread_id, open_checkpointer, selector_loop_factory,
)
from app.db.session import get_engine  # noqa: E402


def checkpoint_count(thread_id: str) -> int:
    with get_engine().connect() as db:
        return db.scalar(text("SELECT count(*) FROM public.checkpoints WHERE thread_id = :id"), {"id": thread_id}) or 0


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--session-id", type=int, required=True)
    parser.add_argument("--action", choices=("inspect", "keep-latest", "delete"), default="inspect")
    parser.add_argument("--apply", action="store_true", help="Perform the selected pruning action")
    args = parser.parse_args()
    if args.user_id <= 0 or args.session_id <= 0:
        parser.error("user-id and session-id must be positive")

    thread_id = checkpoint_thread_id(args.user_id, args.session_id)
    async with open_checkpointer() as saver:
        before = checkpoint_count(thread_id)
        print(f"thread={thread_id} checkpoints={before}")
        if args.action == "inspect":
            return
        if not args.apply:
            print(f"dry run: add --apply to {args.action} this thread")
            return
        if args.action == "keep-latest":
            await saver.aprune([thread_id], strategy="keep_latest")
        else:
            await saver.adelete_thread(thread_id)
        print(f"after {args.action}: checkpoints={checkpoint_count(thread_id)}")


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=selector_loop_factory)
