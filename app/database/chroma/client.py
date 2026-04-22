from __future__ import annotations

from functools import lru_cache

import chromadb
from chromadb import PersistentClient
from chromadb.api.models.Collection import Collection

from app.core.settings import get_settings


settings = get_settings()


@lru_cache
def get_chroma_client() -> PersistentClient:
    """Return a cached persistent Chroma client."""
    return chromadb.PersistentClient(path=str(settings.chroma_path))


@lru_cache
def get_memory_collection() -> Collection:
    """Return the primary conversation memory collection."""
    client = get_chroma_client()
    return client.get_or_create_collection(name=settings.chroma_collection_name)
