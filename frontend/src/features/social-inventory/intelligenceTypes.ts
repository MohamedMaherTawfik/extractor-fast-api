export interface AnalysisJob {
  id: number;
  uuid: string;
  item_uuid: string;
  status: "PENDING" | "QUEUED" | "PROCESSING" | "PARTIAL" | "COMPLETED" | "FAILED" | "RETRYING" | "CANCELLED";
  stage: string;
  progress_percent: number;
  error_category?: string;
  error_message?: string;
  retry_count: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
  quality_summary?: Record<string, unknown>;
  completion_summary?: Record<string, unknown>;
  resource_usage?: Record<string, unknown>;
}

export interface TranscriptSegment {
  segment_index: number;
  start_time: number;
  end_time: number;
  text: string;
  speaker?: string;
  confidence?: number;
}

export interface Transcript {
  language?: string;
  language_probability?: number;
  full_text: string;
  duration_seconds?: number;
  model_name: string;
  status: string;
  segments: TranscriptSegment[];
  raw_text?: string;
  corrected_text?: string;
  correction_status?: string;
  quality_indicators?: {
    average_segment_confidence?: number;
    low_confidence_segment_count?: number;
    repeated_phrase_count?: number;
    timestamps_monotonic?: boolean;
    wer?: number;
    human_reference_available?: boolean;
  };
}

export interface AnalysisEvidence {
  uuid: string;
  item_uuid: string;
  claim_type: string;
  claim_text: string;
  evidence_type: string;
  source_reference: string;
  start_time?: number;
  end_time?: number;
  evidence_quote?: string;
  analysis_provider: string;
  model_version: string;
  verification_status: "verified" | "needs_review" | "invalid" | "unsupported";
  verification_reason?: string;
  confidence?: number;
}

export interface SpokenHook {
  exact_text: string;
  start_time: number;
  end_time: number;
  duration: number;
  linguistic_structure: string;
  opening_strategy: string;
  key_attention_trigger: string;
  evidence: string;
}

export interface VisualHook {
  first_frame_composition: string;
  opening_visual_event: string;
  camera_movement: string;
  visible_subject: string;
  visual_contrast: string;
  scene_changes: number;
  on_screen_text?: string;
  visual_attention_techniques: string[];
  supporting_timestamps: number[];
}

export interface TextHook {
  opening_caption_sentence: string;
  on_screen_headline?: string;
  opening_subtitle?: string;
  title_technique: string;
}

export interface HookEntry {
  modality: "spoken" | "visual" | "caption_text" | "on_screen_overlay";
  category: string;
  exact_text?: string;
  start_time?: number;
  end_time?: number;
  duration?: number;
  mechanism: string;
  attention_strategy: string;
  promise_or_curiosity_gap: string;
  explanation: string;
  evidence: {
    source_modality: string;
    verbatim_quote?: string;
    start_time?: number;
    end_time?: number;
    location_description?: string;
    confidence: number;
  };
  confidence: number;
  subjective_assessment: string;
  suggested_alternatives: string[];
}

export interface HookAnalysis {
  spoken_hook?: SpokenHook;
  visual_hook?: VisualHook;
  text_hook?: TextHook;
  hook_types: string[];
  clarity?: string;
  specificity?: string;
  relevance?: string;
  curiosity_mechanism?: string;
  text_visual_alignment?: string;
  heuristic_score?: number;
  qualitative_strengths?: string[];
  qualitative_weaknesses?: string[];
  recommendations?: string[];
  model_name: string;
  identified_hooks?: HookEntry[];
  opening_payoff_connection?: {
    has_payoff: boolean;
    payoff_timestamp?: number;
    payoff_quote?: string;
    connection_strength?: string;
    reasoning?: string;
  };
}

export interface CopyAnalysis {
  original_caption?: string;
  opening_sentence?: string;
  primary_message?: string;
  main_topic?: string;
  secondary_topics?: string[];
  tone_of_voice?: string;
  writing_style?: string;
  emotional_framing?: string;
  persuasion_techniques?: string[];
  content_objective?: string;
  audience_address?: string;
  hashtag_strategy?: Record<string, unknown>;
  cta_type?: string;
  cta_text?: string;
  is_explicit_cta: boolean;
  caption_structure?: string;
  sentence_characteristics?: string;
  readability_observations?: string;
  brand_voice_indicators?: string;
  summary?: string;
}

export interface NarrativeStage {
  stage_name: string;
  start_time: number;
  end_time: number;
  description: string;
  evidence: string;
  confidence: number;
}

export interface NarrativeAnalysis {
  narrative_pattern: string;
  summary?: string;
  stages: NarrativeStage[];
}

