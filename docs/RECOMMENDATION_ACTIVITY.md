# AniRec recommendation activity

Implemented in the sibling AniRec checkout (feat/react-fastapi-boundary) on
17 September 2026. PySide and React/API instrument the existing engine.
Logging does not depend on a transformer, change ranking, or train a model.

## Controls and storage

Collection is off by default, separately per profile. Native: Activity > Save
activity on this device. React: expand Recommendation activity. Both provide
Clear saved activity. Demo/ephemeral feeds never persist activity.

The shared service writes recommendation_activity.json and
recommendation_events.sqlite in the existing local profile directory. Nothing
is uploaded. Storage is bounded to 50,000 events; rows older than 90 days expire
on writes or status checks. Unopened profiles have no scheduled cleanup.

## Event meanings

| Action | Meaning |
| --- | --- |
| impression | At least 50% of a card/row visible continuously for 1 second |
| detail_open | Inspector opened, including native next/previous navigation |
| external_open | Normal external-open action handed to the platform; destination loading is not established |
| watch_later_add / watch_later_remove | Local Watch Later write succeeded |
| dismiss / restore | Local Not Interested write succeeded |

Watch Later is not a MAL list update or evidence of watching. A detail open is
the click outcome; do not count it twice as independent positive feedback.
Browser modifier-clicks bypassing the normal handler are not collected.

Visibility is sampled every 250ms. Native uses viewport geometry (the title cell
for table rows); React uses viewport intersection and a center hit test. Focus
loss, hidden documents and the inspector interrupt dwell. Collapsed franchise
bundles are excluded. This conservative definition can undercount brief visits
and does not detect every form of partial window occlusion.

## Attribution and failures

Events store schema version, event UUID, local timestamp, presentation/request
UUID, ordered-feed fingerprint, engine version, MAL ID, display position,
original model rank and surface. Identical cached rankings from the same engine
share a fingerprint; request UUID distinguishes presentations. New pipeline
results carry the ranking engine ID and version, including the ONNX checkpoint
hash prefix. Older saved feeds retain the legacy-app-<version> label.

HTTP requests name the originating profile to reject stale events after profile
changes; this field is not stored in the event table. No usernames, titles,
tokens, URLs, notes, searches or full histories are stored as event fields.
The containing profile directory associates activity with the local user;
this is not anonymous data.

Event UUID deduplicates retries. Impressions deduplicate by presentation, item
and surface. React captures position before optimistic removal, records after
the feedback write succeeds, and drains pending requests before clearing.
Native records after state persistence succeeds. Storage failures do not block
normal recommendation actions.

## Implementation and evidence

- Shared storage: AniRec/services/recommendation_event_service.py
- Native: AniRec/gui/recommendation_page.py, card, row and detail dialog
- API: AniRec/api/models.py and AniRec/api/app.py
- React: frontend/src/discover/useRecommendationActivity.ts

Tests cover opt-in, deduplication, expiry, bounded retention, malformed settings,
privacy allowlisting, storage failure, demo exclusion, Qt viewport sampling,
saves, stale feeds/items/profiles, browser dwell and in-flight clearing.
API types are generated from Python models. Offscreen native and desktop/narrow
browser rendering were inspected. An isolated real-browser fixture produced
one visible impression, detail open and Watch Later addition at position 1.

## Next use of the data

Before population-wide collection, define consent, transport, deletion and
versioned model attribution. Link exposures and outcomes; an unclicked or
unseen title is not automatically a negative. Choose observation windows and
an evaluation design before using these events for training or promotion.
