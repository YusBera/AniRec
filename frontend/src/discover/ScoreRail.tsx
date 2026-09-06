/**
 * The score breakdown: the reference component of the whole design language.
 *
 * The product's one defensible claim is that a match percentage decomposes
 * into parts that sum. The rail is that claim, drawn. So two rules are load
 * bearing rather than decorative:
 *
 * - The community term is aqua, everything else is brass. "Mine vs everyone
 *   else's" has to be legible without a legend.
 * - Negative terms do not become positive width. A one-direction track that
 *   drew a penalty as length would misstate the arithmetic it exists to show.
 *   They appear in the rows beneath with their sign.
 */

import type { Contribution } from "../api/types";

/** Named the same way the Qt side identifies it, so the two cannot disagree. */
export function isCommunityTerm(name: string): boolean {
  const lowered = name.toLocaleLowerCase();
  return lowered.includes("community") || lowered.includes("viewer");
}

export type Tone = "a" | "b" | "c" | "x";

export function toneFor(contribution: Contribution, index: number): Tone {
  if (isCommunityTerm(contribution.label)) return "x";
  return (["a", "b", "c"] as const)[Math.min(index, 2)]!;
}

interface Props {
  contributions: Contribution[];
  score: number;
  available: boolean;
}

export function ScoreRail({ contributions, score, available }: Props) {
  const positive = contributions.filter((item) => item.value > 0);
  const total = positive.reduce((sum, item) => sum + item.value, 0);
  const filled = Math.max(0, Math.min(score, 100));

  if (!available || positive.length === 0) {
    return (
      <div
        className="rail"
        role="img"
        aria-label={available ? `Match ${score.toFixed(1)}%` : "Match not available"}
      >
        {available ? <div className="rail-seg" data-tone="a" style={{ width: `${filled}%` }} /> : null}
      </div>
    );
  }

  return (
    <div
      className="rail"
      role="img"
      aria-label={`Match ${score.toFixed(1)}%: ${positive
        .map((item) => `${item.label} ${item.value.toFixed(1)}`)
        .join(", ")}`}
    >
      {positive.map((item, index) => (
        <div
          key={item.label}
          className="rail-seg"
          data-tone={toneFor(item, index)}
          // Each segment's share of the filled length, so the widths are the
          // real proportions rather than an even split.
          style={{
            width: `${(item.value / total) * filled}%`,
            animationDelay: `${0.05 + index * 0.09}s`,
          }}
        />
      ))}
    </div>
  );
}

export function Breakdown({ contributions, score, available = true }: { contributions: Contribution[]; score: number; available?: boolean }) {
  if (!available) return <p className="details-note">Personal match is not available.</p>;
  if (contributions.length === 0) return <p className="details-note">No contribution breakdown is available for this score.</p>;
  const sum = contributions.reduce((total, item) => total + item.value, 0);
  return (
    <div className="breakdown">
      {contributions.map((item, index) => (
        <div
          key={item.label}
          className="breakdown-row"
          style={{ animationDelay: `${0.24 + index * 0.07}s` }}
        >
          <span className="swatch" data-tone={toneFor(item, index)} />
          <span className="name" title={item.label}>
            {item.label}
          </span>
          <span className="val">{item.value >= 0 ? "+" : ""}{item.value.toFixed(1)}</span>
        </div>
      ))}
      <div className="breakdown-sum">
        <span className="k">Total</span>
        {/* Shown against the score it must equal. If the two ever disagree the
            page says so rather than hiding it, which is the point. */}
        <span className="v" data-drift={Math.abs(sum - score) > 0.05 ? "true" : "false"}>
          {sum.toFixed(1)}
        </span>
      </div>
      {Math.abs(sum - score) > 0.05 ? <p className="breakdown-warning">The supplied contributions total {sum.toFixed(1)}, but the displayed match is {score.toFixed(1)}%. This explanation does not fully reconcile.</p> : null}
    </div>
  );
}
