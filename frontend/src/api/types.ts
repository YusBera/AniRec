/**
 * The API's types, aliased from the generated schema.
 *
 * Nothing here restates a field. Every type below is a pointer into
 * `generated/schema.d.ts`, which is produced from FastAPI's OpenAPI document
 * by `npm run generate:api-types` and is never edited by hand. Renaming a
 * field in `AniRec/api/models.py` and forgetting to regenerate is now a
 * failing `npm run verify:api-types`, and renaming one *and* regenerating
 * turns every stale usage in this app into a type error - which is the whole
 * reason for the indirection.
 *
 * These aliases exist rather than importing `components["schemas"][...]`
 * throughout the app so that the generated file stays an implementation
 * detail of this module: components can import `Feed`, not a subscript
 * expression, and the generator's output shape can change without touching
 * them.
 */

import type { components } from "./generated/schema";

type Schemas = components["schemas"];

// -- discover ---------------------------------------------------------------

export type Contribution = Schemas["Contribution"];
export type RecommendationViewModel = Schemas["RecommendationViewModelResponse"];
export type Catalogue = Schemas["Catalogue"];
export type LocalState = Schemas["LocalState"];
export type ProfileSummary = Schemas["ProfileSummary"];
export type Feed = Schemas["FeedResponse"];
export type FeedbackRequest = Schemas["FeedbackRequest"];
export type FeedbackResponse = Schemas["FeedbackResponse"];

// -- system and operations --------------------------------------------------

export type ApiError = Schemas["ApiError"];
export type ErrorEnvelope = Schemas["ErrorEnvelope"];
export type SystemState = Schemas["SystemStateResponse"];
export type OperationSnapshot = Schemas["OperationSnapshotResponse"];
export type OperationStartRequest = Schemas["OperationStartRequest"];

/** The lifecycle states an operation reports. Drawn from the schema's own union. */
export type OperationState = OperationSnapshot["state"];

// -- server-sent events -----------------------------------------------------
//
// Declared by hand, and this is the one place that is correct rather than
// lazy. FastAPI's OpenAPI document describes the /events route's response as
// a stream; it does not describe the shape of the individual frames inside
// it, because OpenAPI has no vocabulary for that. The Python side declares
// these in `AniRec.api.models.ProgressEvent` and `operations.error_payload`,
// and the route's docstring points here. If SSE frames ever gain more
// structure, the honest fix is a shared schema for them, not a generator
// that pretends to know.

export interface ProgressEvent {
  stage_id: string;
  message: string;
  current: number;
  total: number;
  cancellable: boolean;
}

/** The `event:` names the operations stream emits, in the order they can occur. */
export type OperationEventName =
  | "started"
  | "progress"
  | "step"
  | "result"
  | "error"
  | "cancelled"
  | "finished";
