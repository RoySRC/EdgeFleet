from __future__ import annotations

import math
import re
from abc import ABC, abstractmethod
from collections import Counter

from edgefleet.models import Document

_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9_]+")


def _tokens(text: str) -> list[str]:
    return [item.lower() for item in _TOKEN_PATTERN.findall(text)]


class Retriever(ABC):
    @abstractmethod
    async def search(
        self, query: str, *, limit: int = 4
    ) -> list[Document]:
        raise NotImplementedError


class InMemoryRetriever(Retriever):
    """Dependency-free TF-IDF retrieval for small local knowledge bases."""

    def __init__(self, documents: list[Document] | None = None) -> None:
        self.documents = list(documents or [])

    def add(self, document: Document) -> None:
        self.documents.append(document)

    async def search(
        self, query: str, *, limit: int = 4
    ) -> list[Document]:
        query_terms = Counter(_tokens(query))
        if not query_terms or not self.documents:
            return []

        document_terms = [
            Counter(_tokens(document.text)) for document in self.documents
        ]
        count = len(document_terms)
        document_frequency = Counter(
            term for terms in document_terms for term in terms
        )
        idf = {
            term: math.log((count + 1) / (frequency + 1)) + 1
            for term, frequency in document_frequency.items()
        }

        def vector(terms: Counter[str]) -> dict[str, float]:
            return {
                term: frequency * idf.get(term, 1.0)
                for term, frequency in terms.items()
            }

        query_vector = vector(query_terms)
        query_norm = math.sqrt(
            sum(value * value for value in query_vector.values())
        )
        scored: list[tuple[float, Document]] = []
        for document, terms in zip(
            self.documents, document_terms, strict=True
        ):
            document_vector = vector(terms)
            dot = sum(
                query_vector.get(term, 0.0) * value
                for term, value in document_vector.items()
            )
            document_norm = math.sqrt(
                sum(value * value for value in document_vector.values())
            )
            score = (
                dot / (query_norm * document_norm)
                if query_norm and document_norm
                else 0.0
            )
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [document for _, document in scored[:limit]]

