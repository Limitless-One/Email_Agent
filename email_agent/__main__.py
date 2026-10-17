"""Command line entry point for local runs, operator export, and offline evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from .config import AgentConfig
from .gmail_client import GmailApiClient
from .llm import build_provider
from .state import AgentState
from .worker import EmailAgentWorker
from .evaluation import run_interactive_replay, run_offline_suite


def main() -> None:
    parser = argparse.ArgumentParser(description="NovaGear email support worker")
    parser.add_argument("command", choices=("once", "poll", "export", "evaluate", "replay", "retry", "debug", "inspect"))
    parser.add_argument("target", nargs="?", help="JSON path for replay, or Gmail message ID for retry, debug, or inspect")
    args = parser.parse_args()
    config = AgentConfig.from_env()
    state = AgentState(config.state_db_path)
    if args.command == "evaluate":
        print(json.dumps(run_offline_suite(), indent=2))
        return
    if args.command == "replay":
        if not args.target:
            parser.error("replay requires a path to an input JSON file")
        try:
            print(json.dumps(run_interactive_replay(Path(args.target)), indent=2))
        except ValueError as exc:
            parser.error(str(exc))
        return
    if args.command == "retry":
        if not args.target:
            parser.error("retry requires a Gmail message ID")
        if not state.request_retry(args.target):
            parser.error("message is not currently in needs_review")
        print(json.dumps({"retry_requested": args.target}))
        return
    if args.command == "debug":
        if not args.target:
            parser.error("debug requires a Gmail message ID")
        output_dir = Path("debug")
        output_dir.mkdir(exist_ok=True)
        path = output_dir / f"{args.target}.json"
        path.write_text(json.dumps(state.export_debug_trace(args.target), indent=2), encoding="utf-8")
        print(json.dumps({"debug_export": str(path)}))
        return
    if args.command == "inspect":
        if not args.target:
            parser.error("inspect requires a Gmail message ID")
        report = state.export_debug_trace(args.target)
        message, response = report["message"], report["response"]
        print(f"Message: {message['gmail_message_id']}\nStatus: {message['status']}\nTrace: {message['trace_id']}")
        print("\nProposed reply:")
        print(response["body"] if response else "No response plan was stored for this earlier run.")
        print("\nProcess:")
        for event in report["events"]:
            print(f"- {event['event_type']}: {json.dumps(event['data'], sort_keys=True)}")
        return
    if args.command == "export":
        print(json.dumps({"metrics": state.metrics(), "messages": state.operator_rows()}, indent=2))
        return
    worker = EmailAgentWorker(config, GmailApiClient(config), build_provider(config), state)
    if args.command == "once":
        print(json.dumps(worker.run_once()))
        return
    while True:
        print(json.dumps(worker.run_once()))
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    main()
