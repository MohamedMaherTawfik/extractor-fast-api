"""Versioned approved customer-service knowledge and safe keyword retrieval."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.db.models.answer_bot import KnowledgeItem, KnowledgeVersion
from backend.repositories.answer_bot_repository import AnswerBotRepository
from backend.sales.common import uid
from backend.schemas.answer_bot import KnowledgeCreate, KnowledgeUpdate


ALLOWED_DOMAINS = {"PRODUCT", "SALES_POLICY", "DELIVERY", "RETURNS", "FAQ", "BRAND", "GENERAL"}


class KnowledgeBaseService:
    def __init__(self, session: Session) -> None: self.repository = AnswerBotRepository(session)

    def create(self, request: KnowledgeCreate) -> KnowledgeItem:
        domain = request.domain.upper()
        if domain not in ALLOWED_DOMAINS: raise ValueError("Unsupported knowledge domain")
        item = self.repository.add(KnowledgeItem(knowledge_uid=uid("KB"), title=request.title, domain=domain, current_version=1, status=request.status.upper()))
        self.repository.add(KnowledgeVersion(knowledge_id=item.id, version=1, content=request.content, language=request.language, keywords=request.keywords, effective_from=request.effective_from, effective_to=request.effective_to, approved_by=request.approved_by, status=request.status.upper(), source_reference=request.source_reference))
        return item

    def get(self, identifier: int | str) -> KnowledgeItem:
        item = self.repository.get_knowledge(identifier)
        if item is None: raise NotFoundError(f"Knowledge item {identifier} was not found")
        return item

    def update(self, identifier: int | str, request: KnowledgeUpdate) -> KnowledgeItem:
        item = self.get(identifier); versions = self.repository.knowledge_versions(item.id)
        if versions and versions[-1].effective_to is None: versions[-1].effective_to = request.effective_from
        item.current_version += 1; item.status = request.status.upper()
        self.repository.add(KnowledgeVersion(knowledge_id=item.id, version=item.current_version, content=request.content, language=request.language, keywords=request.keywords, effective_from=request.effective_from, effective_to=request.effective_to, approved_by=request.approved_by, status=request.status.upper(), source_reference=request.source_reference))
        return item

    def retrieve(self, query: str, *, domain: str | None = None, language: str | None = None, limit: int = 5) -> list[dict]:
        words = {part.casefold() for part in query.split() if len(part) > 1}; results = []
        for item, version in self.repository.active_knowledge_versions(datetime.now(UTC)):
            if domain and item.domain != domain.upper(): continue
            if language and version.language not in {language, "multi"}: continue
            haystack = f"{item.title} {version.content} {' '.join(version.keywords)}".casefold()
            score = sum(word in haystack for word in words)
            if score: results.append({"knowledge_uid": item.knowledge_uid, "title": item.title, "domain": item.domain, "version": version.version, "content": version.content, "source_reference": version.source_reference, "score": score})
        return sorted(results, key=lambda value: (-value["score"], value["knowledge_uid"]))[:limit]
