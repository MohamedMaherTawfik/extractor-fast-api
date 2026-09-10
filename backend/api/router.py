"""Top-level API router."""

from fastapi import APIRouter

from backend.api.creator_imports import router as creator_imports_router
from backend.api.collection import router as collection_router
from backend.api.analysis import router as analysis_router
from backend.api.creators import router as creators_router
from backend.api.health import router as health_router
from backend.api.patterns import router as patterns_router
from backend.api.recipes import router as recipes_router
from backend.api.rules import router as rules_router
from backend.api.commerce import router as commerce_router
from backend.api.answer_bot import router as answer_bot_router
from backend.api.generation import router as generation_router
from backend.api.operator import router as operator_router
from backend.api.leads import router as leads_router
from backend.api.video_studio import router as video_studio_router
from backend.api.creator_discovery import router as creator_discovery_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(creators_router)
api_router.include_router(creator_imports_router)
api_router.include_router(collection_router)
api_router.include_router(analysis_router)
api_router.include_router(patterns_router)
api_router.include_router(recipes_router)
api_router.include_router(rules_router)
api_router.include_router(generation_router)
api_router.include_router(commerce_router)
api_router.include_router(answer_bot_router)
api_router.include_router(operator_router)
api_router.include_router(leads_router)
api_router.include_router(video_studio_router)
api_router.include_router(creator_discovery_router)
