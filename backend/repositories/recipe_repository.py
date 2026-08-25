"""Version-preserving recipe and experimental-variant persistence."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.db.models.pattern_recipe import (
    Recipe,
    RecipeContentSource,
    RecipePatternLink,
    RecipeVariant,
    RecipeVersion,
)


class RecipeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, **values) -> Recipe:
        recipe = Recipe(**values)
        self._session.add(recipe)
        self._session.flush()
        return recipe

    def add_version(
        self,
        recipe: Recipe,
        *,
        pattern_ids: list[int],
        content_ids: list[int],
        **values,
    ) -> RecipeVersion:
        version = RecipeVersion(**values)
        recipe.versions.append(version)
        self._session.flush()
        version.pattern_links.extend(
            RecipePatternLink(pattern_id=pattern_id) for pattern_id in dict.fromkeys(pattern_ids)
        )
        version.content_sources.extend(
            RecipeContentSource(content_id=content_id) for content_id in dict.fromkeys(content_ids)
        )
        recipe.current_version = version.version
        self._session.flush()
        return version

    def add_variant(self, recipe: Recipe, **values) -> RecipeVariant:
        variant = RecipeVariant(recipe_id=recipe.id, control_recipe_id=recipe.id, **values)
        self._session.add(variant)
        self._session.flush()
        return variant

    def get(self, identifier: int | str) -> Recipe | None:
        predicate = (
            Recipe.id == int(identifier)
            if isinstance(identifier, int) or str(identifier).isdigit()
            else Recipe.recipe_uid == str(identifier)
        )
        return self._session.scalar(self._statement().where(predicate))

    def list(
        self,
        *,
        platform: str | None = None,
        content_type: str | None = None,
        category: str | None = None,
        recipe_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[Recipe]:
        statement = self._statement()
        if platform:
            statement = statement.where(Recipe.target_platform == platform)
        if content_type:
            statement = statement.where(Recipe.content_type == content_type)
        if category:
            statement = statement.where(Recipe.target_category == category)
        if recipe_type:
            statement = statement.where(Recipe.recipe_type == recipe_type)
        if status:
            statement = statement.where(Recipe.status == status)
        return list(self._session.scalars(statement.order_by(Recipe.updated_at.desc()).limit(limit)))

    @staticmethod
    def _statement():
        return select(Recipe).options(
            selectinload(Recipe.versions).selectinload(RecipeVersion.pattern_links),
            selectinload(Recipe.versions).selectinload(RecipeVersion.content_sources),
            selectinload(Recipe.variants),
        )
