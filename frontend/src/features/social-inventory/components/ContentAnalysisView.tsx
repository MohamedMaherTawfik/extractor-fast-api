import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Copy,
  Download,
  Film,
  Lightbulb,
  MessageSquare,
  Play,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import { LoadingState } from "../../../components/States";
import { StatusBadge } from "../../../components/StatusBadge";
import { socialIntelligenceApi as client } from "../api/socialIntelligenceApi";
import type { SocialItem } from "../types";
import type { CompleteAnalysis } from "../intelligenceTypes";

export function ContentAnalysisView({
  item,
  onClose,
}: {
  item: SocialItem;
  onClose: () => void;
}) {
  const cache = useQueryClient();
  const [activeTab, setActiveTab] = useState<
    "overview" | "hooks" | "transcript" | "copy" | "story" | "video" | "creative"
  >("overview");
  const [genType, setGenType] = useState("hook_variations");
  const [copiedId, setCopiedId] = useState<string>();

  const analysisQuery = useQuery({
    queryKey: ["social-intel", item.uuid],
    queryFn: () => client.analysis(item.uuid),
    refetchInterval: (query) => {
      const status = query.state.data?.job?.status;
      return status === "QUEUED" || status === "PROCESSING" ? 2000 : false;
    },
  });

  const analyzeMutation = useMutation({
    mutationFn: () => client.analyze(item.uuid, true),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["social-intel", item.uuid] }),
  });

  const retryMutation = useMutation({
    mutationFn: (jobUuid: string) => client.retry(jobUuid),
    onSuccess: () => cache.invalidateQueries({ queryKey: ["social-intel", item.uuid] }),
  });

  const generateMutation = useMutation({
    mutationFn: () =>
      client.generateCreative({
        item_uuid: item.uuid,
        creator_username: (item.author as Record<string, string>)?.username,
        output_type: genType,
        topic_context: item.title || item.caption?.slice(0, 50),
      }),
    onSuccess: () =>
      cache.invalidateQueries({ queryKey: ["social-intel-creative", item.uuid] }),
  });

  const creativeList = useQuery({
    queryKey: ["social-intel-creative", item.uuid],
    queryFn: () => client.listCreative(item.uuid),
  });

  const analysis = analysisQuery.data;
  const job = analysis?.job;
  const isRunning = job?.status === "QUEUED" || job?.status === "PROCESSING";

  const copyText = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(undefined), 2000);
  };

  return (
    <div className="content-analysis-view">
      <div className="analysis-header-bar">
        <div className="status-row">
          <StatusBadge value={job?.status || "NOT_ANALYZED"} />
          {job?.stage && <span className="stage-tag">{job.stage}</span>}
          {isRunning && (
            <span className="progress-indicator">
              <RefreshCw className="spin" size={13} /> {job.progress_percent}%
            </span>
          )}
        </div>
        <div className="action-row">
          {(!job || job.status === "FAILED" || job.status === "PARTIAL") && (
            <button
              className="button primary small"
              disabled={analyzeMutation.isPending || isRunning}
              onClick={() =>
                job?.uuid ? retryMutation.mutate(job.uuid) : analyzeMutation.mutate()
              }
            >
              <Sparkles size={13} />
              {job?.status === "FAILED" ? "Retry Analysis" : "Run AI Analysis"}
            </button>
          )}
          <a
            className="button secondary small"
            href={client.streamExportUrl({ scope: "single" })}
            download
            title="Export 14-Sheet Excel Workbook"
          >
            <Download size={13} />
            Export XLSX
          </a>
        </div>
      </div>

      {job?.error_message && (
        <div className="analysis-error-banner">
          <AlertCircle size={15} />
          <span>{job.error_message}</span>
        </div>
      )}

      <nav className="analysis-tabs">
        {(
          [
            ["overview", "Overview"],
            ["hooks", "Hooks"],
            ["transcript", "Transcript"],
            ["copy", "Copywriting"],
            ["story", "Storytelling"],
            ["video", "Video DNA"],
            ["creative", "Creative Outputs"],
          ] as const
        ).map(([tabKey, label]) => (
          <button
            key={tabKey}
            className={activeTab === tabKey ? "active" : ""}
            onClick={() => setActiveTab(tabKey)}
          >
            {label}
          </button>
        ))}
      </nav>

      <div className="analysis-tab-body">
        {analysisQuery.isLoading ? (
          <LoadingState />
        ) : (
          <>
            {/* OVERVIEW TAB */}
            {activeTab === "overview" && (
              <div className="overview-pane">
                <div className="card-section">
                  <h3>Original Post & Metadata</h3>
                  <div className="meta-pairs">
                    <div>
                      <label>Platform</label>
                      <span>{item.platform}</span>
                    </div>
                    <div>
                      <label>Published</label>
                      <span>
                        {item.published_at
                          ? new Date(item.published_at).toLocaleString()
                          : "Unknown"}
                      </span>
                    </div>
                    <div>
                      <label>Views</label>
                      <span>{(item.metrics?.views || 0).toLocaleString()}</span>
                    </div>
                    <div>
                      <label>Likes</label>
                      <span>{(item.metrics?.likes || 0).toLocaleString()}</span>
                    </div>
                  </div>
                  <div className="caption-box">
                    <label>Caption</label>
                    <p dir="auto">{item.caption || "No caption provided."}</p>
                  </div>
                </div>

                {analysis?.hooks && (
                  <div className="card-section">
                    <h3>Hook Assessment Snapshot</h3>
                    <div className="kpi-mini">
                      <span>Heuristic Quality Score:</span>
                      <strong>{analysis.hooks.heuristic_score} / 10</strong>
                      <small className="muted">(Model-generated heuristic guideline)</small>
                    </div>
                    <div className="hook-tags">
                      {analysis.hooks.hook_types?.map((t) => (
                        <span key={t} className="pill">
                          {t.replace("_", " ")}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* HOOKS TAB */}
            {activeTab === "hooks" && (
              <div className="hooks-pane">
                {analysis?.hooks ? (
                  <>
                    <div className="card-section spoken-hook-box">
                      <div className="badge-row">
                        <span className="badge-pill">Spoken Hook</span>
                        <span className="time-badge">
                          {analysis.hooks.spoken_hook?.start_time}s -{" "}
                          {analysis.hooks.spoken_hook?.end_time}s (
                          {analysis.hooks.spoken_hook?.duration}s)
                        </span>
                      </div>
                      <p className="hook-quote" dir="auto">
                        "{analysis.hooks.spoken_hook?.exact_text || "No spoken audio detected"}"
                      </p>
                      <div className="meta-sub">
                        <span>Strategy: {analysis.hooks.spoken_hook?.opening_strategy}</span>
                        <span>Trigger: {analysis.hooks.spoken_hook?.key_attention_trigger}</span>
                      </div>
                    </div>

                    <div className="card-section visual-hook-box">
                      <div className="badge-row">
                        <span className="badge-pill">Visual Hook</span>
                      </div>
                      <div className="meta-pairs">
                        <div>
                          <label>Composition</label>
                          <span>{analysis.hooks.visual_hook?.first_frame_composition}</span>
                        </div>
                        <div>
                          <label>Opening Event</label>
                          <span>{analysis.hooks.visual_hook?.opening_visual_event}</span>
                        </div>
                        <div>
                          <label>Contrast</label>
                          <span>{analysis.hooks.visual_hook?.visual_contrast}</span>
                        </div>
                      </div>
                    </div>

                    <div className="card-section text-hook-box">
                      <div className="badge-row">
                        <span className="badge-pill">Caption Hook</span>
                      </div>
                      <p dir="auto">
                        {analysis.hooks.text_hook?.opening_caption_sentence}
                      </p>
                    </div>

                    <div className="card-section qualitative-grid">
                      <div>
                        <h4>Strengths</h4>
                        <ul>
                          {analysis.hooks.qualitative_strengths?.map((s, idx) => (
                            <li key={idx}>{s}</li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <h4>Recommendations</h4>
                        <ul>
                          {analysis.hooks.recommendations?.map((r, idx) => (
                            <li key={idx}>{r}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  </>
                ) : (
                  <p className="empty-notice">
                    {isRunning
                      ? "Analyzing hooks..."
                      : "No hook analysis available. Click 'Run AI Analysis' above."}
                  </p>
                )}
              </div>
            )}

            {/* TRANSCRIPT TAB */}
            {activeTab === "transcript" && (
              <div className="transcript-pane">
                {analysis?.transcript ? (
                  <>
                    <div className="transcript-header-info">
                      <span>Detected Language: {analysis.transcript.language?.toUpperCase()}</span>
                      <span>Model: {analysis.transcript.model_name}</span>
                      <span>Duration: {analysis.transcript.duration_seconds}s</span>
                    </div>
                    <div className="segment-list" dir="auto">
                      {analysis.transcript.segments?.map((seg) => (
                        <div key={seg.segment_index} className="segment-row">
                          <span className="time-code">
                            {seg.start_time.toFixed(1)}s - {seg.end_time.toFixed(1)}s
                          </span>
                          <span className="segment-text">{seg.text}</span>
                          {seg.confidence && (
                            <span className="conf-score">
                              {(seg.confidence * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <p className="empty-notice">
                    {isRunning
                      ? "Transcribing audio..."
                      : "No transcript available. Ensure media URL is accessible and click 'Run AI Analysis'."}
                  </p>
                )}
              </div>
            )}

            {/* COPYWRITING TAB */}
            {activeTab === "copy" && (
              <div className="copy-pane">
                {analysis?.copy ? (
                  <div className="card-section">
                    <h3>Copywriting & Strategic Intent</h3>
                    <div className="meta-pairs">
                      <div>
                        <label>Main Topic</label>
                        <span>{analysis.copy.main_topic}</span>
                      </div>
                      <div>
                        <label>Writing Style / Dialect</label>
                        <span>{analysis.copy.writing_style}</span>
                      </div>
                      <div>
                        <label>Tone of Voice</label>
                        <span>{analysis.copy.tone_of_voice}</span>
                      </div>
                      <div>
                        <label>Emotional Framing</label>
                        <span>{analysis.copy.emotional_framing}</span>
                      </div>
                      <div>
                        <label>CTA Type</label>
                        <span className="pill">{analysis.copy.cta_type}</span>
                      </div>
                      <div>
                        <label>Exact CTA Text</label>
                        <span dir="auto">{analysis.copy.cta_text || "None"}</span>
                      </div>
                    </div>
                    <div className="summary-box">
                      <label>AI Strategic Summary</label>
                      <p>{analysis.copy.summary}</p>
                    </div>
                  </div>
                ) : (
                  <p className="empty-notice">
                    {isRunning ? "Analyzing copywriting..." : "No copy analysis available."}
                  </p>
                )}
              </div>
            )}

            {/* STORYTELLING TAB */}
            {activeTab === "story" && (
              <div className="story-pane">
                {analysis?.storytelling ? (
                  <div className="card-section">
                    <div className="badge-row">
                      <h3>Narrative Architecture</h3>
                      <span className="pill">
                        {analysis.storytelling.narrative_pattern.replace("_", " ")}
                      </span>
                    </div>
                    <p className="story-summary">{analysis.storytelling.summary}</p>
                    <div className="timeline-stages">
                      {analysis.storytelling.stages?.map((stage, i) => (
                        <div key={i} className="timeline-stage-card">
                          <div className="stage-time">
                            {stage.start_time}s - {stage.end_time}s
                          </div>
                          <h4>{stage.stage_name}</h4>
                          <p>{stage.description}</p>
                          <small className="muted" dir="auto">
                            Evidence: {stage.evidence}
                          </small>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="empty-notice">
                    {isRunning ? "Analyzing narrative stages..." : "No storytelling analysis available."}
                  </p>
                )}
              </div>
            )}

            {/* VIDEO DNA TAB */}
            {activeTab === "video" && (
              <div className="video-pane">
                {analysis?.video ? (
                  <div className="card-section">
                    <h3>Visual Deconstruction & Production</h3>
                    <div className="meta-pairs">
                      <div>
                        <label>Aspect Ratio</label>
                        <span>{analysis.video.aspect_ratio}</span>
                      </div>
                      <div>
                        <label>Editing Pace</label>
                        <span>{analysis.video.editing_pace}</span>
                      </div>
                      <div>
                        <label>Scene Count</label>
                        <span>{analysis.video.scene_count} shots</span>
                      </div>
                      <div>
                        <label>Avg Shot Duration</label>
                        <span>{analysis.video.avg_scene_duration}s</span>
                      </div>
                    </div>

                    <div className="scenes-list">
                      <h4>Detected Scenes & Shots</h4>
                      {analysis.video.scenes?.map((scene) => (
                        <div key={scene.scene_index} className="scene-item">
                          <span className="scene-num">#{scene.scene_index}</span>
                          <span className="scene-time">
                            {scene.start_time}s - {scene.end_time}s ({scene.duration}s)
                          </span>
                          <span className="scene-desc">{scene.visual_description}</span>
                          <span className="scene-tag">{scene.camera_framing}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="empty-notice">
                    {isRunning ? "Deconstructing video..." : "No video deconstruction available."}
                  </p>
                )}
              </div>
            )}

            {/* CREATIVE OUTPUTS TAB */}
            {activeTab === "creative" && (
              <div className="creative-pane">
                <div className="card-section generator-controls">
                  <h3>AI Creative Variations</h3>
                  <div className="control-bar">
                    <select
                      value={genType}
                      onChange={(e) => setGenType(e.target.value)}
                    >
                      <option value="hook_variations">Hook Variations (3 Styles)</option>
                      <option value="video_script">Original Video Script Outline</option>
                      <option value="caption_variations">Caption Variations</option>
                      <option value="cta_ideas">Conversion CTA Ideas</option>
                    </select>
                    <button
                      className="button primary"
                      disabled={generateMutation.isPending}
                      onClick={() => generateMutation.mutate()}
                    >
                      <Sparkles size={14} />
                      {generateMutation.isPending ? "Generating..." : "Generate New Creative"}
                    </button>
                  </div>
                </div>

                <div className="generated-cards">
                  {creativeList.data?.map((rec) => (
                    <div key={rec.uuid} className="creative-card">
                      <div className="card-top">
                        <span className="ai-tag">AI GENERATED</span>
                        <span className="rec-type">{rec.output_type.replace("_", " ")}</span>
                        <button
                          className="icon-button"
                          onClick={() =>
                            copyText(
                              rec.suggested_hook || rec.script_outline || rec.suggested_caption || "",
                              rec.uuid
                            )
                          }
                        >
                          {copiedId === rec.uuid ? (
                            <CheckCircle2 size={13} color="#22c55e" />
                          ) : (
                            <Copy size={13} />
                          )}
                        </button>
                      </div>

                      {rec.suggested_hook && (
                        <div className="hook-content" dir="auto">
                          <label>Suggested Hook</label>
                          <p>{rec.suggested_hook}</p>
                        </div>
                      )}

                      {rec.script_outline && (
                        <div className="script-content" dir="auto">
                          <label>Production Recipe / Script</label>
                          <pre>{rec.script_outline}</pre>
                        </div>
                      )}

                      {rec.suggested_caption && (
                        <div className="caption-content" dir="auto">
                          <label>Caption Angle</label>
                          <p>{rec.suggested_caption}</p>
                        </div>
                      )}

                      <div className="rationale-content">
                        <label>Creative Rationale</label>
                        <p>{rec.creative_rationale}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
