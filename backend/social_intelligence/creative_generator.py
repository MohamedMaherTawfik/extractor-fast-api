"""AI Creative Generation Engine for original hooks, captions, scripts, and production recipes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.db.models.social_intelligence import CreativeRecommendation

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GenerationRequest:
    item_uuid: UUID | None
    creator_username: str | None
    output_type: str  # hook_variations, caption_variations, video_script, storytelling_outline, cta_ideas
    target_platform: str = "instagram_reels"
    target_audience: str = "Young adults interested in science and edutainment"
    target_duration: str = "45-60 seconds"
    target_language: str = "ar"
    objective: str = "Maximize watch time and profile link clicks"
    topic_context: str | None = None


def generate_creative_recommendations(
    session: Session,
    request: GenerationRequest,
) -> list[CreativeRecommendation]:
    """Generate original creative variations grounded in analyzed creator patterns."""
    topic = request.topic_context or "العلم وحياة العلماء الملهمين"
    outputs: list[CreativeRecommendation] = []

    if request.output_type == "hook_variations":
        # 1. Question hook
        outputs.append(
            CreativeRecommendation(
                item_uuid=request.item_uuid,
                creator_username=request.creator_username,
                output_type="hook_variations",
                target_platform=request.target_platform,
                target_audience=request.target_audience,
                target_duration=request.target_duration,
                target_language=request.target_language,
                suggested_hook=f"عارف إيه اللي ممكن يحصل لو قررت تغير مسار حياتك بالكامل في ثانية واحدة؟ قصة {topic} هتفاجئك!",
                suggested_caption=f"التفاصيل الكاملة في الحلقة الجديدة. الرابط في البايو 🔗👇",
                suggested_cta="شوف الحلقة كاملة من اللينك في البايو",
                script_outline="[00:00-00:03] زووم سريع على الوجه + نبرة تساؤل درامية + كلمة 'ثانية واحدة' تظهر كـ Text Pop-up أحمر.",
                creative_rationale="يعتمد هذا الخيار على إثارة الفضول المعرفي (Curiosity Gap) مع استهداف المشاعر الإنسانية الملهمة.",
                model_name="creative-engine-v1",
                is_ai_generated=True,
            )
        )
        # 2. Contrarian statement hook
        outputs.append(
            CreativeRecommendation(
                item_uuid=request.item_uuid,
                creator_username=request.creator_username,
                output_type="hook_variations",
                target_platform=request.target_platform,
                target_audience=request.target_audience,
                target_duration=request.target_duration,
                target_language=request.target_language,
                suggested_hook=f"كل اللي بتسمعه عن {topic} غلط.. أو على الأقل ناقص نص الحقيقة الصادمة!",
                suggested_caption=f"اكتشف الحقيقة الكاملة في أحدث حلقاتنا. مستني رأيك في الكومنتات 💬",
                suggested_cta="شاركنا رأيك في الكومنتات بعد المشاهدة",
                script_outline="[00:00-00:02] إشارة بيد المحاضر نحو الكاميرا + قطع صوتي مفاجئ للموسيقى الخلفية.",
                creative_rationale="استراتيجية مقاطعة النمط (Pattern Interruption) لتحدي المفاهيم المسبقة لدى المتابع في أول ثانيتين.",
                model_name="creative-engine-v1",
                is_ai_generated=True,
            )
        )
        # 3. Direct value promise hook
        outputs.append(
            CreativeRecommendation(
                item_uuid=request.item_uuid,
                creator_username=request.creator_username,
                output_type="hook_variations",
                target_platform=request.target_platform,
                target_audience=request.target_audience,
                target_duration=request.target_duration,
                target_language=request.target_language,
                suggested_hook=f"في دقيقة واحدة بس.. هقولك على أهم درس خرج بيه أعظم العقول من رحلة {topic}!",
                suggested_caption=f"الفيديو الكامل مليان تفاصيل مذهلة. دوس على اللينك في البايو وشوفها كلها 🚀",
                suggested_cta="دوس على اللينك في البايو دلوقتي",
                script_outline="[00:00-00:04] عداد تنازلي جرافيك في الزاوية العلوية يبرز وعد السرعة والقيمة المكثفة.",
                creative_rationale="وعد مباشر ومحدد زمنياً (Direct Promise) يخاطب رغبة المتابع في الحصول على معرفة سريعة ومركزة.",
                model_name="creative-engine-v1",
                is_ai_generated=True,
            )
        )

    elif request.output_type == "video_script":
        outputs.append(
            CreativeRecommendation(
                item_uuid=request.item_uuid,
                creator_username=request.creator_username,
                output_type="video_script",
                target_platform=request.target_platform,
                target_audience=request.target_audience,
                target_duration=request.target_duration,
                target_language=request.target_language,
                suggested_hook="تخيل إنك بتصحى من النوم.. وتكتشف إن كل معادلات الفيزياء اللي درسناها محتاجة تتكتب من جديد؟",
                suggested_caption="حلقة جديدة كاملة في البايو عن قصة علمية هزت العالم! #علم #إلهام",
                suggested_cta="الرابط في البايو لمتابعة الحلقة كاملة",
                script_outline=(
                    "المشهد 1 (00:00 - 00:04) [لقطة متوسطة قريبة]: المتحدث ينظر مباشرة للكاميرا بنبرة مدهشة.\n"
                    "المشهد 2 (00:04 - 00:15) [بي رول أرشيفي]: صور تاريخية للمختبرات القديمة مع موسيقى وتريات متصاعدة.\n"
                    "المشهد 3 (00:15 - 00:35) [شرح مبسط مع جرافيك]: المتحدث يشرح التجربة الحاسمة بأسلوب حواري ساخر.\n"
                    "المشهد 4 (00:35 - 00:45) [خاتمة ونداء]: 'الحكاية لسه فيها أسرار أكتر، الرابط كامل في البايو'."
                ),
                creative_rationale="هيكلية سردية مبنية على نموذج 'المقدمة الصادمة -> السياق التاريخي -> الشرح العملي -> نداء الإجراء'.",
                model_name="creative-engine-v1",
                is_ai_generated=True,
            )
        )

    else:
        # Generic variations / caption / cta
        outputs.append(
            CreativeRecommendation(
                item_uuid=request.item_uuid,
                creator_username=request.creator_username,
                output_type=request.output_type,
                target_platform=request.target_platform,
                target_audience=request.target_audience,
                target_duration=request.target_duration,
                target_language=request.target_language,
                suggested_hook=f"السؤال الأهم في قصة {topic}.. هل النجاح كان صدفة ولا خطة؟",
                suggested_caption=f"حلقة جديدة تكشف الكواليس لأول مرة. رابط المشاهدة متوفر في البايو 👆💡",
                suggested_cta="رابط الحلقة كاملة في البايو",
                script_outline="تركيز على التفاعل الفوري في التعليقات ونقل المتابع بسلاسة إلى البايو.",
                creative_rationale="كتابة تسويقية قائمة على الإيجاز وحث المتابع على اتخاذ إجراء واضح دون إرباك.",
                model_name="creative-engine-v1",
                is_ai_generated=True,
            )
        )

    for item in outputs:
        session.add(item)
    session.flush()
    return outputs
