from __future__ import annotations

import base64
from urllib.parse import urlencode

import requests

from eas_reader.config import ClientConfig


class EasTransport:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config

    def build_url(self, command: str) -> str:
        query = urlencode(
            {
                "Cmd": command,
                "User": self.config.user_query_value,
                "DeviceId": self.config.device_id,
                "DeviceType": self.config.device_type,
            }
        )
        return f"{self.config.base_url}?{query}"

    def default_headers(self) -> dict[str, str]:
        credentials = f"{self.config.username}:{self.config.password}".encode("utf-8")
        headers = {
            "Authorization": f"Basic {base64.b64encode(credentials).decode('ascii')}",
            "MS-ASProtocolVersion": self.config.protocol_version,
            "MS-ASDeviceId": self.config.device_id,
            "MS-ASDeviceType": self.config.device_type,
            "Content-Type": "application/vnd.ms-sync.wbxml",
            "User-Agent": self.config.user_agent,
        }
        if self.config.policy_key is not None:
            headers["X-MS-PolicyKey"] = self.config.policy_key
        return headers

    def post(self, command: str, payload: bytes) -> bytes:
        response = requests.post(
            self.build_url(command),
            data=payload,
            headers=self.default_headers(),
            timeout=self.config.timeout,
            verify=self.config.verify_tls,
        )
        response.raise_for_status()
        return response.content
