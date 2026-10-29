import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart2,
  Calendar,
  Download,
  ExternalLink,
  Layers,
  Sparkles,
  TrendingUp,
  Users,
} from "lucide-react";
import { LoadingState } from "../../../components/States";
import { socialIntelligenceApi as client } from "../api/socialIntelligenceApi";

export function CreatorIntelligenceView({
  platform = "instagram",
  username = "eldaheeh",
}: {
  platform?: string;
  username?: string;
}) {
  const [activeMode, setActiveMode] = useState<"single" | "compare">("single");
  const [compareInput, setCompareInput] = useState(`${username},AJplus`);
  const [queryCreators, setQueryCreators] = useState(`${username},AJplus`);

  // Single creator query
  const singleQuery = useQuery({
    queryKey: ["creator-dna", platform, username],
    queryFn: () => client.creator(platform, username),
  });

  // Creator comparison query
  const compareQuery = useQuery({
    queryKey: ["creators-compare", platform, queryCreators],
    queryFn: () => client.compareCreators(queryCreators, platform),
    enabled: activeMode === "compare",
  });

  const data = singleQuery.data;

  if (singleQuery.isLoading) return <LoadingState />;

  return (
    <div className="creator-intelligence-view">
      <header className="creator-header">
        <div className="creator-profile-info">
          <span className="eyebrow">CREATOR INTELLIGENCE ENGINE</span>
          <h2>
            {activeMode === "single"
              ? `${data?.display_name || username} (@${username})`
              : `Creator Comparison: ${queryCreators}`}
          </h2>
          <p>
            {activeMode === "single"
              ? `Synthesized across ${data?.sample_size || 0} analyzed posts on ${platform}.`
              : `Side-by-side comparative benchmarking on ${platform}.`}
          </p>
        </div>
        <div className="header-actions">
          <div className="mode-toggle-buttons">
            <button
              className={`button small ${activeMode === "single" ? "primary" : "secondary"}`}
              onClick={() => setActiveMode("single")}
            >
              Profile DNA
            </button>
            <button
              className={`button small ${activeMode === "compare" ? "primary" : "secondary"}`}
              onClick={() => setActiveMode("compare")}
            >
              <Users size={13} /> Compare Creators
            </button>
          </div>
          <a
            className="button primary"
            href={client.streamExportUrl({ creator: username })}
            download
            title="Export full 18-sheet workbook"
          >
            <Download size={14} />
            Export Creator Workbook (.XLSX)
          </a>
        </div>
      </header>

      {/* COMPARISON MODE */}
      {activeMode === "compare" ? (
        <div className="creator-comparison-section">
          <div className="card-section comparison-controls">
            <label>Compare Creators (comma-separated usernames):</label>
            <div className="control-row">
              <input
                type="text"
                value={compareInput}
                onChange={(e) => setCompareInput(e.target.value)}
                placeholder="e.g. eldaheeh,AJplus,creator3"
              />
              <button
                className="button primary"
                disabled={compareQuery.isFetching}
                onClick={() => setQueryCreators(compareInput)}
              >
                {compareQuery.isFetching ? "Comparing..." : "Run Comparison"}
              </button>
            </div>
          </div>

          {compareQuery.isLoading ? (
            <LoadingState />
          ) : compareQuery.data ? (
            <div className="comparison-results">
              <div className="card-section">
                <h3>Comparative Performance & Strategy Matrix</h3>
                <div className="table-responsive">
                  <table className="comparison-table">
                    <thead>
                      <tr>
                        <th>Metric / Dimension</th>
                        {compareQuery.data.creators?.map((c: any) => (
                          <th key={c.username}>
                            {c.display_name || c.username} (@{c.username})
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Analyzed Sample Size</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>{c.sample_size} posts</td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Average Views</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            {(c.engagement_observations?.average_views || 0).toLocaleString()}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Median Views</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            {(c.engagement_observations?.median_views || 0).toLocaleString()}
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Interaction / View Rate</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            {c.engagement_observations?.observed_like_rate_pct || 0}%
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Top Hook Strategy</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            <span className="pill">
                              {c.common_hook_types?.[0]?.replace("_", " ") || "N/A"}
                            </span>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Top Call to Action</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            <span className="pill">
                              {c.common_cta_types?.[0]?.replace("_", " ") || "N/A"}
                            </span>
                          </td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Typical Video Duration</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>{c.typical_video_duration || "N/A"}</td>
                        ))}
                      </tr>
                      <tr>
                        <td><strong>Posting Cadence</strong></td>
                        {compareQuery.data.creators?.map((c: any) => (
                          <td key={c.username}>
                            {c.posting_frequency?.cadence_description || "Observed"}
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <p className="empty-notice">No comparison data returned.</p>
          )}
        </div>
      ) : (
        /* SINGLE CREATOR VIEW */
        <>
          {/* KPI METRICS */}
          <div className="metric-grid creator-metrics">
            <article className="metric-card">
              <span>Analyzed Posts</span>
              <strong>{data?.sample_size || 0}</strong>
            </article>
            <article className="metric-card">
              <span>Average Views</span>
              <strong>{(data?.engagement_observations?.average_views || 0).toLocaleString()}</strong>
            </article>
            <article className="metric-card">
              <span>Median Views</span>
              <strong>{(data?.engagement_observations?.median_views || 0).toLocaleString()}</strong>
            </article>
            <article className="metric-card">
              <span>Interaction Rate</span>
              <strong>{data?.engagement_observations?.observed_like_rate_pct || 0}%</strong>
            </article>
          </div>

          {/* CREATOR DNA SUMMARY */}
          <section className="panel creator-dna-panel">
            <div className="panel-heading">
              <h3>
                <Sparkles size={16} /> Creator DNA Synthesis V2
              </h3>
            </div>
            <p className="summary-paragraph">{data?.creator_dna_summary}</p>

            {/* TOPIC DISTRIBUTION BREAKDOWN */}
            {data?.topic_distribution && Object.keys(data.topic_distribution).length > 0 && (
              <div className="topic-dist-section">
                <h4><Layers size={14} /> Topic Distribution (% of Analyzed Corpus)</h4>
                <div className="topic-bars-grid">
                  {Object.entries(data.topic_distribution).map(([topName, topData]) => (
                    <div key={topName} className="topic-bar-row">
                      <div className="topic-bar-label">
                        <span>{topName}</span>
                        <strong>{topData.percentage}% ({topData.count} posts)</strong>
                      </div>
                      <div className="progress-bar-bg">
                        <div
                          className="progress-bar-fill"
                          style={{ width: `${topData.percentage}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="dna-features-grid">
              <div>
                <h4>Primary Topics</h4>
                <div className="pills-list">
                  {data?.primary_topics?.map((topic) => (
                    <span key={topic} className="pill">
                      {topic}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h4>Signature Hook Archetypes</h4>
                <div className="pills-list">
                  {data?.common_hook_types?.map((hook) => (
                    <span key={hook} className="pill">
                      {hook.replace("_", " ")}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h4>Storytelling Patterns</h4>
                <div className="pills-list">
                  {data?.storytelling_patterns?.map((story) => (
                    <span key={story} className="pill">
                      {story.replace("_", " ")}
                    </span>
                  ))}
                </div>
              </div>
              <div>
                <h4>Common CTA Habits</h4>
                <div className="pills-list">
                  {data?.common_cta_types?.map((cta) => (
                    <span key={cta} className="pill">
                      {cta.replaceAll("_", " ")}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            {/* VISUAL STYLE AND POSTING CADENCE */}
            <div className="cadence-visual-grid">
              {data?.posting_frequency && (
                <div className="cadence-card">
                  <h4><Calendar size={14} /> Posting Cadence & Cadence</h4>
                  <p>{data.posting_frequency.cadence_description}</p>
                </div>
              )}
              {data?.temporal_trends?.available && (
                <div className="temporal-card">
                  <h4><TrendingUp size={14} /> Changes Over Time</h4>
                  <p>{data.temporal_trends.observation}</p>
                </div>
              )}
            </div>

            {/* STANDOUT REPRESENTATIVE POSTS */}
            {data?.representative_posts && data.representative_posts.length > 0 && (
              <div className="representative-posts-section">
                <h4>Verified Standout Posts (By Engagement)</h4>
                <div className="standout-posts-grid">
                  {data.representative_posts.map((post) => (
                    <div key={post.item_uuid} className="standout-post-card">
                      <div className="standout-top">
                        <span className="views-tag">{(post.views || 0).toLocaleString()} Views</span>
                        <span className="likes-tag">{(post.likes || 0).toLocaleString()} Likes</span>
                      </div>
                      <p className="caption-preview" dir="auto">{post.caption_snippet}...</p>
                      {post.canonical_url && (
                        <a
                          href={post.canonical_url}
                          target="_blank"
                          rel="noreferrer"
                          className="link-out"
                        >
                          View Source Post <ExternalLink size={12} />
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="hypotheses-box">
              <h4>Observed Facts vs. Hypotheses</h4>
              <div className="dual-columns">
                <div>
                  <span className="subhead">Directly Observed Patterns:</span>
                  <ul>
                    {data?.hypotheses_vs_observed?.observed_facts?.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <span className="subhead">Strategic Hypotheses:</span>
                  <ul>
                    {data?.hypotheses_vs_observed?.working_hypotheses?.map((h, i) => (
                      <li key={i}>{h}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {data?.limitations_notice && (
              <div className="limitations-banner">
                <small>{data.limitations_notice}</small>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
