from __future__ import annotations

import base64

import requests

from eas_client.config import ClientConfig
from eas_client.ews.models import EwsAttachmentContent, EwsFindItemsResponse, EwsItemDetail
from eas_client.ews.parsers import (
    parse_find_item_response,
    parse_get_attachment_response,
    parse_get_item_response,
)
from eas_client.ews.soap import (
    build_find_item_envelope,
    build_get_attachment_envelope,
    build_get_item_envelope,
)


class EwsClient:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.config.server}{self.config.ews_endpoint_path}"

    def find_items(self, max_items: int = 10) -> EwsFindItemsResponse:
        response = self._post(
            soap_action="http://schemas.microsoft.com/exchange/services/2006/messages/FindItem",
            body=build_find_item_envelope(max_entries=max_items),
        )
        return parse_find_item_response(response)

    def get_item(self, item_id: str) -> EwsItemDetail:
        response = self._post(
            soap_action="http://schemas.microsoft.com/exchange/services/2006/messages/GetItem",
            body=build_get_item_envelope(item_id=item_id),
        )
        return parse_get_item_response(response)

    def get_attachment(self, attachment_id: str) -> EwsAttachmentContent:
        response = self._post(
            soap_action="http://schemas.microsoft.com/exchange/services/2006/messages/GetAttachment",
            body=build_get_attachment_envelope(attachment_id=attachment_id),
        )
        return parse_get_attachment_response(response)

    def _post(self, *, soap_action: str, body: str) -> str:
        errors: list[str] = []
        for username in self._auth_usernames():
            try:
                response = requests.post(
                    self.endpoint_url,
                    data=body.encode("utf-8"),
                    headers=self._headers(username=username, soap_action=soap_action),
                    timeout=self.config.timeout,
                    verify=self.config.verify_tls,
                )
            except requests.RequestException as exc:
                errors.append(f"{username}: {exc}")
                continue

            if response.status_code == 401:
                errors.append(f"{username}: HTTP 401")
                continue

            response.raise_for_status()
            return response.text

        raise ValueError(f"EWS request failed for all auth forms: {'; '.join(errors)}")

    def _headers(self, *, username: str, soap_action: str) -> dict[str, str]:
        auth = base64.b64encode(f"{username}:{self.config.password}".encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {auth}",
            "Content-Type": "text/xml; charset=utf-8",
            "Accept": "text/xml",
            "SOAPAction": soap_action,
            "User-Agent": self.config.user_agent,
        }

    def _auth_usernames(self) -> list[str]:
        usernames = [self.config.account_email, self.config.username]
        deduped: list[str] = []
        for username in usernames:
            if username and username not in deduped:
                deduped.append(username)
        return deduped
