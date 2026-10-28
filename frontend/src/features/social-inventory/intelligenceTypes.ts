export interface AnalysisJob {
  id: number;
  uuid: string;
  item_uuid: string;
  status: "PENDING" | "QUEUED" | "PROCESSING" | "PARTIAL" | "COMPLETED" | "FAILED" | "RETRYING";
  stage: string;
  progress_percent: number;
  error_category?: string;
  error_message?: string;
  retry_count: number;
  started_at?: string;
  completed_at?: string;
  created_at?: string;
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
    average_likes?: number;
    observed_like_rate_pct?: number;
    views_range?: [number, number];
  };
  creator_dna_summary?: string;
  hypotheses_vs_observed?: {
    observed_facts?: string[];
    working_hypotheses?: string[];
  };
  limitations_notice?: string;
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
