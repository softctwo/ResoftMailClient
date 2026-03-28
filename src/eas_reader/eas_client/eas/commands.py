from eas_client.eas.encoder import WbxmlRequestElement, encode_document

AIRSYNC_PAGE = 0
FOLDER_HIERARCHY_PAGE = 7
PROVISION_PAGE = 14
ITEM_OPERATIONS_PAGE = 20
AIRSYNC_BASE_PAGE = 17
PING_PAGE = 13


def build_folder_sync_request(sync_key: str) -> bytes:
    root = WbxmlRequestElement(
        page=FOLDER_HIERARCHY_PAGE,
        tag="FolderSync",
        children=[
            WbxmlRequestElement(
                page=FOLDER_HIERARCHY_PAGE,
                tag="SyncKey",
                text=sync_key,
            )
        ],
    )
    return encode_document(root)


def build_sync_request(collection_id: str, sync_key: str = "0", window_size: int = 10) -> bytes:
    collection_children = [
        WbxmlRequestElement(page=AIRSYNC_PAGE, tag="SyncKey", text=sync_key),
        WbxmlRequestElement(
            page=AIRSYNC_PAGE,
            tag="CollectionId",
            text=collection_id,
        ),
    ]

    if sync_key != "0":
        collection_children.extend(
            [
                WbxmlRequestElement(page=AIRSYNC_PAGE, tag="GetChanges"),
                WbxmlRequestElement(
                    page=AIRSYNC_PAGE,
                    tag="WindowSize",
                    text=str(window_size),
                ),
            ]
        )

    root = WbxmlRequestElement(
        page=AIRSYNC_PAGE,
        tag="Sync",
        children=[
            WbxmlRequestElement(
                page=AIRSYNC_PAGE,
                tag="Collections",
                children=[
                    WbxmlRequestElement(
                        page=AIRSYNC_PAGE,
                        tag="Collection",
                        children=collection_children,
                    )
                ],
            )
        ],
    )
    return encode_document(root)


def build_item_operations_attachment_request(file_reference: str) -> bytes:
    root = WbxmlRequestElement(
        page=ITEM_OPERATIONS_PAGE,
        tag="ItemOperations",
        children=[
            WbxmlRequestElement(
                page=ITEM_OPERATIONS_PAGE,
                tag="Fetch",
                children=[
                    WbxmlRequestElement(
                        page=ITEM_OPERATIONS_PAGE,
                        tag="Store",
                        text="Mailbox",
                    ),
                    WbxmlRequestElement(
                        page=AIRSYNC_BASE_PAGE,
                        tag="FileReference",
                        text=file_reference,
                    ),
                ],
            )
        ],
    )
    return encode_document(root)


def build_item_operations_message_request(collection_id: str, server_id: str) -> bytes:
    body_preferences = [
        WbxmlRequestElement(
            page=AIRSYNC_BASE_PAGE,
            tag="BodyPreference",
            children=[
                WbxmlRequestElement(
                    page=AIRSYNC_BASE_PAGE,
                    tag="Type",
                    text="2",
                ),
                WbxmlRequestElement(
                    page=AIRSYNC_BASE_PAGE,
                    tag="TruncationSize",
                    text="204800",
                ),
            ],
        ),
        WbxmlRequestElement(
            page=AIRSYNC_BASE_PAGE,
            tag="BodyPreference",
            children=[
                WbxmlRequestElement(
                    page=AIRSYNC_BASE_PAGE,
                    tag="Type",
                    text="1",
                ),
                WbxmlRequestElement(
                    page=AIRSYNC_BASE_PAGE,
                    tag="TruncationSize",
                    text="204800",
                ),
            ],
        ),
    ]

    root = WbxmlRequestElement(
        page=ITEM_OPERATIONS_PAGE,
        tag="ItemOperations",
        children=[
            WbxmlRequestElement(
                page=ITEM_OPERATIONS_PAGE,
                tag="Fetch",
                children=[
                    WbxmlRequestElement(
                        page=ITEM_OPERATIONS_PAGE,
                        tag="Store",
                        text="Mailbox",
                    ),
                    WbxmlRequestElement(
                        page=AIRSYNC_PAGE,
                        tag="CollectionId",
                        text=collection_id,
                    ),
                    WbxmlRequestElement(
                        page=AIRSYNC_PAGE,
                        tag="ServerId",
                        text=server_id,
                    ),
                    WbxmlRequestElement(
                        page=ITEM_OPERATIONS_PAGE,
                        tag="Options",
                        children=body_preferences,
                    ),
                ],
            )
        ],
    )
    return encode_document(root)


def build_provision_request(policy_key: str | None = None) -> bytes:
    policy_children = [
        WbxmlRequestElement(
            page=PROVISION_PAGE,
            tag="PolicyType",
            text="MS-EAS-Provisioning-WBXML",
        )
    ]
    if policy_key is not None:
        policy_children.extend(
            [
                WbxmlRequestElement(
                    page=PROVISION_PAGE,
                    tag="PolicyKey",
                    text=policy_key,
                ),
                WbxmlRequestElement(
                    page=PROVISION_PAGE,
                    tag="Status",
                    text="1",
                ),
            ]
        )

    root = WbxmlRequestElement(
        page=PROVISION_PAGE,
        tag="Provision",
        children=[
            WbxmlRequestElement(
                page=PROVISION_PAGE,
                tag="Policies",
                children=[
                    WbxmlRequestElement(
                        page=PROVISION_PAGE,
                        tag="Policy",
                        children=policy_children,
                    )
                ],
            )
        ],
    )
    return encode_document(root)


def build_ping_request(folder_ids: list[str], heartbeat_interval: int = 600) -> bytes:
    """Build a Ping request to monitor folders for real time."""
    folder_elements = []
    for fid in folder_ids:
        folder_elements.append(
            WbxmlRequestElement(
                page=PING_PAGE,
                tag="Folder",
                children=[
                    WbxmlRequestElement(page=PING_PAGE, tag="Id", text=fid),
                ],
            ),
        )

    root = WbxmlRequestElement(
        page=PING_PAGE,
        tag="Ping",
        children=[
            WbxmlRequestElement(page=PING_PAGE, tag="HeartbeatInterval", text=str(heartbeat_interval)),
            WbxmlRequestElement(
                page=PING_PAGE,
                tag="Folders",
                children=folder_elements,
            ),
        ],
    )
    return encode_document(root)


def build_send_mail_request(mime_message: bytes, client_id: str | None = None) -> bytes:
    """Build a SendMail request. For EAS 14.0, the message is sent as raw MIME in the POST body.
    The URL query params handle the command routing."""
    # For protocol 14.0+, SendMail uses plain MIME body (not WBXML)
    # The Content-Type should be message/rfc822
    return mime_message
