from eas_reader.eas.encoder import WbxmlRequestElement, encode_document

AIRSYNC_PAGE = 0
FOLDER_HIERARCHY_PAGE = 7


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
