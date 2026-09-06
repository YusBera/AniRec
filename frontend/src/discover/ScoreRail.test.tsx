/**
 * The invariant the product is built on: the parts of an explanation add up to
 * the score shown, and the community term is never presented as one of the
 * user's own genres. tests/test_scoring_invariants.py states these for the
 * engine; this states the presentation half.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Breakdown, ScoreRail, isCommunityTerm, toneFor } from "./ScoreRail";

const CONTRIBUTIONS = [
  { label: "Psychological", value: 44.1 },
  { label: "Thriller", value: 26.8 },
  { label: "Supernatural", value: 5.2 },
  { label: "Community rating", value: 16.3 },
];

describe("score rail", () => {
  it("gives the community term the system colour, never a taste colour", () => {
    expect(toneFor({ label: "Community rating", value: 16.3 }, 0)).toBe("x");
    expect(toneFor({ label: "Similar viewers", value: 4 }, 1)).toBe("x");
    expect(toneFor({ label: "Psychological", value: 44.1 }, 0)).toBe("a");
  });

  it("identifies the community term the same way the Qt side does", () => {
    expect(isCommunityTerm("Community rating")).toBe(true);
    expect(isCommunityTerm("Similar viewers")).toBe(true);
    expect(isCommunityTerm("Supernatural")).toBe(false);
  });

  it("gives every positive term a share proportional to its value", () => {
    const { container } = render(
      <ScoreRail contributions={CONTRIBUTIONS} score={92.4} available />,
    );
    const segments = [...container.querySelectorAll<HTMLElement>(".rail-seg")];
    expect(segments).toHaveLength(4);
    const widths = segments.map((node) => Number.parseFloat(node.style.width));
    // Proportions of the filled length, so they total the score.
    expect(widths.reduce((sum, value) => sum + value, 0)).toBeCloseTo(92.4, 1);
    // Ordering is preserved, and the largest term is the widest.
    expect(Math.max(...widths)).toBeCloseTo(widths[0]!, 5);
  });

  it("never draws a negative term as positive width", () => {
    const { container } = render(
      <ScoreRail
        contributions={[
          { label: "Action", value: 30 },
          { label: "Ecchi", value: -12 },
        ]}
        score={30}
        available
      />,
    );
    expect(container.querySelectorAll(".rail-seg")).toHaveLength(1);
  });

  it("renders an unavailable match as an empty rail, not a zero-width one", () => {
    const { container } = render(
      <ScoreRail contributions={[]} score={0} available={false} />,
    );
    expect(container.querySelectorAll(".rail-seg")).toHaveLength(0);
    expect(screen.getByRole("img")).toHaveAccessibleName("Match not available");
  });

  it("describes the breakdown to a screen reader without a legend", () => {
    render(<ScoreRail contributions={CONTRIBUTIONS} score={92.4} available />);
    expect(screen.getByRole("img")).toHaveAccessibleName(
      "Match 92.4%: Psychological 44.1, Thriller 26.8, Supernatural 5.2, Community rating 16.3",
    );
  });
});

describe("breakdown", () => {
  it("discloses a mismatch instead of silently implying that the parts reconcile", () => {
    render(<Breakdown contributions={[{ label: "Adventure", value: 38.9 }]} score={34.7} />);
    expect(screen.getByText(/does not fully reconcile/)).toHaveTextContent("38.9");
    expect(screen.getByText(/does not fully reconcile/)).toHaveTextContent("34.7%");
  });

  it("does not turn a missing match into a numeric zero", () => {
    render(<Breakdown contributions={[]} score={0} available={false} />);
    expect(screen.getByText("Personal match is not available.")).toBeInTheDocument();
    expect(screen.queryByText("0.0")).not.toBeInTheDocument();
  });
  it("shows a total that reconciles with the score", () => {
    render(<Breakdown contributions={CONTRIBUTIONS} score={92.4} />);
    expect(screen.getByText("92.4")).toBeInTheDocument();
  });

  it("keeps the sign on a negative contribution", () => {
    const { container } = render(
      <Breakdown contributions={[{ label: "Ecchi", value: -12.5 }]} score={-12.5} />,
    );
    // Scoped to the row: the total below it reads -12.5 as well, and a bare
    // text query cannot tell the two apart.
    expect(container.querySelector(".breakdown-row .val")).toHaveTextContent("-12.5");
  });

  it("adds a plus to a positive one, so the sign is never implied", () => {
    const { container } = render(
      <Breakdown contributions={[{ label: "Action", value: 30 }]} score={30} />,
    );
    expect(container.querySelector(".breakdown-row .val")).toHaveTextContent("+30.0");
  });
});
