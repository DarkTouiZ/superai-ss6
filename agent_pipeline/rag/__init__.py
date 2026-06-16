"""RAG subsystem: ingest → embed → store → retrieve."""
from .retriever import Retriever, build_index

__all__ = ["Retriever", "build_index"]
