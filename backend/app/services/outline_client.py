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


class OutlineAuthenticationError(RuntimeError):
    """The configured service key is missing, expired, or revoked."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class OutlineUnavailableError(RuntimeError):
    """Outline could not be reached or returned a server-side failure."""


def _raise_for_outline_response(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise OutlineAuthenticationError(
            f"Outline API authentication failed (HTTP {response.status_code})",
            status_code=response.status_code,
        )
    if response.status_code >= 500:
        raise OutlineUnavailableError(
            f"Outline API returned HTTP {response.status_code}"
        )
    response.raise_for_status()


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

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_token:
            raise OutlineAuthenticationError("Outline API key is missing")
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.post(
                    f"{self.api_url}/{endpoint}", headers=self._headers, json=payload,
                )
        except httpx.RequestError as exc:
            raise OutlineUnavailableError("Outline API could not be reached") from exc
        _raise_for_outline_response(response)
        try:
            return response.json()
        except ValueError as exc:
            raise OutlineUnavailableError("Outline API returned invalid JSON") from exc

    # ------------------------------------------------------------------
    # Collections
    # ------------------------------------------------------------------

    async def list_collections(self) -> list[dict]:
        """List all collections accessible to the API token."""
        data = await self._post("collections.list", {"limit": 100})
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
            "permission": "read_write",
        }
        if parent_id:
            payload["parentId"] = parent_id

        data = await self._post("collections.create", payload)
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

        data = await self._post("documents.create", payload)
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

        data = await self._post("documents.update", payload)
        return data.get("data", {})

    async def get_document(self, doc_id: str) -> dict:
        """Read a document by its Outline ID."""
        data = await self._post("documents.info", {"id": doc_id})
        return data.get("data", {})

    async def delete_document(self, doc_id: str) -> None:
        """Remove a controlled test document from the active Wiki.

        Outline service keys may archive documents but be forbidden from
        permanent deletion. Treat archive as the safe cleanup fallback.
        """
        try:
            await self._post("documents.delete", {"id": doc_id, "permanent": True})
        except OutlineAuthenticationError as exc:
            if exc.status_code != 403:
                raise
            await self._post("documents.archive", {"id": doc_id})

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

        data = await self._post("documents.search", payload)
        return data.get("data", [])

    async def list_documents(
        self,
        collection_id: str,
        parent_document_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """List all documents in a collection.

        Args:
            collection_id: Collection to list documents from.
            limit: Max documents to return.

        Returns:
            List of document dicts (id, title, updatedAt).
        """
        data = await self._post("documents.list", {
            "collectionId": collection_id,
            "parentDocumentId": parent_document_id,
            "limit": limit,
            "sort": "updatedAt",
            "direction": "DESC",
        })
        return data.get("data", [])

    async def get_collection_tree(self, collection_id: str) -> list[dict]:
        """Fetch the hierarchical document tree for a collection.

        Prefer Outline's native tree endpoint, but fall back to recursive
        documents.list calls because some deployments intermittently return
        403 for collections.documents even when document APIs still work.
        """
        try:
            data = await self._post("collections.documents", {"id": collection_id})
            return data.get("data", [])
        except OutlineAuthenticationError as exc:
            if exc.status_code != 403:
                raise
            logger.warning("collections.documents returned 403 for collection %s; checking documents.list", collection_id)
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                raise
            logger.warning(
                "collections.documents failed for collection %s with %s, falling back to documents.list",
                collection_id,
                e.response.status_code,
            )

        return await self._build_collection_tree(collection_id, parent_document_id=None, seen=set())

    async def _build_collection_tree(
        self,
        collection_id: str,
        parent_document_id: str | None,
        seen: set[str],
    ) -> list[dict]:
        documents = await self.list_documents(
            collection_id=collection_id,
            parent_document_id=parent_document_id,
            limit=200,
        )
        tree: list[dict] = []
        for doc in documents:
            doc_id = doc.get("id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            children = await self._build_collection_tree(collection_id, doc_id, seen)
            tree.append({
                **doc,
                "children": children,
            })
        return tree

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Check if Outline API is reachable and authenticated."""
        try:
            await self.list_collections()
            return True
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
