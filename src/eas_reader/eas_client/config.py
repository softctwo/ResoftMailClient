from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.lower() not in {"0", "false", "no", "off"}


@dataclass(frozen=True)
class ClientConfig:
    server: str
    username: str
    password: str
    account_email: str | None = None
    policy_key: str | None = None
    device_id: str = "PYEASCLI001"
    device_type: str = "iPhone"
    user_agent: str = "Apple-iOS/17.0"
    protocol_version: str = "14.0"
    endpoint_path: str = "/Microsoft-Server-ActiveSync"
    ews_endpoint_path: str = "/EWS/Exchange.asmx"
    use_tls: bool = True
    verify_tls: bool = True
    timeout: float = 30.0

    @property
    def base_url(self) -> str:
        scheme = "https" if self.use_tls else "http"
        return f"{scheme}://{self.server}{self.endpoint_path}"

    @property
    def user_query_value(self) -> str:
        return self.account_email or self.username

    @classmethod
    def from_env(cls) -> "ClientConfig":
        return cls.from_mapping(os.environ)

    @classmethod
    def from_mapping(cls, values: dict[str, str] | os._Environ[str]) -> "ClientConfig":
        server = values.get("EAS_SERVER")
        username = values.get("EAS_USERNAME")
        password = values.get("EAS_PASSWORD")
        missing = [
            name
            for name, value in {
                "EAS_SERVER": server,
                "EAS_USERNAME": username,
                "EAS_PASSWORD": password,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required EAS environment variables: {', '.join(missing)}")

        timeout = float(values.get("EAS_TIMEOUT", "30"))
        return cls(
            server=server,
            username=username,
            password=password,
            account_email=values.get("EAS_ACCOUNT_EMAIL"),
            policy_key=values.get("EAS_POLICY_KEY"),
            device_id=values.get("EAS_DEVICE_ID", "PYEASCLI001"),
            device_type=values.get("EAS_DEVICE_TYPE", "iPhone"),
            user_agent=values.get("EAS_USER_AGENT", "Apple-iOS/17.0"),
            protocol_version=values.get("EAS_PROTOCOL_VERSION", "14.0"),
            endpoint_path=values.get("EAS_ENDPOINT_PATH", "/Microsoft-Server-ActiveSync"),
            ews_endpoint_path=values.get("EWS_ENDPOINT_PATH", "/EWS/Exchange.asmx"),
            use_tls=_env_bool(values.get("EAS_USE_TLS"), True),
            verify_tls=_env_bool(values.get("EAS_VERIFY_TLS"), True),
            timeout=timeout,
        )
