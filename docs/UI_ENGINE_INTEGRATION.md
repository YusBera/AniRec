# Latest UI and v3 engine integration

Verified on 20 September 2026. This clone combines GitHub UI branch
`codex/library-led-workspace-handoff` at `82f7cbd` with the local v3 ONNX
serving and recommendation activity changes. Integration branch:
`codex/ui-v3-engine`. Changes are local and uncommitted.

The original sibling AniRec checkout and its uncommitted work were preserved.
This clone is under `AniRecTrainer/work/anirec-ui`; `work` is ignored by the
parent Trainer repository, so integration changes belong to this clone's Git
repository.

## Launch locally

From this clone's root, in a PowerShell terminal:

```powershell
$env:ANIREC_MODEL_BUNDLE = 'C:\Users\yusuf\AniRecTrainerWork\exports\sasrec-typed-d256-p6-seed2-split56534d1a96-v3'
& 'C:\Users\yusuf\OneDrive\Desktop\projects\AniRec\.venv\Scripts\python.exe' -B -m AniRec.api --port 8770
```

In another terminal, from this clone's `frontend` directory:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173/>. The API uses AniRec's existing local profile and
data directory. The interpreter currently comes from the original checkout's
virtual environment. Both servers bind to loopback. Stop an existing preview
before starting another instance.

## Verified behavior

- Generated API schema verification, TypeScript checks, 61 frontend tests and
  production build passed.
- 66 targeted Python tests passed across workspace API, ONNX engine, pipeline,
  API boundary, activity events and user data.
- Real ONNX inspection in this clone ranked 22,210 eligible candidates with no
  fallback (about 20 ms inference for the inspected history).
- Discover, My Library and Settings load with the existing local profile.
- Discover activity does not record hidden Discover cards while another
  workspace page is active. Library interactions are not attributed to
  Discover impressions.

The initial Discover feed is saved output from the previous heuristic engine.
Launching with a model bundle does not regenerate or relabel saved results.
The ONNX inspection used an anonymous evaluation history; fresh generation
with the active personal profile still needs to be checked separately.
Recommendation activity remains opt-in and local-only.

See `ONNX_MODEL_SERVING.md` for model selection and fallback semantics and
`RECOMMENDATION_ACTIVITY.md` for logging behavior. UI refinement remains
deferred.
