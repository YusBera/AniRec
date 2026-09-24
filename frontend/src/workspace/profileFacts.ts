/**
 * The "NOT ON YOUR MAL PROFILE" board, as `gui/profile_page.py` composes it:
 * `board_facts = reading_facts + receipt_facts + unlisted_facts`, broad to
 * specific. Each fact is a mark, a legend, a figure and a sentence, with the
 * anime behind the claim where the profile names them.
 *
 * Nothing is computed here. Every figure is a field the API returned,
 * formatted the way the desktop's `*_text` properties format it; a fact whose
 * field is absent is left off the board rather than shown as N/A.
 */

import type { TasteProfile } from "../api/types";
import type { IconName } from "../assets/Icon";

export interface Fact {
  icon: IconName;
  legend: string;
  value: string;
  caption: string;
  /** "against" is drawn in the danger role, as `tone="against"` is on the desktop. */
  tone: "you" | "against" | "";
  evidence: string[];
}

type Titles = readonly { title: string; your_score?: number | null }[] | null | undefined;

const DASH = "N/A";
export const countText = (value: number | null | undefined) => value == null ? DASH : Math.trunc(value).toLocaleString("en-US");
export const scoreText = (value: number | null | undefined, places = 1) => value == null ? DASH : value.toFixed(places);
const wholeScore = (value: number | null | undefined) => value == null ? DASH : value.toFixed(0);

const READING_ICONS: Record<string, IconName> = {
  "community-sync": "fact-sync",
  "rating-bias": "fact-bias",
  contrarian: "fact-contrarian",
  completion: "fact-completion",
  mainstream: "fact-mainstream",
};

const SEASON_ICONS: Record<string, IconName> = {
  winter: "fact-season-winter",
  spring: "fact-season-spring",
  summer: "fact-season-summer",
  fall: "fact-season-fall",
  autumn: "fact-season-fall",
};

/** `_evidence`: up to two titles per group, best first, no title twice. */
function evidence(...groups: Titles[]): string[] {
  const seen = new Set<string>();
  const lines: string[] = [];
  for (const titles of groups) {
    for (const entry of (titles ?? []).slice(0, 2)) {
      const name = (entry.title ?? "").trim();
      if (!name || seen.has(name.toLocaleLowerCase())) continue;
      seen.add(name.toLocaleLowerCase());
      lines.push(`${name} ${wholeScore(entry.your_score)}`);
    }
  }
  return lines;
}

const titleCase = (value: string) => value.toLocaleLowerCase().replace(/\b\w/g, (letter) => letter.toLocaleUpperCase());

export function boardFacts(profile: TasteProfile): Fact[] {
  const facts: Fact[] = [];

  for (const reading of profile.fingerprint ?? []) {
    facts.push({
      icon: READING_ICONS[reading.reading_id] ?? "fact-unknown",
      legend: reading.caption,
      value: reading.value_text ?? DASH,
      caption: reading.detail || reading.label || "",
      tone: reading.tone === "you" ? "you" : "",
      evidence: [],
    });
  }

  const biggest = profile.hype_killers?.biggest;
  if (biggest?.title) facts.push({
    icon: "fact-hype", legend: "BIGGEST HYPE KILL", value: biggest.title, tone: "against", evidence: [],
    caption: `You said ${wholeScore(biggest.your_score)}. Everyone else said ${scoreText(biggest.community_score, 2)}.`,
  });
  const deepest = profile.hidden_gems?.deepest;
  if (deepest?.title) facts.push({
    icon: "fact-gem", legend: "DEEPEST CUT", value: deepest.title, tone: "you", evidence: [],
    caption: `You said ${wholeScore(deepest.your_score)}. Everyone else said ${scoreText(deepest.community_score, 2)}.`,
  });
  const rewatch = profile.habits?.most_rewatched;
  if (rewatch?.title) facts.push({
    icon: "fact-rewatch", legend: "MOST REWATCHED", value: rewatch.title, tone: "you", evidence: [],
    caption: `You have been back through it ${rewatch.watches == null ? DASH : `${rewatch.watches}×`}.`,
  });

  const nemesis = profile.studios?.nemesis;
  if (nemesis?.name) facts.push({
    icon: "fact-nemesis", legend: "NEMESIS", value: nemesis.name, tone: "against",
    caption: `Your nemesis studio. ${countText(nemesis.watched)} watched, averaging ${scoreText(nemesis.average, 2)}.`,
    evidence: evidence(nemesis.lowest?.length ? nemesis.lowest : nemesis.titles),
  });
  const trusted = profile.studios?.most_trusted;
  if (trusted?.name) facts.push({
    icon: "fact-trusted", legend: "MOST TRUSTED", value: trusted.name, tone: "you",
    caption: `The studio you trust most, at ${scoreText(trusted.average, 2)} across their work.`,
    evidence: evidence(trusted.titles),
  });
  const divisive = profile.genres?.divisive;
  if (divisive?.name) facts.push({
    icon: "fact-divisive", legend: "MOST DIVISIVE", value: divisive.name, tone: "you",
    caption: "Your most divisive genre. You either love it or you do not.",
    evidence: evidence(divisive.titles, divisive.lowest),
  });
  const golden = profile.eras?.golden;
  if (golden?.label) facts.push({
    icon: "fact-era", legend: "GOLDEN ERA", value: golden.label, tone: "you", evidence: [],
    caption: `Your golden era, averaging ${scoreText(golden.average, 2)}.`,
  });
  const season = (profile.eras?.season_of_choice ?? "").trim();
  if (season) facts.push({
    icon: SEASON_ICONS[season.toLocaleLowerCase()] ?? "fact-unknown", legend: "SEASON OF CHOICE", value: titleCase(season), tone: "you", evidence: [],
    caption: `You rate ${season.toLocaleLowerCase()} premieres higher than any other season.`,
  });
  const gems = profile.hidden_gems?.rate_text;
  if (gems && gems !== DASH) facts.push({
    icon: "fact-gem", legend: "DEEP CUTS", value: gems, tone: "you", evidence: [],
    caption: "of your list is material almost nobody else has rated.",
  });
  const hype = profile.hype_killers?.count;
  if (hype) facts.push({
    icon: "fact-hype", legend: "HYPE KILLED", value: String(hype), tone: "against", evidence: [],
    caption: "widely loved shows you rated well below the crowd.",
  });
  return facts;
}
