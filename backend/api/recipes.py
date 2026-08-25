"""API for editable, versioned generation-plan recipes and variants."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from backend.db.session import get_db
from backend.schemas.pattern_recipe import (
    RecipeBuildRequest,
    RecipeEvidenceResponse,
    RecipeResponse,
    RecipeVariantCreate,
    RecipeVariantResponse,
    RecipeVersionCreate,
    RecipeVersionResponse,
)
from backend.services.recipe_builder_service import RecipeBuilderService
from backend.services.recipe_version_service import RecipeVersionService


router = APIRouter(tags=["recipes"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/recipes/build", response_model=RecipeResponse, status_code=status.HTTP_201_CREATED)
def build_recipe(request: RecipeBuildRequest, session: DatabaseSession):
    return RecipeBuilderService(session).build(request)


@router.get("/recipes", response_model=list[RecipeResponse])
def list_recipes(
    session: DatabaseSession,
    platform: str | None = None,
    content_type: str | None = None,
    category: str | None = None,
    recipe_type: str | None = None,
    recipe_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=1000),
):
    return RecipeBuilderService(session).list(
        platform=platform,
        content_type=content_type,
        category=category,
        recipe_type=recipe_type,
        status=recipe_status,
        limit=limit,
    )


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
def get_recipe(recipe_id: str, session: DatabaseSession):
    return RecipeBuilderService(session).get(recipe_id)


@router.post("/recipes/{recipe_id}/versions", response_model=RecipeVersionResponse, status_code=status.HTTP_201_CREATED)
def create_recipe_version(recipe_id: str, request: RecipeVersionCreate, session: DatabaseSession):
    return RecipeVersionService(session).create_version(recipe_id, request)


@router.post("/recipes/{recipe_id}/variants", response_model=RecipeVariantResponse, status_code=status.HTTP_201_CREATED)
def create_recipe_variant(recipe_id: str, request: RecipeVariantCreate, session: DatabaseSession):
    return RecipeVersionService(session).create_variant(recipe_id, request)


@router.get("/recipes/{recipe_id}/evidence", response_model=RecipeEvidenceResponse)
def get_recipe_evidence(recipe_id: str, session: DatabaseSession):
    return RecipeBuilderService(session).evidence(recipe_id)

