# ══════════════════════════════════════════════════════════════
# routes/docs.py — proxy endpoints for user-facing documentation
# ══════════════════════════════════════════════════════════════
# Streams the User Manual and Release Notes from the private Azure Blob
# container `ai-navigator-docs`. Reuses the same ACCOUNT_NAME/ACCOUNT_KEY
# env vars that feedback attachments use — no new credentials required.
#
# Why proxy instead of returning a SAS URL?
#   • One click, one request from the browser (no extra JSON round-trip).
#   • URLs stay short and permanent: /docs/user-manual, /docs/release-notes.
#     Uploading a new version of the blob (same name) instantly updates
#     what users see — the HTML never needs to change.
#   • Container stays PRIVATE — only the app can read blobs via the
#     account key, so uploaded docs aren't publicly enumerable.
#
# Adding another document later? Add a new tuple to _DOC_MAP and wire an
# @router.get route — no other file needs to change.
# ══════════════════════════════════════════════════════════════

import logging
import os
from typing import Tuple

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

_log = logging.getLogger(__name__)

router = APIRouter()

# Container that holds the docs. Sibling of `ai-navigator-feedback`
# in the same storage account (ACCOUNT_NAME).
_DOCS_CONTAINER = "ai-navigator-docs"

# Logical name → (blob filename in the container, MIME type, download filename).
# The download filename is what browsers suggest if the user hits "Save as…";
# we keep it identical to the blob name so versioning stays obvious.
_DOC_MAP = {
    "user-manual": (
        "AI_Navigator_User_Manual_v1.pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "release-notes": (
        "AI_Navigator_Release_Notes_v1.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
}


def _get_docs_container():
    """Return a container client for `ai-navigator-docs`.

    Mirrors routes/feedback.py::_get_blob_container() so credentials and
    connection-string format stay identical across the app.
    """
    from azure.storage.blob import BlobServiceClient

    account_name = os.getenv("ACCOUNT_NAME", "")
    account_key  = os.getenv("ACCOUNT_KEY", "")
    if not account_name or not account_key:
        raise HTTPException(500, "Azure Storage credentials are not configured")

    conn_str = (
        f"DefaultEndpointsProtocol=https;"
        f"AccountName={account_name};"
        f"AccountKey={account_key};"
        f"EndpointSuffix=core.windows.net"
    )
    client = BlobServiceClient.from_connection_string(conn_str)
    return client.get_container_client(_DOCS_CONTAINER)


def _stream_doc(doc_key: str) -> StreamingResponse:
    """Download the blob and stream it back to the browser.

    .docx / .pptx don't render inline in browsers — every browser will
    download them regardless of Content-Disposition. We still send
    `inline` so browsers with the Office plugin (Edge, some Chrome
    setups) can preview it; others will download with the correct name.
    """
    if doc_key not in _DOC_MAP:
        raise HTTPException(404, "Document not found")

    blob_name, content_type = _DOC_MAP[doc_key]

    try:
        container = _get_docs_container()
        downloader = container.download_blob(blob_name)
        # readall() pulls the full file into memory. These are small
        # marketing/help docs (< 10 MB) so this is fine and simpler than
        # a chunked iterator. If docs ever grow past ~20 MB, switch to
        # `downloader.chunks()` and yield each chunk.
        data = downloader.readall()
    except HTTPException:
        raise
    except Exception as e:
        _log.exception("[docs] Failed to fetch blob %s: %s", blob_name, e)
        raise HTTPException(502, f"Could not fetch document: {e}")

    headers = {
        # `inline` lets browsers that CAN preview (PDFs, some Office
        # viewers) show it in-tab; ones that can't will download using
        # the filename below. This is the same behaviour SharePoint gives.
        "Content-Disposition": f'inline; filename="{blob_name}"',
        "Cache-Control": "no-cache",
    }

    # StreamingResponse with a single-element iterable is equivalent to a
    # plain Response but keeps the API uniform if we later swap to chunked.
    return StreamingResponse(iter([data]), media_type=content_type, headers=headers)


@router.get("/docs/user-manual")
async def get_user_manual():
    """Serve the AI Navigator user manual (PowerPoint)."""
    return _stream_doc("user-manual")


@router.get("/docs/release-notes")
async def get_release_notes():
    """Serve the AI Navigator release notes (Word)."""
    return _stream_doc("release-notes")
