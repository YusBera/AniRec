import type { RecommendationViewModel } from "../api/types";

const integer = new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 });

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

/**
 * The card's personal-fit line, worded as the desktop words it
 * (`RecommendationViewModel.personal_match_text`): a rank inside the engine's
 * ordering, never a percentage. Both numbers come from the API; a missing one
 * is stated in words.
 */
export function fitRankText(model: RecommendationViewModel): string {
  if (model.fit_rank === null || model.fit_rank === undefined || model.fit_pool_size === null || model.fit_pool_size === undefined) {
    return "Personal match unavailable";
  }
  return `Ranked #${integer.format(model.fit_rank)} of ${integer.format(model.fit_pool_size)} for you`;
}
