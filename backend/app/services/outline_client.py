"""Outline Wiki API client for syncing enzyme data to the knowledge base.

Uses the Outline REST API (v1) with Bearer token authentication.
All methods are async and use httpx for non-blocking HTTP calls.

Environment variables:
    OUTLINE_API_URL:  Base URL (default: http://outline:3001/api)
    OUTLINE_API_TOKEN: API key (required)
"""

from __future__ import annotations

import os
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OUTLINE_API_URL = os.getenv("OUTLINE_API_URL", "http://outline:3001/api")
OUTLINE_API_TOKEN = os.getenv("OUTLINE_API_TOKEN", "")

# Timeout for API calls (Outline can be slow on large docs)
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class OutlineClient:
    """Async client for the Outline Wiki API."""

    def __init__(
        self,
        api_url: str | None = None,
        api_token: str | None = None,
    ):
        self.api_url = (api_url or OUTLINE_API_URL).rstrip("/")
        self.api_token = api_token or OUTLINE_API_TOKEN
        if not self.api_token:
            logger.warning("OUTLINE_API_TOKEN not set — Outline sync will fail")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    async def list_collections(self) -> list[dict]:
        """List all collections accessible to the API token."""
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/collections.list",
                headers=self._headers,
                json={"limit": 100},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def create_collection(
        self,
        name: str,
        description: str = "",
        parent_id: str | None = None,
    ) -> dict:
        """Create a new collection.

        Args:
            name: Collection name (e.g., "酶数据库").
            description: Optional description.
            parent_id: Optional parent collection ID for nesting.

        Returns:
            Created collection dict with "id" field.
        """
        payload: dict[str, Any] = {
            "name": name,
            "description": description,
            "permission": "member",
        }
        if parent_id:
            payload["parentId"] = parent_id

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/collections.create",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            collection = data.get("data", {})
            logger.info("Created collection: %s (id=%s)", name, collection.get("id"))
            return collection

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def create_document(
        self,
        title: str,
        content: str,
        collection_id: str,
        parent_id: str | None = None,
        publish: bool = True,
    ) -> dict:
        """Create a new Markdown document in a collection.

        Args:
            title: Document title.
            content: Markdown content.
            collection_id: Target collection ID.
            parent_id: Optional parent document ID for nesting.
            publish: Whether to publish immediately (vs draft).

        Returns:
            Created document dict with "id" field.
        """
        payload: dict[str, Any] = {
            "title": title,
            "text": content,
            "collectionId": collection_id,
            "publish": publish,
        }
        if parent_id:
            payload["parentDocumentId"] = parent_id

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/documents.create",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            doc = data.get("data", {})
            logger.info("Created document: %s (id=%s)", title, doc.get("id"))
            return doc

    async def update_document(
        self,
        doc_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> dict:
        """Update an existing document.

        Args:
            doc_id: Document ID to update.
            title: New title (optional).
            content: New Markdown content (optional).

        Returns:
            Updated document dict.
        """
        payload: dict[str, Any] = {"id": doc_id}
        if title is not None:
            payload["title"] = title
        if content is not None:
            payload["text"] = content

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/documents.update",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})

    async def search_documents(
        self,
        query: str,
        collection_id: str | None = None,
        limit: int = 25,
    ) -> list[dict]:
        """Search documents by title or content.

        Args:
            query: Search query string.
            collection_id: Optional collection to restrict search.
            limit: Max results to return.

        Returns:
            List of matching document dicts.
        """
        payload: dict[str, Any] = {
            "query": query,
            "limit": limit,
        }
        if collection_id:
            payload["collectionId"] = collection_id

        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/documents.search",
                headers=self._headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    async def list_documents(
        self,
        collection_id: str,
        limit: int = 100,
    ) -> list[dict]:
        """List all documents in a collection.

        Args:
            collection_id: Collection to list documents from.
            limit: Max documents to return.

        Returns:
            List of document dicts (id, title, updatedAt).
        """
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{self.api_url}/documents.list",
                headers=self._headers,
                json={"collectionId": collection_id, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if Outline API is reachable and authenticated."""
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                resp = await client.get(
                    f"{self.api_url}/../api/auth.info",
                    headers=self._headers,
                )
                return resp.status_code == 200
        except Exception as e:
            logger.warning("Outline health check failed: %s", e)
            return False


# Module-level singleton for convenience
_client: OutlineClient | None = None


def get_outline_client() -> OutlineClient:
    """Get or create the singleton Outline client."""
    global _client
    if _client is None:
        _client = OutlineClient()
    return _client
