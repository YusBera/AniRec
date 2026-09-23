import { useState } from "react";
import type {
  Explanation,
  ExplanationEvidence,
  ExplanationSegment,
  RecommendationViewModel,
} from "../api/types";

const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });
const decimal = new Intl.NumberFormat(undefined, { maximumFractionDigits: 3 });
const EVIDENCE_PAGE_SIZE = 8;

export function rankingEngineId(userStats: Record<string, unknown>): string | null {
  const value = userStats.ranking_engine_id;
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function rankingEngineLabel(engineId: string | null): string {
  if (engineId === "sasrec-onnx") return "sequence model";
  if (engineId === "heuristic") return "heuristic";
  if (!engineId) return "ranking engine unavailable";
  return engineId.replaceAll("-", " ");
}

export function personalFitText(model: RecommendationViewModel, engineId: string | null): string {
  if (model.fit_rank === null || model.fit_rank === undefined || model.fit_pool_size === null || model.fit_pool_size === undefined) {
    return "Personal fit unavailable";
  }
  return `#${integer.format(model.fit_rank)} of ${integer.format(model.fit_pool_size)} · ${rankingEngineLabel(engineId)}`;
}

export function FitIndicator({ model, engineId, onOpen }: {
  model: RecommendationViewModel;
  engineId: string | null;
  onOpen: () => void;
}) {
  const fit = personalFitText(model, engineId);
  return (
    <button type="button" className="fit-indicator" onClick={onOpen} aria-label={`Why this pick. ${fit}`}>
      <span className="lbl">Personal fit</span>
      <strong>{fit}</strong>
      <span className="fit-action">Why this pick</span>
    </button>
  );
}

export function WhyExplanation({ why }: { why: Explanation | null | undefined }) {
  if (!why || why.method === "unavailable") {
    return <UnavailableExplanation reason={why?.unavailable_reason ?? null} />;
  }
  if (why.method === "exact-additive") return <AdditiveExplanation why={why} />;
  return <CounterfactualExplanation why={why} />;
}

function AdditiveExplanation({ why }: { why: Explanation }) {
  return (
    <div className="why-explanation">
      <p className="details-note">These score parts add to the ranking score. Positive parts raised the pick; negative parts held it back.</p>
      <dl className="why-total">
        <div><dt>Ranking score</dt><dd>{why.total === null ? "Unavailable" : decimal.format(why.total)}</dd></div>
      </dl>
      <ImpactBar segments={why.segments} label="Additive score parts" />
      <div className="why-segments">
        {why.segments.map((segment, index) => (
          <details className="why-segment" key={`${segment.kind}:${segment.label}:${index}`}>
            <summary>
              <span>{segmentDisplayLabel(segment)}</span>
              <span className="why-value">{formatSigned(segment.value)}</span>
              <span className="why-direction">{direction(segment.value)}</span>
            </summary>
            <AdditiveSegmentDetail segment={segment} />
          </details>
        ))}
      </div>
    </div>
  );
}

function AdditiveSegmentDetail({ segment }: { segment: ExplanationSegment }) {
  if (segment.kind === "taste") {
    const taste = segment.taste;
    const count = taste?.rated_count;
    const mean = taste?.mean_user_score;
    const overall = taste?.overall_mean_user_score;
    return (
      <div className="why-segment-body">
        <p>{segment.facet ? `This ${segment.facet} part` : "This taste part"} {segment.feedback_adjustment === null ? "comes from your ratings." : "combines your ratings with an adjustment from your likes/dislikes."}</p>
        <p>{count === null || count === undefined || mean === null || mean === undefined
          ? "Rated-title count and mean rating: unknown."
          : `${integer.format(count)} rated titles with this facet, average ${decimal.format(mean)} / 10.`}</p>
        <p>Overall mean rating: {overall === null || overall === undefined ? "unknown" : `${decimal.format(overall)} / 10`}.</p>
        {segment.feedback_adjustment !== null
          ? <p>Adjusted by your likes/dislikes: {formatSigned(segment.feedback_adjustment)}.</p>
          : null}
        <EvidenceList evidence={segment.evidence} mode="ratings" fullRank={null} />
      </div>
    );
  }

  const signal = segment.kind === "community" ? "community" : "similar-viewers";
  return (
    <div className="why-segment-body">
      <p>This {signal} signal is not about your taste.</p>
      {!segment.signal_available ? <p>No signal data was available, so a neutral stand-in was used.</p> : null}
      {segment.kind === "community" ? (
        <dl className="why-facts">
          <div><dt>MAL mean score</dt><dd>{segment.community?.mean_score === null || segment.community?.mean_score === undefined ? "Unknown" : `${decimal.format(segment.community.mean_score)} / 10`}</dd></div>
          <div><dt>Scoring users</dt><dd>{segment.community?.scoring_users === null || segment.community?.scoring_users === undefined ? "Unknown" : integer.format(segment.community.scoring_users)}</dd></div>
        </dl>
      ) : null}
    </div>
  );
}

function CounterfactualExplanation({ why }: { why: Explanation }) {
  const windowCopy = why.history_window === null || why.history_window === undefined
    ? "from your recent-title window (size unavailable)"
    : `from your ${integer.format(why.history_window)} most recent titles`;
  return (
    <div className="why-explanation">
      <p className="details-note">The sequence model was rerun without parts of your history {windowCopy}. These are overlapping relative effects, not shares of a score.</p>
      <ImpactBar segments={why.segments} label="Relative model-score impacts" />
      <div className="why-segments">
        {why.segments.map((segment, index) => {
          const label = segment.kind === "history-other" ? "Your titles without genre labels" : `Your ${segment.label} titles`;
          return (
            <details className="why-segment" key={`${segment.kind}:${segment.label}:${index}`}>
              <summary>
                <span>{label}</span>
                <span className="why-value">{formatSigned(segment.value)} · {direction(segment.value)}</span>
                <span className="why-direction">{formatRankChange(why.full_rank, segment.rank_without)}</span>
              </summary>
              <div className="why-segment-body">
                <p>{segment.member_count === null ? "History-title count unavailable." : `${integer.format(segment.member_count)} titles in this group.`}</p>
                {segment.member_count !== null && why.history_window !== null && why.history_window !== undefined && segment.member_count === why.history_window
                  ? <p>Removing it leaves no history; the rank shown is a brand-new reader&apos;s rank.</p>
                  : null}
                <p>The group effect above and the single-title effects below can disagree; each number is shown as returned.</p>
                <EvidenceList evidence={segment.evidence} mode="counterfactual" fullRank={why.full_rank} />
              </div>
            </details>
          );
        })}
      </div>
      {why.influences.length ? (
        <section className="why-influences" aria-labelledby="strongest-effects">
          <h4 id="strongest-effects">Strongest individual history effects</h4>
          <EvidenceList evidence={why.influences} mode="influences" fullRank={why.full_rank} />
        </section>
      ) : null}
    </div>
  );
}

function ImpactBar({ segments, label }: { segments: ExplanationSegment[]; label: string }) {
  const negative = segments.filter((segment) => segment.value < 0);
  const positive = segments.filter((segment) => segment.value > 0);
  const negativeMagnitude = negative.reduce((sum, segment) => sum + Math.abs(segment.value), 0);
  const positiveMagnitude = positive.reduce((sum, segment) => sum + Math.abs(segment.value), 0);
  const scale = Math.max(negativeMagnitude, positiveMagnitude, 1);
  const description = segments.length
    ? `${label}: ${segments.map((segment) => `${segmentDisplayLabel(segment)} ${formatSigned(segment.value)}, ${direction(segment.value).toLocaleLowerCase()}`).join("; ")}`
    : `${label}: no effects were recorded`;

  return (
    <div className="impact-bar" role="img" aria-label={description}>
      <div className="impact-side" data-side="negative">
        {negative.map((segment, index) => <span key={`${segment.label}:${index}`} data-kind={segment.kind} style={{ width: `${Math.abs(segment.value) / scale * 100}%` }} />)}
      </div>
      <span className="impact-axis" aria-hidden="true" />
      <div className="impact-side" data-side="positive">
        {positive.map((segment, index) => <span key={`${segment.label}:${index}`} data-kind={segment.kind} style={{ width: `${Math.abs(segment.value) / scale * 100}%` }} />)}
      </div>
    </div>
  );
}

function EvidenceList({ evidence, mode, fullRank }: {
  evidence: ExplanationEvidence[];
  mode: "ratings" | "counterfactual" | "influences";
  fullRank: number | null;
}) {
  const [page, setPage] = useState(0);
  if (!evidence.length) return <p>No title evidence was recorded.</p>;
  const pageCount = Math.ceil(evidence.length / EVIDENCE_PAGE_SIZE);
  const currentPage = Math.min(page, pageCount - 1);
  const shown = evidence.slice(currentPage * EVIDENCE_PAGE_SIZE, (currentPage + 1) * EVIDENCE_PAGE_SIZE);
  return (
    <>
      <ul className="why-evidence">
        {shown.map((item, index) => (
          <li key={`${item.mal_id ?? "unknown"}:${item.title}:${index}`}>
            {mode === "influences" ? (
              <><strong>Because you {statusVerb(item.list_status)} {item.title}</strong><span>Without it, {formatRankChange(fullRank, item.rank_without)} · effect {effectText(item.value)}.</span></>
            ) : (
              <><strong>{item.title}</strong><span>Your score: {item.user_score === null ? "unknown" : `${decimal.format(item.user_score)} / 10`}.</span>
                {mode === "counterfactual" ? <span>Status: {statusLabel(item.list_status)} · single-title effect {effectText(item.value)} · {formatRankChange(fullRank, item.rank_without)}.</span> : null}</>
            )}
          </li>
        ))}
      </ul>
      {pageCount > 1 ? (
        <nav className="evidence-pages" aria-label="Title evidence pages">
          <button type="button" className="pill" disabled={currentPage === 0} onClick={() => setPage((value) => Math.max(0, value - 1))}>Previous evidence</button>
          <span>Page {integer.format(currentPage + 1)} of {integer.format(pageCount)}</span>
          <button type="button" className="pill" disabled={currentPage === pageCount - 1} onClick={() => setPage((value) => Math.min(pageCount - 1, value + 1))}>Next evidence</button>
        </nav>
      ) : null}
    </>
  );
}

function UnavailableExplanation({ reason }: { reason: string | null }) {
  const copy: Record<string, string> = {
    "engine-cannot-explain": "this engine can't explain its picks",
    "explanation-failed": "couldn't compute an explanation this time",
    "explanation-unavailable": "couldn't compute an explanation this time",
    "outside-ranked-candidates": "not in the ranked set",
    "score-parts-missing": "no score breakdown was recorded",
  };
  return (
    <div className="why-unavailable">
      <h4>This pick can&apos;t be explained</h4>
      <p>{reason ? copy[reason] ?? "An explanation is unavailable for this pick." : "No explanation was recorded for this pick."}</p>
    </div>
  );
}

function formatSigned(value: number): string {
  return `${value >= 0 ? "+" : ""}${decimal.format(value)}`;
}

function segmentDisplayLabel(segment: ExplanationSegment): string {
  if (segment.kind !== "taste" || !segment.facet) return segment.label;
  const facet = segment.facet.replaceAll("-", " ");
  return `${facet.charAt(0).toLocaleUpperCase()}${facet.slice(1)} · ${segment.label}`;
}

function effectText(value: number | null): string {
  return value === null ? "unavailable" : `${formatSigned(value)} · ${direction(value).toLocaleLowerCase()}`;
}

function direction(value: number): string {
  if (value > 0) return "Raised it";
  if (value < 0) return "Held it back";
  return "No change";
}

function formatRankChange(fullRank: number | null, rankWithout: number | null): string {
  if (fullRank === null || rankWithout === null) return "Rank change unavailable";
  return `#${integer.format(fullRank)} → #${integer.format(rankWithout)}`;
}

function statusVerb(status: string | null): string {
  const normalized = status?.trim().toLocaleLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (normalized === "completed") return "watched";
  if (normalized === "watching") return "are watching";
  if (normalized === "dropped") return "dropped";
  if (normalized === "on_hold") return "put on hold";
  if (normalized === "plan_to_watch") return "plan to watch";
  return "had in your recent history:";
}

function statusLabel(status: string | null): string {
  if (!status) return "unknown";
  return status.replaceAll("_", " ").replaceAll("-", " ");
}
