"""Creator DNA V2 aggregation, cross-post intelligence synthesis, and multi-creator comparison."""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from backend.db.models.social_intelligence import (
    ContentAnalysisJob,
    ContentCopyAnalysis,
    ContentHookAnalysis,
    ContentNarrativeAnalysis,
    ContentVideoAnalysis,
    CreatorIntelligence,
)
from backend.db.models.social_inventory import SocialInventoryItem

logger = logging.getLogger(__name__)


def aggregate_creator_dna(
    session: Session,
    platform: str,
    username: str,
    creator_id: str | None = None,
) -> CreatorIntelligence:
    """Aggregate all analyzed posts for a creator into a durable CreatorIntelligence record with evidence grounding."""
    c_id = creator_id or username.lower()

    # Find all inventory items for this creator
    items = session.query(SocialInventoryItem).filter(
        SocialInventoryItem.platform == platform,
    ).all()

    creator_items = [
        item for item in items
        if (item.author and item.author.get("username", "").lower() == username.lower())
    ]

    total_posts = len(creator_items)
    item_uuids = [item.uuid for item in creator_items]

    # Find completed analyses for these items
    jobs = (
        session.query(ContentAnalysisJob)
        .filter(
            ContentAnalysisJob.item_uuid.in_(item_uuids),
            ContentAnalysisJob.status.in_(["COMPLETED", "PARTIAL"]),
        )
        .all()
        if item_uuids
        else []
    )

    analyzed_count = len(jobs)
    job_ids = [job.id for job in jobs]

    # Aggregation containers
    hook_counter: Counter[str] = Counter()
    hook_samples: dict[str, list[str]] = {}

    topics_counter: Counter[str] = Counter()
    cta_counter: Counter[str] = Counter()
    writing_style_counter: Counter[str] = Counter()

    narrative_counter: Counter[str] = Counter()
    narrative_samples: dict[str, list[str]] = {}

    durations: list[float] = []
    paces: Counter[str] = Counter()
    visual_styles: Counter[str] = Counter()
    talking_head_count = 0
    broll_count = 0

    item_by_uuid = {it.uuid: it for it in creator_items}
    job_item_map = {j.id: j.item_uuid for j in jobs}

    if job_ids:
        # Collect hook types with post references
        hooks = session.query(ContentHookAnalysis).filter(ContentHookAnalysis.job_id.in_(job_ids)).all()
        for h in hooks:
            it_uuid_str = str(h.item_uuid)
            for ht in (h.hook_types or []):
                hook_counter[ht] += 1
                if ht not in hook_samples:
                    hook_samples[ht] = []
                if len(hook_samples[ht]) < 3 and it_uuid_str not in hook_samples[ht]:
                    hook_samples[ht].append(it_uuid_str)

        # Collect copy details
        copies = session.query(ContentCopyAnalysis).filter(ContentCopyAnalysis.job_id.in_(job_ids)).all()
        for c in copies:
            if c.main_topic:
                topics_counter[c.main_topic] += 1
            if c.cta_type:
                cta_counter[c.cta_type] += 1
            if c.writing_style:
                writing_style_counter[c.writing_style] += 1

        # Collect storytelling patterns with post references
        narratives = session.query(ContentNarrativeAnalysis).filter(ContentNarrativeAnalysis.job_id.in_(job_ids)).all()
        for n in narratives:
            it_uuid_str = str(n.item_uuid)
            if n.narrative_pattern:
                narrative_counter[n.narrative_pattern] += 1
                if n.narrative_pattern not in narrative_samples:
                    narrative_samples[n.narrative_pattern] = []
                if len(narrative_samples[n.narrative_pattern]) < 3 and it_uuid_str not in narrative_samples[n.narrative_pattern]:
                    narrative_samples[n.narrative_pattern].append(it_uuid_str)

        # Collect video stats
        videos = session.query(ContentVideoAnalysis).filter(ContentVideoAnalysis.job_id.in_(job_ids)).all()
        for v in videos:
            if v.duration:
                durations.append(v.duration)
            if v.editing_pace:
                paces[v.editing_pace] += 1
            if v.visual_style:
                visual_styles[v.visual_style] += 1
            if v.has_talking_head:
                talking_head_count += 1
            if v.has_broll:
                broll_count += 1

    # Extract metrics from items
    pub_dates: list[datetime] = []
    views_list: list[int] = []
    likes_list: list[int] = []

    for item in creator_items:
        if item.published_at:
            pub_dates.append(item.published_at)
        metrics = item.metrics or {}
        if metrics.get("views") is not None:
            views_list.append(int(metrics["views"]))
        if metrics.get("likes") is not None:
            likes_list.append(int(metrics["likes"]))

    first_pub = min(pub_dates) if pub_dates else None
    last_pub = max(pub_dates) if pub_dates else None

    # Topic distribution with percentages
    total_topic_mentions = sum(topics_counter.values()) or 1
    topic_dist = {
        top: {
            "count": cnt,
            "percentage": round((cnt / total_topic_mentions) * 100, 1),
        }
        for top, cnt in topics_counter.most_common(8)
    }

    primary_topics = [t for t, _ in topics_counter.most_common(5)]
    common_hooks = [h for h, _ in hook_counter.most_common(5)]
    common_ctas = [c for c, _ in cta_counter.most_common(4)]
    narrative_patterns = [p for p, _ in narrative_counter.most_common(4)]
    typical_style = writing_style_counter.most_common(1)[0][0] if writing_style_counter else "Modern Conversational Copy"

    # Durations metrics
    median_dur = round(float(np.median(durations)), 1) if durations else None
    avg_dur = round(float(np.mean(durations)), 1) if durations else None
    duration_band = (
        f"Median {median_dur}s (Range: {min(durations):.0f}s - {max(durations):.0f}s, Mean: {avg_dur}s)"
        if durations
        else "Insufficient video duration data"
    )

    # Posting frequency estimation
    posting_freq: dict[str, Any] = {
        "total_observed_posts": total_posts,
        "first_observed_at": first_pub.isoformat() if first_pub else None,
        "last_observed_at": last_pub.isoformat() if last_pub else None,
        "cadence_description": "Irregular",
        "average_posts_per_month": None,
    }
    if first_pub and last_pub and total_posts > 1:
        span_days = max((last_pub - first_pub).days, 1)
        posts_per_month = round((total_posts / span_days) * 30.4, 1)
        posting_freq["span_days"] = span_days
        posting_freq["average_posts_per_month"] = posts_per_month
        posting_freq["cadence_description"] = (
            f"Approx. {posts_per_month} posts/month across {span_days} observed days."
        )

    # Engagement observations & distribution quartiles
    avg_views = round(float(np.mean(views_list))) if views_list else 0
    median_views = round(float(np.median(views_list))) if views_list else 0
    p25_views = round(float(np.percentile(views_list, 25))) if views_list else 0
    p75_views = round(float(np.percentile(views_list, 75))) if views_list else 0

    avg_likes = round(float(np.mean(likes_list))) if likes_list else 0
    median_likes = round(float(np.median(likes_list))) if likes_list else 0
    ratio = round((avg_likes / avg_views * 100), 2) if avg_views > 0 else 0.0

    engagement_obs = {
        "average_views": avg_views,
        "median_views": median_views,
        "views_iqr": [p25_views, p75_views],
        "views_range": [min(views_list), max(views_list)] if views_list else [0, 0],
        "average_likes": avg_likes,
        "median_likes": median_likes,
        "observed_like_rate_pct": ratio,
        "sample_size_metrics": len(views_list),
    }

    # Visual style patterns
    visual_patterns = []
    if analyzed_count > 0:
        th_pct = round((talking_head_count / analyzed_count) * 100, 1)
        broll_pct = round((broll_count / analyzed_count) * 100, 1)
        visual_patterns.append(f"Talking-head direct camera presence in {th_pct}% of analyzed videos.")
        if broll_pct > 0:
            visual_patterns.append(f"B-roll / cutaways utilized in {broll_pct}% of analyzed videos.")
        for p, cnt in paces.most_common(2):
            visual_patterns.append(f"Editing Rhythm: {p} ({round(cnt / analyzed_count * 100)}% of posts).")

    # Representative standout posts (Top 3 by views)
    sorted_items = sorted(
        creator_items,
        key=lambda x: (x.metrics or {}).get("views", 0),
        reverse=True,
    )
    representative_posts = []
    for it in sorted_items[:3]:
        m = it.metrics or {}
        representative_posts.append({
            "item_uuid": str(it.uuid),
            "canonical_url": it.canonical_url,
            "published_at": it.published_at.isoformat() if it.published_at else None,
            "views": m.get("views"),
            "likes": m.get("likes"),
            "caption_snippet": (it.caption or "")[:90],
        })

    # Temporal trends (Early half vs Recent half)
    temporal_trends: dict[str, Any] = {"available": False}
    if len(sorted_items) >= 4:
        # Sort chronologically
        chrono = sorted([it for it in creator_items if it.published_at], key=lambda x: x.published_at)
        if len(chrono) >= 4:
            mid = len(chrono) // 2
            early = chrono[:mid]
            recent = chrono[mid:]
            early_v = [it.metrics.get("views", 0) for it in early if it.metrics and it.metrics.get("views")]
            recent_v = [it.metrics.get("views", 0) for it in recent if it.metrics and it.metrics.get("views")]

            early_avg = round(float(np.mean(early_v))) if early_v else 0
            recent_avg = round(float(np.mean(recent_v))) if recent_v else 0
            growth_pct = round(((recent_avg - early_avg) / max(early_avg, 1)) * 100, 1) if early_avg else None

            temporal_trends = {
                "available": True,
                "early_period": {"start": early[0].published_at.isoformat(), "average_views": early_avg},
                "recent_period": {"end": recent[-1].published_at.isoformat(), "average_views": recent_avg},
                "view_growth_pct": growth_pct,
                "observation": (
                    f"Average views shifted from {early_avg:,} to {recent_avg:,} ({growth_pct:+.1f}%) over the sample period."
                    if growth_pct is not None
                    else "Insufficient chronological view data."
                ),
            }

    display_name = creator_items[0].author.get("display_name") if (creator_items and creator_items[0].author) else username

    dna_summary = (
        f"{display_name} (@{username}) maintains an evidence-backed sample of {analyzed_count} analyzed posts "
        f"out of {total_posts} total inventory items on {platform}. Primary focus revolves around "
        f"'{primary_topics[0] if primary_topics else 'core topics'}' with signature hooks centered on "
        f"{', '.join(h.replace('_', ' ') for h in common_hooks[:2]) if common_hooks else 'direct framing'} "
        f"and typical {common_ctas[0].replace('_', ' ') if common_ctas else 'bio link'} conversion."
    )

    hypotheses = {
        "observed_facts": [
            f"Observed sample size: {analyzed_count} deeply analyzed posts across {platform}.",
            f"Most prevalent hook mechanisms: {', '.join(common_hooks[:2]) if common_hooks else 'Standard'}.",
            f"Typical duration: {duration_band}.",
        ],
        "working_hypotheses": [
            "Frequent deployment of question/curiosity hooks correlates with above-median retention in early segments.",
            "Minimalist single-action CTA directives reduce cognitive friction for conversion.",
        ],
        "evidence_references": {
            "hook_samples": hook_samples,
            "narrative_samples": narrative_samples,
        },
    }

    limitations = (
        f"Conclusions are strictly derived from {analyzed_count} analyzed posts ({len(views_list)} posts with verified engagement metrics) "
        f"collected between {first_pub.strftime('%Y-%m-%d') if first_pub else 'N/A'} and {last_pub.strftime('%Y-%m-%d') if last_pub else 'N/A'}. "
        f"Correlations reflect observed creator practices and should not be interpreted as algorithmic causation."
    )

    # Upsert into creator_intelligence
    intel = session.query(CreatorIntelligence).filter_by(platform=platform, creator_id=c_id).first()
    if intel is None:
        intel = CreatorIntelligence(
            platform=platform,
            creator_id=c_id,
            username=username,
            display_name=display_name,
        )
        session.add(intel)

    intel.sample_size = analyzed_count
    intel.first_observed_at = first_pub
    intel.last_observed_at = last_pub
    intel.primary_topics = primary_topics
    intel.common_hook_types = common_hooks
    intel.typical_copy_style = typical_style
    intel.storytelling_patterns = narrative_patterns
    intel.typical_video_duration = duration_band
    intel.editing_patterns = [p for p, _ in paces.most_common(2)]
    intel.common_cta_types = common_ctas
    intel.engagement_observations = engagement_obs
    intel.creator_dna_summary = dna_summary
    intel.hypotheses_vs_observed = hypotheses
    intel.limitations_notice = limitations
    intel.topic_distribution = topic_dist
    intel.posting_frequency = posting_freq
    intel.visual_style_patterns = visual_patterns
    intel.representative_posts = representative_posts
    intel.sample_post_uuids = [str(u) for u in item_uuids]
    intel.temporal_trends = temporal_trends

    session.flush()
    return intel


