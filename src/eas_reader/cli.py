"""Minimal EAS mail reader CLI — folders and messages commands only."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass

from eas_reader.config import ClientConfig
from eas_reader.eas.commands import build_folder_sync_request, build_sync_request
from eas_reader.eas.parsers import parse_folder_sync_response, parse_sync_response
from eas_reader.transport import EasTransport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eas-mail-reader",
        description="Minimal Exchange ActiveSync mail reader",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    folders = subparsers.add_parser("folders", help="Run FolderSync and print folders")
    folders.add_argument("--sync-key", default="0")
    folders.add_argument("--json", action="store_true")
    _add_connection_args(folders)

    messages = subparsers.add_parser("messages", help="Run Sync and print message summaries")
    messages.add_argument("--collection-id", required=True)
    messages.add_argument("--sync-key", default="0")
    messages.add_argument("--window-size", type=int, default=10)
    messages.add_argument("--json", action="store_true")
    _add_connection_args(messages)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = _config_from_args(args)
        transport = EasTransport(config)

        if args.command == "folders":
            payload = build_folder_sync_request(sync_key=args.sync_key)
            response = transport.post("FolderSync", payload)
            result = parse_folder_sync_response(response)
            if args.json:
                print(_render_json(result))
                return 0
            for folder in result.folders:
                print(
                    f"{folder.server_id}\t{folder.parent_id}\t"
                    f"{folder.folder_type}\t{folder.display_name}"
                )
            return 0

        if args.command == "messages":
            payload = build_sync_request(
                collection_id=args.collection_id,
                sync_key=args.sync_key,
                window_size=args.window_size,
            )
            response = transport.post("Sync", payload)
            result = parse_sync_response(response)

            if args.sync_key == "0":
                payload = build_sync_request(
                    collection_id=args.collection_id,
                    sync_key=result.sync_key,
                    window_size=args.window_size,
                )
                response = transport.post("Sync", payload)
                result = parse_sync_response(response)

            if args.json:
                print(_render_json(result))
                return 0
            for message in result.messages:
                print(
                    f"{message.server_id}\t{message.received_at or '-'}\t"
                    f"{message.sender or '-'}\t{message.subject or '-'}"
                )
            return 0

    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


def _render_json(value: object) -> str:
    return json.dumps(_json_ready(value), ensure_ascii=False, sort_keys=True)


def _add_connection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--server")
    parser.add_argument("--username")
    parser.add_argument("--password")
    parser.add_argument("--account-email")
    parser.add_argument("--device-id")
    parser.add_argument("--device-type")
    parser.add_argument("--user-agent")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--insecure", action="store_true")


def _config_from_args(args: argparse.Namespace) -> ClientConfig:
    mapping: dict[str, str] = {}
    if args.server:
        mapping["EAS_SERVER"] = args.server
    if args.username:
        mapping["EAS_USERNAME"] = args.username
    if args.password:
        mapping["EAS_PASSWORD"] = args.password
    if getattr(args, "account_email", None):
        mapping["EAS_ACCOUNT_EMAIL"] = args.account_email
    if getattr(args, "device_id", None):
        mapping["EAS_DEVICE_ID"] = args.device_id
    if getattr(args, "device_type", None):
        mapping["EAS_DEVICE_TYPE"] = args.device_type
    if getattr(args, "user_agent", None):
        mapping["EAS_USER_AGENT"] = args.user_agent
    if getattr(args, "timeout", None) is not None:
        mapping["EAS_TIMEOUT"] = str(args.timeout)
    if getattr(args, "insecure", False):
        mapping["EAS_VERIFY_TLS"] = "false"

    env_defaults = {key: value for key, value in os.environ.items() if key.startswith("EAS_")}
    return ClientConfig.from_mapping({**env_defaults, **mapping})


def _json_ready(value: object) -> object:
    if is_dataclass(value):
        return {key: _json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    return value


if __name__ == "__main__":
    raise SystemExit(main())
