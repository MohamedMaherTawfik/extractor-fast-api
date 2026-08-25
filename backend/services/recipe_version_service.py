"""Immutable recipe history and experiment-ready variant management."""

from uuid import uuid4

from sqlalchemy.orm import Session

from backend.core.exceptions import NotFoundError
from backend.repositories.recipe_repository import RecipeRepository
from backend.schemas.pattern_recipe import RecipeVariantCreate, RecipeVersionCreate


class RecipeVersionService:
    def __init__(self, session: Session) -> None:
        self.repository = RecipeRepository(session)

    def create_version(self, identifier: int | str, request: RecipeVersionCreate):
        recipe = self._get(identifier)
        current = max(recipe.versions, key=lambda item: item.version)
        return self.repository.add_version(
            recipe,
            version=recipe.current_version + 1,
            payload=request.payload,
            constraints=request.constraints,
            confidence=current.confidence,
            evidence_type=current.evidence_type,
            evidence=current.evidence,
            provenance={**current.provenance, "derived_from_version": current.version},
            change_summary=request.change_summary,
            created_by=request.created_by,
            pattern_ids=[link.pattern_id for link in current.pattern_links],
            content_ids=[link.content_id for link in current.content_sources],
        )

    def create_variant(self, identifier: int | str, request: RecipeVariantCreate):
        recipe = self._get(identifier)
        version_number = request.base_version or recipe.current_version
        base = next((item for item in recipe.versions if item.version == version_number), None)
        if base is None:
            raise NotFoundError(f"Recipe version {version_number} was not found")
        return self.repository.add_variant(
            recipe,
            variant_uid=f"VAR_{uuid4().hex.upper()}",
            base_version_id=base.id,
            name=request.name,
            changed_variables=list(dict.fromkeys(request.changed_variables)),
            overrides=request.overrides,
            experiment_id=request.experiment_id,
            status="experimental",
        )

    def _get(self, identifier):
        recipe = self.repository.get(identifier)
        if recipe is None:
            raise NotFoundError(f"Recipe {identifier} was not found")
        return recipe

