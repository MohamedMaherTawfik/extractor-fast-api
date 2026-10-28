import { useQuery } from "@tanstack/react-query";
import { Download, Sparkles, TrendingUp, Users } from "lucide-react";
import { LoadingState } from "../../../components/States";
import { socialIntelligenceApi as client } from "../api/socialIntelligenceApi";

export function CreatorIntelligenceView({
  platform = "instagram",
  username = "eldaheeh",
}: {
  platform?: string;
  username?: string;
}) {
  const query = useQuery({
    queryKey: ["creator-dna", platform, username],
    queryFn: () => client.creator(platform, username),
  });

  const data = query.data;

  if (query.isLoading) return <LoadingState />;

  return (
    <div className="creator-intelligence-view">
      <header className="creator-header">
        <div className="creator-profile-info">
          <span className="eyebrow">CREATOR INTELLIGENCE ENGINE</span>
          <h2>
            {data?.display_name || username} (@{username})
          </h2>
          <p>
            Synthesized across {data?.sample_size || 0} analyzed posts on {platform}.
          </p>
        </div>
        <a
          className="button primary"
          href={client.streamExportUrl({ creator: username })}
          download
        >
          <Download size={14} />
          Export Creator Workbook (.XLSX)
        </a>
      </header>

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
          <span>Average Likes</span>
          <strong>{(data?.engagement_observations?.average_likes || 0).toLocaleString()}</strong>
        </article>
        <article className="metric-card">
          <span>Interaction / View Ratio</span>
          <strong>{data?.engagement_observations?.observed_like_rate_pct || 0}%</strong>
        </article>
      </div>

      {/* CREATOR DNA SUMMARY */}
      <section className="panel creator-dna-panel">
        <div className="panel-heading">
          <h3>
            <Sparkles size={16} /> Creator DNA Synthesis
          </h3>
        </div>
        <p className="summary-paragraph">{data?.creator_dna_summary}</p>

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
                  {cta.replace("_", " ")}
                </span>
              ))}
            </div>
          </div>
        </div>

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
    </div>
  );
}
