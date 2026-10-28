import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ContentAnalysisView } from "../features/social-inventory/components/ContentAnalysisView";
import { CreatorIntelligenceView } from "../features/social-inventory/components/CreatorIntelligenceView";
import { json, mockBackend, renderApp } from "./renderApp";
import type { SocialItem } from "../features/social-inventory/types";
import type {
  CompleteAnalysis,
  CreatorIntelligence,
  CreativeRecommendation,
} from "../features/social-inventory/intelligenceTypes";

const mockSocialItem: SocialItem = {
  uuid: "test-item-uuid-1",
  source_id: 1,
  platform: "instagram",
  external_id: "ext-1",
  canonical_url: "https://www.instagram.com/p/TEST1/",
  content_type: "video",
  caption: "من حلقة أحمد زويل من برنامج #الدحيح رابط الحلقة في البايو",
  published_at: "2026-10-25T12:41:31",
  author: {
    username: "eldaheeh",
    display_name: "ElDa7ee7 - الدحيح",
  },
  media: [{ type: "video", width: 1080, height: 1920, duration_seconds: 88.72 }],
  metrics: { views: 172045, likes: 5257, comments: 17, shares: null, saves: null },
  hashtags: ["الدحيح"],
  provider: "apify",
  first_observed_at: "2026-10-25T13:00:00",
  last_observed_at: "2026-10-25T13:00:00",
};

const mockAnalysisData: CompleteAnalysis = {
  item_uuid: "test-item-uuid-1",
  job: {
    id: 1,
    uuid: "job-uuid-1",
    item_uuid: "test-item-uuid-1",
    status: "COMPLETED",
    stage: "DONE",
    progress_percent: 100,
    retry_count: 0,
    created_at: "2026-10-25T13:00:00",
    completed_at: "2026-10-25T13:02:00",
  },
  transcript: {
    language: "ar",
    full_text: "أهلاً بيك يا صديقي في حلقة جديدة من الدحيح، والنهارده هنتكلم عن أحمد زويل.",
    model_name: "faster-whisper-base",
    duration_seconds: 88.72,
    status: "COMPLETED",
    segments: [
      {
        segment_index: 0,
        start_time: 0.0,
        end_time: 3.5,
        text: "أهلاً بيك يا صديقي في حلقة جديدة من الدحيح",
        confidence: 0.96,
        speaker: "Speaker 1",
      },
    ],
  },
  hooks: {
    model_name: "gemini-2.0-flash",
    heuristic_score: 9.0,
    hook_types: ["Curiosity_Gap", "Pattern_Interrupt"],
    spoken_hook: {
      exact_text: "أهلاً بيك يا صديقي في حلقة جديدة من الدحيح",
      start_time: 0.0,
      end_time: 3.5,
      duration: 3.5,
      linguistic_structure: "Friendly greeting + topic preview",
      opening_strategy: "question_inquiry",
      key_attention_trigger: "Catchphrase delivery",
      evidence: "Intro sequence",
    },
    visual_hook: {
      first_frame_composition: "Close-up presenter smiling directly into camera",
      opening_visual_event: "Sudden camera punch-in",
      camera_movement: "static_zoom",
      visible_subject: "Presenter face",
      visual_contrast: "High studio contrast",
      scene_changes: 2,
      visual_attention_techniques: ["punch_in"],
      supporting_timestamps: [0.0, 1.2],
    },
    text_hook: {
      opening_caption_sentence: "من حلقة أحمد زويل من برنامج #الدحيح",
      title_technique: "Authority Reference",
    },
  },
  copy: {
    original_caption: "من حلقة أحمد زويل من برنامج #الدحيح رابط الحلقة في البايو",
    tone_of_voice: "Informative, Entertaining",
    writing_style: "Egyptian Dialect (Ammiya) with scientific terminology",
    cta_text: "رابط الحلقة في البايو",
    cta_type: "link_in_bio",
    is_explicit_cta: true,
  },
  storytelling: {
    narrative_pattern: "educational_explanation",
    summary: "The scientific legacy of Ahmed Zewail",
    stages: [
      {
        stage_name: "Opening Hook",
        start_time: 0.0,
        end_time: 5.0,
        description: "Introduction to Zewail's breakthrough",
        evidence: "Mention of femtosecond chemistry",
        confidence: 0.95,
      },
      {
        stage_name: "Development",
        start_time: 5.0,
        end_time: 75.0,
        description: "Explanation of lasers and Nobel discovery",
        evidence: "Camera explanations and diagrams",
        confidence: 0.92,
      },
    ],
  },
  video: {
    duration: 88.72,
    aspect_ratio: "9:16",
    width: 1080,
    height: 1920,
    scene_count: 14,
    avg_scene_duration: 2.8,
    editing_pace: "fast",
    has_talking_head: true,
    has_broll: true,
    has_graphics: true,
    has_subtitles: true,
    scenes: [
      {
        scene_index: 0,
        start_time: 0.0,
        end_time: 2.8,
        duration: 2.8,
        camera_framing: "Medium Close-up",
        visual_description: "Host speaking to camera with studio backdrop",
      },
    ],
  },
};

