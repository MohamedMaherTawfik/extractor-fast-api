"""Deterministic first-pass QA gates with explicit UNKNOWN semantics."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from backend.core.enums import QACategory, QAResultStatus
from backend.schemas.generation import QAResultData
from backend.core.paths import paths
from hashlib import sha256


class CharacterConsistencyService:
    def check(self, package, metadata):
        character = package.character or {}
        expected = ((character.get("hair") or {}).get("color") if isinstance(character.get("hair"), dict) else None)
        actual = metadata.get("character_hair_color")
        if expected and actual and str(expected).lower() != str(actual).lower():
            return QAResultData(check_id="CHARACTER_HAIR", category=QACategory.CHARACTER, result=QAResultStatus.FAIL, severity="high", evidence={"expected": expected, "actual": actual}, message="CHARACTER_QA_FAILED: hair color drift", suggested_action="reference_adjustment")
        if character and expected and actual is None:
            return QAResultData(check_id="CHARACTER_IDENTITY", category=QACategory.CHARACTER, result=QAResultStatus.UNKNOWN, severity="high", evidence={"character_version": character.get("version")}, message="Character observation unavailable; approval requires review")
        return QAResultData(check_id="CHARACTER_IDENTITY", category=QACategory.CHARACTER, result=QAResultStatus.PASS, severity="info", evidence={"character_version": character.get("version")}, message="Character anchors matched available observations" if character else "No character required")


class TemporalConsistencyService:
    FIELDS = ("wardrobe", "hair", "product_state", "background_state", "lighting", "screen_direction", "camera_axis")

    def check(self, metadata):
        states = metadata.get("shot_states") or []
        for previous, current in zip(states, states[1:]):
            for field in self.FIELDS:
                if field in previous and field in current and previous[field] != current[field]:
                    return QAResultData(check_id="TEMPORAL_CONTINUITY", category=QACategory.CONTINUITY, result=QAResultStatus.FAIL, severity="high", evidence={"field": field, "before": previous[field], "after": current[field]}, message=f"Continuity changed unexpectedly: {field}", suggested_action="human_review")
        return QAResultData(check_id="TEMPORAL_CONTINUITY", category=QACategory.CONTINUITY, result=QAResultStatus.PASS if states else QAResultStatus.UNKNOWN, severity="medium", evidence={"shots": len(states)}, message="Continuity observations checked" if states else "Continuity observations unavailable")


class GenerationQAPipeline:
    def __init__(self, repository) -> None:
        self.repository = repository
        self.character = CharacterConsistencyService()
        self.temporal = TemporalConsistencyService()

    def run(self, job, asset_version, package, contract_payload):
        now = datetime.now(UTC)
        run = self.repository.create_qa_run(
            qa_uid=f"GQA_{uuid4().hex}", job_id=job.id, asset_version_id=asset_version.id,
            status="running", started_at=now,
        )
        metadata = asset_version.metadata_payload or {}
        checks = [self._technical(asset_version, package), self._schema(job, metadata), self.character.check(package, metadata),
                  self._product(package, metadata), self._brand(package, metadata),
                  self._visual(job.modality, metadata), self._copy(package, metadata), self._audio(job.modality, metadata),
                  self._accessibility(job, contract_payload, metadata),
                  self._rights(package), self._provenance(asset_version)]
        if job.modality == "video": checks.append(self.temporal.check(metadata))
        for result in checks:
            self.repository.add_qa_result(run, **result.model_dump())
        failures = [item for item in checks if item.result is QAResultStatus.FAIL]
        unknown_required = [item for item in checks if item.result is QAResultStatus.UNKNOWN and item.severity in {"high", "critical"}]
        run.status = "failed" if failures else ("human_review" if unknown_required else "passed")
        run.completed_at = datetime.now(UTC)
        asset_version.qa_status = run.status
        return run, checks

    @staticmethod
    def _technical(asset, package):
        expected = package.output_specification
        issues = []
        try:
            source = paths.resolve_under(paths.project_root, asset.relative_path)
            if not source.is_file(): issues.append("missing file")
            elif sha256(source.read_bytes()).hexdigest() != asset.checksum: issues.append("checksum")
        except ValueError:
            issues.append("unsafe path")
        if asset.file_size <= 0: issues.append("empty file")
        if expected.width and asset.width != expected.width: issues.append("width")
        if expected.height and asset.height != expected.height: issues.append("height")
        if expected.aspect_ratio and asset.aspect_ratio != expected.aspect_ratio: issues.append("aspect ratio")
        if expected.duration_seconds and (asset.duration_seconds is None or abs(expected.duration_seconds - asset.duration_seconds) > 0.5): issues.append("duration")
        return QAResultData(check_id="TECHNICAL_OUTPUT", category=QACategory.TECHNICAL, result=QAResultStatus.FAIL if issues else QAResultStatus.PASS, severity="high", evidence={"issues": issues, "checksum": asset.checksum}, message="Technical output invalid" if issues else "File, size, format, dimensions, and checksum checks passed", suggested_action="retry" if issues else None, automatically_repairable=bool(issues))

    @staticmethod
    def _schema(job, metadata):
        required = {
            "copy": "copy_uid", "script": "script_uid", "storyboard": "shots",
            "captions": "cues", "transcript": "segments",
        }.get(job.generation_type.value)
        failed = bool(required and required not in metadata)
        return QAResultData(check_id="OUTPUT_SCHEMA", category=QACategory.SCHEMA, result=QAResultStatus.FAIL if failed else QAResultStatus.PASS, severity="high", evidence={"required": required}, message="Structured output schema is incomplete" if failed else "Output schema checked")

    @staticmethod
    def _visual(modality, metadata):
        if modality not in {"image", "video", "storyboard"}:
            return QAResultData(check_id="VISUAL_RISK", category=QACategory.VISUAL, result=QAResultStatus.PASS, severity="info", message="Visual QA not applicable")
        risks = [key for key in ("anatomy_error", "text_rendering_error", "logo_rendering_error", "safe_zone_violation", "color_drift") if metadata.get(key)]
        return QAResultData(check_id="VISUAL_RISK", category=QACategory.VISUAL, result=QAResultStatus.FAIL if risks else QAResultStatus.PASS, severity="high", evidence={"risks": risks}, message="Visual QA risks detected" if risks else "Available visual checks passed", suggested_action="regional_repair" if risks else None, automatically_repairable=bool(risks))

    @staticmethod
    def _product(package, metadata):
        product = package.product or {}
        expected = product.get("label") or product.get("name")
        actual = metadata.get("product_label")
        failed = bool(expected and actual and str(expected) != str(actual))
        unknown = bool(product and expected and actual is None)
        return QAResultData(check_id="PRODUCT_INTEGRITY", category=QACategory.PRODUCT, result=QAResultStatus.FAIL if failed else (QAResultStatus.UNKNOWN if unknown else QAResultStatus.PASS), severity="high" if product else "info", evidence={"expected": expected, "actual": actual}, message="Product label or identity changed" if failed else ("Product observation unavailable" if unknown else "Product integrity checked"))

    @staticmethod
    def _brand(package, metadata):
        brand = package.brand or {}
        palette = [str(value).lower() for value in brand.get("palette", [])]
        actual = str(metadata.get("background_color") or "").lower()
        failed = bool(palette and actual and actual not in palette)
        unknown = bool(brand and palette and not actual)
        return QAResultData(check_id="BRAND_PALETTE", category=QACategory.BRAND, result=QAResultStatus.FAIL if failed else (QAResultStatus.UNKNOWN if unknown else QAResultStatus.PASS), severity="high" if brand else "info", evidence={"palette": palette, "actual": actual}, message="BRAND_QA_FAILED: unapproved palette value" if failed else ("Brand color observation unavailable" if unknown else "Brand constraints checked"))

    @staticmethod
    def _copy(package, metadata):
        generated_claims = set(metadata.get("claims") or [])
        approved = set((package.product or {}).get("approved_claims") or (package.product or {}).get("approved_facts") or [])
        unsupported = sorted(generated_claims - approved) if generated_claims else []
        return QAResultData(check_id="COPY_CLAIMS", category=QACategory.COPY, result=QAResultStatus.FAIL if unsupported else QAResultStatus.PASS, severity="high", evidence={"unsupported_claims": unsupported}, message="UNSUPPORTED_CLAIM" if unsupported else "Generated claims are supported", suggested_action="rewrite" if unsupported else None, automatically_repairable=bool(unsupported))

    @staticmethod
    def _audio(modality, metadata):
        if modality != "audio":
            return QAResultData(check_id="AUDIO_VALIDITY", category=QACategory.AUDIO, result=QAResultStatus.PASS, severity="info", message="Audio QA not applicable to primary asset")
        failed = bool(metadata.get("clipped") or metadata.get("invalid_audio"))
        return QAResultData(check_id="AUDIO_VALIDITY", category=QACategory.AUDIO, result=QAResultStatus.FAIL if failed else QAResultStatus.PASS, severity="high", evidence={"clipped": metadata.get("clipped")}, message="Audio clipping or invalid stream detected" if failed else "Audio stream checks passed")

    @staticmethod
    def _accessibility(job, contract, metadata):
        requirements = contract.get("accessibility_requirements") or []
        joined = " ".join(str(item).lower() for item in requirements)
        captions_required = "caption" in joined or bool(contract.get("captions_required"))
        captions_present = bool(metadata.get("captions_present") or job.generation_type.value == "captions")
        transcript_required = "transcript" in joined
        audio_description_required = "audio description" in joined or "audio_description" in joined
        alt_required = "alt text" in joined or "alt_text" in joined
        missing = []
        if captions_required and job.modality == "video" and not captions_present: missing.append("captions")
        if transcript_required and job.modality == "video" and not metadata.get("transcript_present"): missing.append("transcript")
        if audio_description_required and job.modality == "video" and not metadata.get("audio_description_present"): missing.append("audio_description")
        if alt_required and job.modality == "image" and not metadata.get("alt_text_present"): missing.append("alt_text")
        return QAResultData(check_id="ACCESSIBILITY_PACKAGE", category=QACategory.ACCESSIBILITY, result=QAResultStatus.FAIL if missing else QAResultStatus.PASS, severity="high" if any((captions_required, transcript_required, audio_description_required, alt_required)) else "info", evidence={"missing": missing}, message=f"ACCESSIBILITY_QA_FAILED: required {', '.join(missing)} missing" if missing else "Accessibility requirements checked")

    @staticmethod
    def _rights(package):
        invalid = [item.asset_id for item in package.reference_assets if not item.approved or item.rights_status.upper() != "CLEARED"]
        return QAResultData(check_id="REFERENCE_RIGHTS", category=QACategory.RIGHTS, result=QAResultStatus.FAIL if invalid else QAResultStatus.PASS, severity="critical", evidence={"invalid_references": invalid}, message="Reference rights blocked" if invalid else "All references are approved and rights-cleared")

    @staticmethod
    def _provenance(asset):
        passed = bool(asset.provenance and asset.prompt_hash and asset.provider and asset.model_version)
        return QAResultData(check_id="PROVENANCE", category=QACategory.PROVENANCE, result=QAResultStatus.PASS if passed else QAResultStatus.FAIL, severity="high", evidence={"prompt_hash": asset.prompt_hash}, message="Provenance captured" if passed else "Provenance is incomplete")
