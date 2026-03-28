from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path

from eas_client.config import ClientConfig
from eas_client.eas.commands import (
    build_folder_sync_request,
    build_item_operations_attachment_request,
    build_item_operations_message_request,
    build_provision_request,
    build_sync_request,
)
from eas_client.eas.models import MessageSummary, ProvisionResponse, SyncResponse
from eas_client.eas.parsers import (
    parse_folder_sync_response,
    parse_item_operations_attachment_response,
    parse_item_operations_message_response,
    parse_provision_response,
    parse_sync_response,
)
from eas_client.ews import EwsClient
from eas_client.transport import EasTransport
from eas_client.wbxml import WbxmlDocument, WbxmlElement, WbxmlOpaque, WbxmlText, decode_document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eas-cli")
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

    message_detail = subparsers.add_parser("message-detail", help="Read one message and attachment metadata")
    message_detail.add_argument("--collection-id", required=True)
    message_detail.add_argument("--server-id", required=True)
    message_detail.add_argument("--json", action="store_true")
    _add_connection_args(message_detail)

    provision = subparsers.add_parser("provision", help="Run Provision and print mailbox policy")
    _add_connection_args(provision)

    ews_find_items = subparsers.add_parser("ews-find-items", help="List recent inbox messages via EWS")
    ews_find_items.add_argument("--max-items", type=int, default=10)
    _add_connection_args(ews_find_items)

    ews_get_item = subparsers.add_parser("ews-get-item", help="Fetch one message and attachment metadata via EWS")
    ews_get_item.add_argument("--item-id", required=True)
    _add_connection_args(ews_get_item)

    ews_download_attachment = subparsers.add_parser(
        "ews-download-attachment",
        help="Download a file attachment via EWS",
    )
    ews_download_attachment.add_argument("--attachment-id", required=True)
    ews_download_attachment.add_argument("--output", required=True)
    _add_connection_args(ews_download_attachment)

    download_attachment = subparsers.add_parser(
        "download-attachment",
        help="Find the first attachment for a message and save it locally",
    )
    download_attachment.add_argument("--collection-id", required=True)
    download_attachment.add_argument("--server-id", required=True)
    download_attachment.add_argument("--output", required=True)
    download_attachment.add_argument("--attachment-index", type=int, default=0)
    download_attachment.add_argument("--sync-key", default="0")
    download_attachment.add_argument("--window-size", type=int, default=50)
    _add_connection_args(download_attachment)

    dump = subparsers.add_parser("dump-wbxml", help="Write a live WBXML response to disk")
    dump.add_argument("--command", dest="live_command", choices=["folder-sync", "sync"], required=True)
    dump.add_argument("--output", required=True)
    dump.add_argument("--sync-key", default="0")
    dump.add_argument("--collection-id")
    dump.add_argument("--window-size", type=int, default=10)
    _add_connection_args(dump)

    decode = subparsers.add_parser("decode-wbxml", help="Decode a saved WBXML file")
    decode.add_argument("path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "decode-wbxml":
            payload = Path(args.path).read_bytes()
            document = decode_document(payload)
            print(render_document(document))
            return 0

        config = _config_from_args(args)
        transport = EasTransport(config)
        ews_client = EwsClient(config)

        if args.command == "folders":
            payload = build_folder_sync_request(sync_key=args.sync_key)
            response = transport.post("FolderSync", payload)
            result = parse_folder_sync_response(response)
            if args.json:
                print(render_json(result))
                return 0
            for folder in result.folders:
                print(
                    f"{folder.server_id}\t{folder.parent_id}\t"
                    f"{folder.folder_type}\t{folder.display_name}"
                )
            return 0

        if args.command == "messages":
            result = _run_sync(
                transport=transport,
                collection_id=args.collection_id,
                sync_key=args.sync_key,
                window_size=args.window_size,
            )
            if args.json:
                print(render_json(result))
                return 0

            for message in result.messages:
                print(
                    f"{message.server_id}\t{message.received_at or '-'}\t"
                    f"{message.sender or '-'}\t{message.subject or '-'}"
                )
            return 0

        if args.command == "message-detail":
            result = _run_message_detail(
                transport=transport,
                collection_id=args.collection_id,
                server_id=args.server_id,
            )
            if args.json:
                print(render_json(result))
                return 0

            print(f"subject={result.subject or '-'}")
            print(f"from={result.sender or '-'}")
            print(f"to={result.to or '-'}")
            print(f"received_at={result.received_at or '-'}")
            print(f"body_type={result.body_type or '-'}")
            print(f"body_length={len(result.body or '')}")
            for attachment in result.attachments:
                print(
                    f"attachment\t{attachment.display_name or '-'}\t{attachment.size or '-'}\t"
                    f"{attachment.content_type or '-'}"
                )
            return 0

        if args.command == "provision":
            result = _run_provision(transport)
            print(f"status={result.status}")
            print(f"policy_type={result.policy_type or '-'}")
            print(f"policy_key={result.policy_key or '-'}")
            for key in sorted(result.settings):
                print(f"{key}={result.settings[key]}")
            return 0

        if args.command == "ews-find-items":
            result = ews_client.find_items(max_items=args.max_items)
            for item in result.items:
                print(
                    f"{item.item_id}\t{item.received_at or '-'}\t"
                    f"{item.sender or '-'}\t{item.subject or '-'}\t"
                    f"{'1' if item.has_attachments else '0'}"
                )
            return 0

        if args.command == "ews-get-item":
            result = ews_client.get_item(args.item_id)
            print(f"item_id={result.item_id}")
            print(f"change_key={result.change_key or '-'}")
            print(f"subject={result.subject or '-'}")
            print(f"body_length={len(result.body or '')}")
            for attachment in result.attachments:
                print(
                    f"attachment\t{attachment.attachment_id}\t{attachment.name or '-'}\t"
                    f"{attachment.content_type or '-'}\t{attachment.size or '-'}\t"
                    f"{'1' if attachment.is_inline else '0'}"
                )
            return 0

        if args.command == "ews-download-attachment":
            result = ews_client.get_attachment(args.attachment_id)
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(result.content)
            print(str(output_path))
            return 0

        if args.command == "download-attachment":
            result = _run_sync(
                transport=transport,
                collection_id=args.collection_id,
                sync_key=args.sync_key,
                window_size=args.window_size,
            )
            message = _require_message(result, args.server_id)
            attachment = _require_attachment(message, args.attachment_index)
            if attachment.file_reference is None:
                raise ValueError(f"Attachment {args.attachment_index} on message {args.server_id} has no file reference")

            payload = build_item_operations_attachment_request(attachment.file_reference)
            response = transport.post("ItemOperations", payload)
            try:
                attachment_result = parse_item_operations_attachment_response(response)
            except ValueError as exc:
                if "ItemOperations status '130'" in str(exc):
                    policy = _run_provision(transport)
                    if policy.settings.get("AttachmentsEnabled") == "0":
                        raise ValueError(
                            "Attachment download denied by server policy: AttachmentsEnabled=0"
                        ) from exc
                raise

            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(attachment_result.data)
            print(str(output_path))
            return 0

        if args.command == "dump-wbxml":
            if args.live_command == "sync" and not args.collection_id:
                parser.error("--collection-id is required when --command sync")

            command_name, payload = _build_live_request(args)
            response = transport.post(command_name, payload)
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(response)
            print(str(output_path))
            return 0

    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


def render_document(document: WbxmlDocument) -> str:
    lines: list[str] = []
    _render_node(document.root, lines, level=0)
    return "\n".join(lines)


def render_json(value: object) -> str:
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
        mapping["EWS_USER_AGENT"] = args.user_agent
    if getattr(args, "timeout", None) is not None:
        mapping["EAS_TIMEOUT"] = str(args.timeout)
    if getattr(args, "insecure", False):
        mapping["EAS_VERIFY_TLS"] = "false"

    combined = {
        key: value
        for key, value in {
            "EAS_SERVER": mapping.get("EAS_SERVER"),
            "EAS_USERNAME": mapping.get("EAS_USERNAME"),
            "EAS_PASSWORD": mapping.get("EAS_PASSWORD"),
            "EAS_ACCOUNT_EMAIL": mapping.get("EAS_ACCOUNT_EMAIL"),
            "EAS_DEVICE_ID": mapping.get("EAS_DEVICE_ID"),
            "EAS_DEVICE_TYPE": mapping.get("EAS_DEVICE_TYPE"),
            "EAS_USER_AGENT": mapping.get("EAS_USER_AGENT"),
            "EAS_TIMEOUT": mapping.get("EAS_TIMEOUT"),
            "EAS_VERIFY_TLS": mapping.get("EAS_VERIFY_TLS"),
            "EWS_USER_AGENT": mapping.get("EWS_USER_AGENT"),
        }.items()
        if value is not None
    }
    return ClientConfig.from_mapping({**dict(_read_env_defaults()), **combined})


def _read_env_defaults() -> dict[str, str]:
    import os

    return {key: value for key, value in os.environ.items() if key.startswith("EAS_")}


def _build_live_request(args: argparse.Namespace) -> tuple[str, bytes]:
    if args.live_command == "folder-sync":
        return "FolderSync", build_folder_sync_request(sync_key=args.sync_key)
    if not args.collection_id:
        raise ValueError("--collection-id is required for sync dumps")
    return (
        "Sync",
        build_sync_request(
            collection_id=args.collection_id,
            sync_key=args.sync_key,
            window_size=args.window_size,
        ),
    )


def _run_sync(
    *,
    transport: EasTransport,
    collection_id: str,
    sync_key: str,
    window_size: int,
) -> SyncResponse:
    payload = build_sync_request(
        collection_id=collection_id,
        sync_key=sync_key,
        window_size=window_size,
    )
    response = transport.post("Sync", payload)
    result = parse_sync_response(response)

    if sync_key == "0":
        payload = build_sync_request(
            collection_id=collection_id,
            sync_key=result.sync_key,
            window_size=window_size,
        )
        response = transport.post("Sync", payload)
        result = parse_sync_response(response)

    return result


def _run_provision(transport: EasTransport) -> ProvisionResponse:
    initial = parse_provision_response(transport.post("Provision", build_provision_request()))
    if initial.policy_key is None:
        return initial

    previous_key = transport.config.policy_key
    transport.config.__dict__["policy_key"] = initial.policy_key
    try:
        acknowledged = parse_provision_response(
            transport.post("Provision", build_provision_request(policy_key=initial.policy_key))
        )
    finally:
        transport.config.__dict__["policy_key"] = previous_key

    if not acknowledged.settings:
        return ProvisionResponse(
            status=acknowledged.status,
            policy_type=acknowledged.policy_type or initial.policy_type,
            policy_key=acknowledged.policy_key,
            settings=initial.settings,
        )
    return acknowledged


def _run_message_detail(
    *,
    transport: EasTransport,
    collection_id: str,
    server_id: str,
):
    payload = build_item_operations_message_request(collection_id=collection_id, server_id=server_id)
    response = transport.post("ItemOperations", payload)
    return parse_item_operations_message_response(response)


def _require_message(result: SyncResponse, server_id: str) -> MessageSummary:
    for message in result.messages:
        if message.server_id == server_id:
            return message
    raise ValueError(f"Message {server_id!r} was not found in the current sync window")


def _require_attachment(message: MessageSummary, index: int):
    if index < 0 or index >= len(message.attachments):
        raise ValueError(
            f"Message {message.server_id!r} does not have attachment index {index}; "
            f"available attachments: {len(message.attachments)}"
        )
    return message.attachments[index]


def _render_node(node: WbxmlElement | WbxmlText | WbxmlOpaque, lines: list[str], level: int) -> None:
    indent = "  " * level
    if isinstance(node, WbxmlText):
        lines.append(f"{indent}{node.text}")
        return
    if isinstance(node, WbxmlOpaque):
        lines.append(f"{indent}<opaque>{node.opaque.hex()}</opaque>")
        return

    lines.append(f"{indent}<{node.tag}>")
    for child in node.children:
        _render_node(child, lines, level + 1)
    lines.append(f"{indent}</{node.tag}>")


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