const mockCreativeList: CreativeRecommendation[] = [
  {
    id: 1,
    uuid: "rec-uuid-1",
    item_uuid: "test-item-uuid-1",
    creator_username: "eldaheeh",
    output_type: "hook_variations",
    target_platform: "instagram",
    target_language: "ar",
    suggested_hook: "عارف ليه أحمد زويل ما كانش هيدخل كلية العلوم أصلاً؟",
    creative_rationale: "Creates an immediate contradiction with common knowledge to drive curiosity.",
    model_name: "gemini-2.0-flash",
    is_ai_generated: true,
    created_at: "2026-10-25T13:05:00",
  },
];

const mockCreatorData: CreatorIntelligence = {
  platform: "instagram",
  creator_id: "eldaheeh",
  username: "eldaheeh",
  display_name: "ElDa7ee7 - الدحيح",
  sample_size: 10,
  primary_topics: ["Science", "History", "Biographies"],
  common_hook_types: ["Curiosity Gap", "Pattern Interrupt", "Contrarian Angle"],
  typical_copy_style: "Egyptian Dialect (Ammiya) with scientific terminology",
  storytelling_patterns: ["Educational Infotainment", "Chronological Discovery"],
  typical_video_duration: "60-90s",
  editing_patterns: ["Fast-Paced Jump Cuts", "Dynamic B-Roll"],
  common_cta_types: ["link_in_bio", "comment"],
  engagement_observations: {
    average_views: 240000,
    average_likes: 12500,
    observed_like_rate_pct: 5.2,
  },
  creator_dna_summary: "High-cadence storytelling combining Egyptian humor with academic research.",
  limitations_notice: "Sampled from 10 public Instagram Reels. Private metrics (saves, shares) omitted.",
};

