"""Compile immutable Generation Contracts into provider-neutral prompt packages."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from uuid import uuid4

from backend.core.enums import GenerationType
from backend.core.exceptions import PromptConflictError, ReferenceSafetyError
from backend.repositories.generation_repository import GenerationRepository
from backend.schemas.generation import GenerationRequest, PromptPackageData, PromptPackageResponse, PromptSection


def stable_prompt_hash(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


class PromptCompiler:
    VISUAL_TYPES = {GenerationType.IMAGE, GenerationType.IMAGE_VARIATION, GenerationType.IMAGE_EDIT, GenerationType.VIDEO, GenerationType.VIDEO_SHOT, GenerationType.VIDEO_SEQUENCE, GenerationType.STORYBOARD}
    AUDIO_TYPES = {GenerationType.AUDIO, GenerationType.VOICE, GenerationType.SFX, GenerationType.MUSIC_BRIEF, GenerationType.AUDIO_DESCRIPTION_DRAFT}
    COPY_TYPES = {GenerationType.TEXT, GenerationType.COPY, GenerationType.SCRIPT, GenerationType.CAPTIONS, GenerationType.TRANSCRIPT}

    def compile(self, contract_version, request: GenerationRequest) -> PromptPackageResponse:
        contract = deepcopy(contract_version.payload)
        self._validate_references(request)
        recipe = deepcopy(contract.get("normalized_recipe") or {})
        positive = list(contract.get("positive_constraints") or []) + self._constraints(contract, "hard_constraints") + self._constraints(contract, "soft_constraints")
        negative = list(contract.get("negative_constraints") or []) + list(contract.get("forbidden_changes") or [])
        self._apply_explicit_constraints(recipe, positive)
        character = self._character_for(request.generation_type, contract.get("character"), contract)
        brand = self._brand_for(request.generation_type, contract.get("brand"), contract)
        product = deepcopy(contract.get("product") or contract.get("product_context"))
        sections = self._sections(recipe, contract, character, brand, product, positive, negative)
        package = PromptPackageData(
            task=request.task_id or str(contract.get("task_id") or "generation"),
            objective=str(recipe.get("objective") or contract.get("objective") or request.generation_type.value),
            modality=self._modality(request.generation_type), generation_type=request.generation_type,
            content_type=contract.get("content_type"), platform=contract.get("platform_profile"),
            character=character, brand=brand, product=product,
            scene=deepcopy(recipe.get("scene") or recipe.get("structure") or {}),
            visual=deepcopy(recipe.get("visual") or {}), camera=deepcopy(recipe.get("camera") or {}),
            lighting=deepcopy(recipe.get("lighting") or {}), performance=deepcopy(recipe.get("performance") or {}),
            copy=deepcopy(recipe.get("copy") or {}), audio=deepcopy(recipe.get("audio") or {}),
            accessibility={"requirements": contract.get("accessibility_requirements") or []},
            positive_constraints=positive, negative_constraints=negative,
            forbidden_changes=list(contract.get("forbidden_changes") or []),
            required_evidence=list(contract.get("required_evidence") or []),
            reference_assets=request.references, output_specification=request.output_specification,
            qa_requirements=list(contract.get("qa_requirements") or []),
            provenance_requirements=list(contract.get("provenance_requirements") or ["contract", "recipe", "rules", "provider", "model", "prompt", "references"]),
            sections=sections,
        )
        self.detect_conflicts(package)
        payload = package.model_dump(mode="json")
        return PromptPackageResponse(
            prompt_uid=f"PROMPT_{uuid4().hex}", version=1,
            prompt_hash=stable_prompt_hash(payload), data=package,
        )

    def persist(self, repository: GenerationRepository, job, compiled: PromptPackageResponse, *, change_reason: str = "initial"):
        package = repository.create_prompt_package(job, prompt_uid=compiled.prompt_uid, current_version=1)
        version = repository.add_prompt_version(
            package, version=1, prompt_hash=compiled.prompt_hash,
            payload=compiled.data.model_dump(mode="json"),
            sections=[item.model_dump(mode="json") for item in compiled.data.sections],
            change_reason=change_reason,
        )
        return package, version

    def repair(self, repository, package, data: PromptPackageData, reason: str):
        payload = data.model_dump(mode="json")
        number = package.current_version + 1
        return repository.add_prompt_version(
            package, version=number, prompt_hash=stable_prompt_hash(payload), payload=payload,
            sections=[item.model_dump(mode="json") for item in data.sections], change_reason=reason,
        )

    def detect_conflicts(self, package: PromptPackageData) -> None:
        positives = {self._canonical(item) for item in package.positive_constraints}
        negatives = {self._canonical(item, negative=True) for item in package.negative_constraints}
        collision = sorted(value for value in positives & negatives if value)
        if collision:
            raise PromptConflictError(f"PROMPT_CONFLICT: {', '.join(collision)}")

    @staticmethod
    def _validate_references(request):
        for reference in request.references:
            if not reference.approved or reference.rights_status.upper() in {"PROHIBITED", "PENDING", "UNKNOWN"}:
                raise ReferenceSafetyError(f"Reference {reference.asset_id} is not rights-cleared and approved")

    @staticmethod
    def _constraints(contract, key):
        values = []
        for item in contract.get(key) or []:
            if isinstance(item, dict):
                value = item.get("value")
                values.append({"target": (item.get("affected_fields") or [None])[0], "value": value, "rule_code": item.get("rule_code")})
            else:
                values.append(item)
        return values

    @staticmethod
    def _apply_explicit_constraints(recipe, constraints):
        for constraint in constraints:
            if not isinstance(constraint, dict) or constraint.get("value") is None or not constraint.get("target"): continue
            target = str(constraint["target"]).removeprefix("recipe.")
            current = recipe
            parts = target.split(".")
            for part in parts[:-1]: current = current.setdefault(part, {})
            current[parts[-1]] = constraint["value"]

    def _character_for(self, generation_type, character, contract):
        if not character: return None
        character = deepcopy(character)
        character["id"] = character.get("id") or contract.get("character_id")
        character["version"] = character.get("version") or contract.get("character_version")
        if generation_type in self.AUDIO_TYPES:
            allowed = {"id", "version", "voice", "voice_profile", "language", "dialect", "rights", "consent"}
        elif generation_type in self.COPY_TYPES:
            allowed = {"id", "version", "voice", "tone", "language", "dialect", "persona"}
        else:
            allowed = {"id", "version", "face", "skin", "hair", "eyes", "iris", "body_proportions", "wardrobe", "forbidden_changes", "identity_anchors"}
        return {key: value for key, value in character.items() if key in allowed}

    def _brand_for(self, generation_type, brand, contract):
        if not brand: return None
        brand = deepcopy(brand)
        brand["id"] = brand.get("id") or contract.get("brand_id")
        brand["version"] = brand.get("version") or contract.get("brand_version")
        if generation_type in self.AUDIO_TYPES:
            allowed = {"id", "version", "tone", "voice", "audio"}
        elif generation_type in self.COPY_TYPES:
            allowed = {"id", "version", "tone", "voice", "language", "prohibited_language", "keywords"}
        else:
            allowed = {"id", "version", "palette", "typography", "logo", "symbol_system", "visual_grid", "forbidden_uses", "tone"}
        return {key: value for key, value in brand.items() if key in allowed}

    @staticmethod
    def _sections(recipe, contract, character, brand, product, positive, negative):
        raw = [
            ("recipe", 100, recipe, "soft", "recipe"),
            ("character", 400, character, "hard", "generation_contract"),
            ("brand", 300, brand, "hard", "generation_contract"),
            ("product", 400, product, "hard", "source_of_truth"),
            ("positive_constraints", 500, positive, "hard", "rules"),
            ("negative_constraints", 500, negative, "hard", "rules"),
            ("accessibility", 500, contract.get("accessibility_requirements") or [], "hard", "rules"),
        ]
        return [PromptSection(id=key, priority=priority, content=content, hardness=hardness, source=source, order=index) for index, (key, priority, content, hardness, source) in enumerate(raw) if content]

    @staticmethod
    def _canonical(value, negative=False):
        if isinstance(value, dict):
            value = value.get("value") or value.get("message") or value.get("target") or ""
        text = " ".join(str(value).strip().lower().replace("_", " ").split())
        if negative:
            for prefix in ("no ", "avoid ", "do not ", "without "):
                if text.startswith(prefix): text = text[len(prefix):]
        return text

    @staticmethod
    def _modality(generation_type):
        if generation_type in PromptCompiler.VISUAL_TYPES:
            return "video" if generation_type in {GenerationType.VIDEO, GenerationType.VIDEO_SHOT, GenerationType.VIDEO_SEQUENCE} else ("storyboard" if generation_type is GenerationType.STORYBOARD else "image")
        if generation_type in PromptCompiler.AUDIO_TYPES: return "audio"
        return "text"
