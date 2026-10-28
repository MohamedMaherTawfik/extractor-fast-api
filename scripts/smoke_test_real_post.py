"""Smoke test script executing end-to-end Social Content Intelligence on a real normalized post."""
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from uuid import UUID
from backend.db.session import session_scope
from backend.db.models.social_inventory import SocialInventoryItem
from backend.social_intelligence.worker import social_intelligence_worker
from backend.social_intelligence.excel_exporter import export_intelligence_workbook
from backend.social_intelligence.creator_dna import aggregate_creator_dna
from backend.social_intelligence.creative_generator import (
    GenerationRequest,
    generate_creative_recommendations,
)
from backend.db.models.social_intelligence import (
    ContentAnalysisJob,
    ContentTranscript,
    ContentHookAnalysis,
    ContentCopyAnalysis,
    ContentNarrativeAnalysis,
    ContentVideoAnalysis,
    CreatorIntelligence,
    CreativeRecommendation,
)

def run_smoke_test():
    print("=== STARTING SOCIAL INTELLIGENCE SMOKE TEST ===")
    target_uuid = UUID("24ae372693ff48c0a79a02cc5c43c8d5")

    with session_scope() as session:
        item = session.query(SocialInventoryItem).filter_by(uuid=target_uuid).first()
        if not item:
            print(f"Error: item {target_uuid} not found in database.")
            return

        author_name = (item.author or {}).get("username", "unknown")
        print(f"Loaded item: {item.uuid} (Platform: {item.platform}, Author: {author_name})")
        print(f"Caption: {item.caption[:60]}...")
        if item.media:
            print(f"Media count: {len(item.media)}, First URL prefix: {item.media[0].get('url', '')[:50]}")

        # Create or reuse job
        job = ContentAnalysisJob(
            item_uuid=target_uuid,
            status="QUEUED",
            stage="QUEUED",
            progress_percent=0.0,
        )
        session.add(job)
        session.flush()
        job_uuid = job.uuid

    # Use worker to process the item directly
    worker = social_intelligence_worker
    print(f"\nExecuting worker._execute_job({job_uuid}) synchronously...")
    worker._execute_job(str(job_uuid))

    # Inspect results in DB
    print("\nVerifying database records created:")
    with session_scope() as session:
        job = session.query(ContentAnalysisJob).filter_by(item_uuid=target_uuid).first()
        print(f"  Job Status: {job.status if job else 'None'}, Error: {job.error_message}")
        
        transcript = session.query(ContentTranscript).filter_by(item_uuid=target_uuid).first()
        print(f"  Transcript: {transcript.language if transcript else 'None'}, Segments: {len(transcript.segments) if transcript else 0}")
        if transcript and transcript.full_text:
            print(f"    Sample text: {transcript.full_text[:80]}...")

        hook = session.query(ContentHookAnalysis).filter_by(item_uuid=target_uuid).first()
        print(f"  Hook Analysis: Hook Types={hook.hook_types if hook else 'None'}, Heuristic Score={hook.heuristic_score if hook else 'None'}")
        if hook:
            spk = (hook.spoken_hook or {}).get("exact_text")
            vis = (hook.visual_hook or {}).get("first_frame_composition")
            print(f"    Spoken Hook: {spk[:60] if spk else 'None'}")
            print(f"    Visual Hook: {vis[:60] if vis else 'None'}")

        copy = session.query(ContentCopyAnalysis).filter_by(item_uuid=target_uuid).first()
        print(f"  Copy Analysis: Tone={copy.tone_of_voice if copy else 'None'}, CTA={copy.cta_text if copy else 'None'}")

        narrative = session.query(ContentNarrativeAnalysis).filter_by(item_uuid=target_uuid).first()
        print(f"  Narrative Analysis: Structure={narrative.narrative_pattern if narrative else 'None'}, Stages={len(narrative.stages) if narrative and narrative.stages else 0}")

        video = session.query(ContentVideoAnalysis).filter_by(item_uuid=target_uuid).first()
        print(f"  Video Analysis: Aspect={video.aspect_ratio if video else 'None'}, Scenes={len(video.scenes) if video else 0}, Pace={video.editing_pace if video else 'None'}")

        # Test Creator DNA synthesis
        print("\nSynthesizing Creator DNA for eldaheeh...")
        creator_dna = aggregate_creator_dna(session, "instagram", "eldaheeh")
        print(f"  Creator DNA Sample Size: {creator_dna.sample_size if creator_dna else 'None'}")
        if creator_dna:
            eng = creator_dna.engagement_observations or {}
            print(f"  Average Views: {eng.get('average_views')}, Interaction Rate: {eng.get('observed_like_rate_pct')}%")
            print(f"  Top Hook Types: {creator_dna.common_hook_types}")

        # Test Creative Generation
        print("\nGenerating AI Creative Recommendations...")
        req = GenerationRequest(
            item_uuid=target_uuid,
            creator_username="eldaheeh",
            output_type="hook_variations",
            topic_context="الدحيح أحمد زويل",
        )
        recs = generate_creative_recommendations(session=session, request=req)
        print(f"  Generated {len(recs)} creative recommendations:")
        for r in recs:
            hook_txt = r.suggested_hook or r.suggested_caption or "N/A"
            print(f"    - [{r.output_type}] {hook_txt[:60]}... (AI: {r.is_ai_generated})")

        # Test Exporting full 14-Sheet Excel Workbook
        print(f"\nGenerating 14-Sheet Excel Workbook for target_uuid and eldaheeh...")
        out_file, filename = export_intelligence_workbook(
            session=session,
            item_uuids=[target_uuid],
            creator_username="eldaheeh",
        )
        print(f"  Generated file: {filename} at {out_file} (Size: {out_file.stat().st_size} bytes)")

        # Verify sheets in workbook
        import openpyxl
        wb = openpyxl.load_workbook(str(out_file))
        print(f"  Total sheets generated: {len(wb.sheetnames)}")
        for idx, name in enumerate(wb.sheetnames, 1):
            sheet = wb[name]
            print(f"    Sheet {idx:02d}: '{name}' ({sheet.max_row} rows, {sheet.max_column} cols)")

    print("\n=== SMOKE TEST COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_smoke_test()