describe("Social Content Intelligence Engine Components", () => {
  function renderWithClient(ui: React.ReactElement) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
  }

  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/social-intelligence/items/test-item-uuid-1")) {
        return json(mockAnalysisData);
      }
      if (url.includes("/social-intelligence/creative/items/test-item-uuid-1")) {
        return json(mockCreativeList);
      }
      if (url.includes("/social-intelligence/creators/instagram/eldaheeh")) {
        return json(mockCreatorData);
      }
      return json({});
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  test("ContentAnalysisView renders tabs and displays Overview data", async () => {
    renderWithClient(
      <ContentAnalysisView item={mockSocialItem} onClose={vi.fn()} />
    );

    // Header status badge
    expect(await screen.findByText("COMPLETED")).toBeInTheDocument();
    expect(screen.getByText("Original Post & Metadata")).toBeInTheDocument();
    expect(screen.getByText("172,045")).toBeInTheDocument();

    // Verify Tab buttons exist
    expect(screen.getByRole("button", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hooks" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Transcript" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Copywriting" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Storytelling" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Video DNA" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Creative Outputs" })).toBeInTheDocument();
  });

  test("ContentAnalysisView switches across tabs and renders analytical details", async () => {
    renderWithClient(
      <ContentAnalysisView item={mockSocialItem} onClose={vi.fn()} />
    );

    // Switch to Hooks tab
    await userEvent.click(await screen.findByRole("button", { name: "Hooks" }));
    expect(await screen.findByText("Close-up presenter smiling directly into camera")).toBeInTheDocument();
    expect(screen.getByText(/Catchphrase delivery/i)).toBeInTheDocument();

    // Switch to Transcript tab
    await userEvent.click(screen.getByRole("button", { name: "Transcript" }));
    expect(await screen.findByText("أهلاً بيك يا صديقي في حلقة جديدة من الدحيح")).toBeInTheDocument();
    expect(screen.getByText("96%")).toBeInTheDocument();

    // Switch to Copywriting tab
    await userEvent.click(screen.getByRole("button", { name: "Copywriting" }));
    expect(await screen.findByText("Egyptian Dialect (Ammiya) with scientific terminology")).toBeInTheDocument();
    expect(screen.getByText("link_in_bio")).toBeInTheDocument();

    // Switch to Storytelling tab
    await userEvent.click(screen.getByRole("button", { name: "Storytelling" }));
    expect(await screen.findByText(/educational explanation/i)).toBeInTheDocument();
    expect(screen.getByText("Opening Hook")).toBeInTheDocument();
    expect(screen.getByText(/Mention of femtosecond chemistry/i)).toBeInTheDocument();

    // Switch to Video DNA tab
    await userEvent.click(screen.getByRole("button", { name: "Video DNA" }));
    expect(await screen.findByText("9:16")).toBeInTheDocument();
    expect(screen.getByText(/14 shots/i)).toBeInTheDocument();

    // Switch to Creative Outputs tab
    await userEvent.click(screen.getByRole("button", { name: "Creative Outputs" }));
    expect(await screen.findByText("عارف ليه أحمد زويل ما كانش هيدخل كلية العلوم أصلاً؟")).toBeInTheDocument();
    expect(screen.getByText(/Creates an immediate contradiction/i)).toBeInTheDocument();
  });

  test("CreatorIntelligenceView renders aggregated creator metrics and hook patterns", async () => {
    renderWithClient(
      <CreatorIntelligenceView platform="instagram" username="eldaheeh" />
    );

    expect(await screen.findByText("CREATOR INTELLIGENCE ENGINE")).toBeInTheDocument();
    expect(await screen.findByText("ElDa7ee7 - الدحيح (@eldaheeh)")).toBeInTheDocument();
    expect(await screen.findByText("High-cadence storytelling combining Egyptian humor with academic research.")).toBeInTheDocument();

    // Verify hook pill archetypes
    expect(await screen.findByText("Curiosity Gap")).toBeInTheDocument();
    expect(screen.getByText("Pattern Interrupt")).toBeInTheDocument();

    // Verify KPI numbers
    expect(screen.getByText("240,000")).toBeInTheDocument();
    expect(screen.getByText("5.2%")).toBeInTheDocument();
    expect(screen.getByText("Export Creator Workbook (.XLSX)")).toBeInTheDocument();
  });

  test("SocialInventoryPage shows full 14-sheet Excel export button and batch selection", async () => {
    mockBackend((url) => {
      if (url.includes("/social-inventory/capabilities")) {
        return json({
          apify: { enabled: true, platforms: { instagram: true } },
          jev: { enabled: false },
          limits: { max_items: 500, max_comments_per_post: 100 },
        });
      }
      if (url.includes("/social-inventory/overview")) {
        return json({ sources: 1, items: 1, total_views: 172045, total_engagement: 5274, problem_runs: 0 });
      }
      if (url.includes("/social-inventory/sources")) {
        return json([]);
      }
      if (url.includes("/social-inventory/runs")) {
        return json([]);
      }
      if (url.includes("/social-inventory/items")) {
        return json({
          items: [mockSocialItem],
          total: 1,
          offset: 0,
          limit: 50,
        });
      }
      if (url.includes("/social-intelligence/creators/instagram/eldaheeh")) {
        return json(mockCreatorData);
      }
      return undefined;
    });

    renderApp("/social-inventory?tab=content");

    // Verify 14-Sheet Excel Export Button is present in the export section
    expect(await screen.findByText("Full 14-Sheet Excel Intelligence Report (.xlsx)")).toBeInTheDocument();

    // Verify the Item caption is rendered in table
    expect(await screen.findByText("من حلقة أحمد زويل من برنامج #الدحيح رابط الحلقة في البايو")).toBeInTheDocument();

    // Multi-select checkbox
    const checkbox = await screen.findByRole("checkbox", {
      name: "Select من حلقة أحمد زويل من برنامج #الدحيح رابط الحلقة في البايو",
    });
    expect(checkbox).toBeInTheDocument();

    // Select the item checkbox
    await userEvent.click(checkbox);

    // Verify batch action bar appears
    expect(await screen.findByText("1 selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analyze Selected (1)" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Export Selected (.XLSX)" })).toBeInTheDocument();
  });
});