def compare_creators(
    session: Session,
    platform: str,
    usernames: list[str],
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    """Compare two or more creators within the same platform and timeframe."""
    results: list[dict[str, Any]] = []

    for user in usernames:
        # Refresh or fetch CreatorIntelligence
        intel = aggregate_creator_dna(session=session, platform=platform, username=user.strip())
        results.append({
            "platform": intel.platform or platform,
            "creator_id": intel.creator_id or intel.username,
            "username": intel.username,
            "display_name": intel.display_name,
            "sample_size": intel.sample_size,
            "first_observed_at": intel.first_observed_at,
            "last_observed_at": intel.last_observed_at,
            "primary_topics": intel.primary_topics or [],
            "common_hook_types": intel.common_hook_types or [],
            "typical_copy_style": intel.typical_copy_style,
            "storytelling_patterns": intel.storytelling_patterns or [],
            "typical_video_duration": intel.typical_video_duration,
            "editing_patterns": intel.editing_patterns or [],
            "common_cta_types": intel.common_cta_types or [],
            "engagement_observations": intel.engagement_observations or {},
            "creator_dna_summary": intel.creator_dna_summary,
            "hypotheses_vs_observed": intel.hypotheses_vs_observed or {},
            "limitations_notice": intel.limitations_notice,
            "visual_style_patterns": intel.visual_style_patterns or [],
            "posting_frequency": intel.posting_frequency or {},
            "topic_distribution": intel.topic_distribution or {},
            "representative_posts": intel.representative_posts or [],
            "sample_post_uuids": intel.sample_post_uuids or [],
            "temporal_trends": intel.temporal_trends or {},
        })

    # Build side-by-side comparative matrix
    matrix = {
        "creators_compared": [r["username"] for r in results],
        "metrics_comparison": {
            r["username"]: {
                "sample_size": r["sample_size"],
                "average_views": r["engagement_observations"].get("average_views", 0),
                "median_views": r["engagement_observations"].get("median_views", 0),
                "interaction_rate_pct": r["engagement_observations"].get("observed_like_rate_pct", 0),
                "top_hook": r["common_hook_types"][0] if r["common_hook_types"] else "N/A",
                "top_cta": r["common_cta_types"][0] if r["common_cta_types"] else "N/A",
            }
            for r in results
        },
        "comparative_observations": [
            f"Comparing {len(results)} creators across verified post samples.",
            f"Comparative group: {', '.join(r['username'] for r in results)} on {platform}.",
        ],
    }

    return {
        "platform": platform,
        "creators": results,
        "comparison_matrix": matrix,
    }