export interface VideoScene {
  scene_index: number;
  start_time: number;
  end_time: number;
  duration: number;
  visual_description?: string;
  camera_framing?: string;
  camera_movement?: string;
  visible_text?: string;
  editing_notes?: string;
  scene_classification?: string;
  confidence?: number;
  sampled_metrics?: {
    luminance?: number;
    contrast?: number;
    color_tone?: string;
    dominant_color?: string;
    subtitle_band_detected?: boolean;
    top_graphics_detected?: boolean;
    center_skin_tone_ratio?: number;
    is_talking_head_candidate?: boolean;
  };
}

export interface VideoAnalysis {
  duration?: number;
  aspect_ratio?: string;
  width?: number;
  height?: number;
  scene_count: number;
  avg_scene_duration?: number;
  editing_pace?: string;
  opening_style?: string;
  visual_style?: string;
  has_talking_head: boolean;
  has_broll: boolean;
  has_graphics: boolean;
  has_subtitles: boolean;
  ending_style?: string;
  production_characteristics?: string;
  shot_distribution?: {
    total_shots?: number;
    cuts_per_minute?: number;
    median_shot_duration?: number;
    shots_under_2s?: number;
    shots_2s_to_4s?: number;
    shots_over_4s?: number;
  };
  visual_analysis_level?: string;
  scenes: VideoScene[];
}

export interface CompleteAnalysis {
  item_uuid: string;
  job?: AnalysisJob;
  transcript?: Transcript;
  hooks?: HookAnalysis;
  copy?: CopyAnalysis;
  storytelling?: NarrativeAnalysis;
  video?: VideoAnalysis;
  evidence?: AnalysisEvidence[];
}

export interface CreatorIntelligence {
  platform: string;
  creator_id: string;
  username: string;
  display_name?: string;
  sample_size: number;
  first_observed_at?: string;
  last_observed_at?: string;
  primary_topics?: string[];
  common_hook_types?: string[];
  typical_copy_style?: string;
  storytelling_patterns?: string[];
  typical_video_duration?: string;
  editing_patterns?: string[];
  common_cta_types?: string[];
  engagement_observations?: {
    average_views?: number;
    median_views?: number;
    average_likes?: number;
    median_likes?: number;
    observed_like_rate_pct?: number;
    views_range?: [number, number];
    views_iqr?: [number, number];
    sample_size_metrics?: number;
  };
  creator_dna_summary?: string;
  hypotheses_vs_observed?: {
    observed_facts?: string[];
    working_hypotheses?: string[];
  };
  limitations_notice?: string;
  topic_distribution?: Record<string, { count: number; percentage: number }>;
  posting_frequency?: {
    total_observed_posts?: number;
    first_observed_at?: string;
    last_observed_at?: string;
    span_days?: number;
    average_posts_per_month?: number;
    cadence_description?: string;
  };
  visual_style_patterns?: string[];
  representative_posts?: Array<{
    item_uuid: string;
    canonical_url?: string;
    published_at?: string;
    views?: number;
    likes?: number;
    caption_snippet?: string;
  }>;
  sample_post_uuids?: string[];
  temporal_trends?: {
    available: boolean;
    view_growth_pct?: number;
    observation?: string;
  };
}

export interface CreatorComparisonData {
  platform: string;
  creators: CreatorIntelligence[];
  comparison_matrix: {
    creators_compared: string[];
    metrics_comparison: Record<string, any>;
    comparative_observations: string[];
  };
}

export interface ContentSearchFilter {
  hook_category?: string;
  storytelling_structure?: string;
  topic?: string;
  has_talking_head?: boolean;
  has_broll?: boolean;
  transcript_phrase?: string;
  creator_username?: string;
  platform?: string;
  date_from?: string;
  date_to?: string;
  min_duration?: number;
  max_duration?: number;
}

export interface ContentSearchResult {
  total: number;
  results: Array<{
    item_uuid: string;
    platform: string;
    author_username?: string;
    title?: string;
    caption_snippet?: string;
    published_at?: string;
    analysis_status: string;
    duration_seconds?: number;
    matched_hook_category?: string;
    matched_storytelling_pattern?: string;
    matched_topic?: string;
    evidence_snippet?: string;
  }>;
}

export interface CreativeRecommendation {
  id: number;
  uuid: string;
  item_uuid?: string;
  creator_username?: string;
  output_type: string;
  target_platform: string;
  target_audience?: string;
  target_duration?: string;
  target_language: string;
  suggested_hook?: string;
  suggested_caption?: string;
  suggested_cta?: string;
  script_outline?: string;
  creative_rationale?: string;
  model_name: string;
  is_ai_generated: boolean;
  created_at: string;
}

export interface ExcelExportJob {
  uuid: string;
  status: string;
  scope: string;
  filename?: string;
  total_rows: number;
  file_size_bytes: number;
  created_at: string;
  completed_at?: string;
}
