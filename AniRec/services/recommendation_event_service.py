"""Opt-in, local-only recommendation activity. No network or personal text."""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from time import monotonic
from uuid import UUID, uuid4

from .. import __version__
from ..infrastructure.paths import profile_dir

EVENTS = frozenset({"impression", "detail_open", "external_open", "watch_later_add",
                    "watch_later_remove", "dismiss", "restore"})
SURFACES = frozenset({"native_cards", "native_list", "native_table", "web_cards"})
MAX_EVENTS = 50_000
RETENTION_SECONDS = 90 * 86400
MODEL_VERSION = f"legacy-app-{__version__}"


def activity_model_version(user_stats=None) -> str:
    stats = user_stats or {}
    engine_id = str(stats.get("ranking_engine_id") or "").strip()
    engine_version = str(stats.get("ranking_engine_version") or "").strip()
    if not engine_id or not engine_version:
        return MODEL_VERSION
    return f"{engine_id}:{engine_version}"[:200]


def feed_fingerprint(models, model_version=MODEL_VERSION) -> str:
    # Identifies the presented ranking, not an invented training artifact or
    # generation timestamp. Cached identical feeds deliberately share this ID.
    payload = {
        "model_version": str(model_version),
        "rows": [(m.mal_id, m.rank, str(m.personal_match)) for m in models],
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


class RecommendationEventService:
    def __init__(self, root_override=None):
        self.root_override = root_override
        self._last_expiry = {}

    def _root(self, profile):
        return profile_dir(profile, self.root_override)

    def status(self, profile):
        enabled = False
        path = self._root(profile) / "recommendation_activity.json"
        if path.exists():
            try:
                settings = json.loads(path.read_text(encoding="utf-8"))
                enabled = isinstance(settings, dict) and settings.get("enabled") is True
            except (ValueError, OSError):
                pass
        # Expire old activity even when collection is off. No files are created
        # by checking a profile that has never recorded activity.
        database = self._root(profile) / "recommendation_events.sqlite"
        if database.exists() and monotonic() - self._last_expiry.get(profile, -float("inf")) >= 60:
            self._last_expiry[profile] = monotonic()
            try:
                with closing(sqlite3.connect(database, timeout=0.05)) as conn, conn:
                    conn.execute("DELETE FROM events WHERE recorded_at < ?",
                                 (int(datetime.now(timezone.utc).timestamp()) - RETENTION_SECONDS,))
            except (OSError, sqlite3.Error):
                pass
        return {"enabled": enabled, "local_only": True, "retention_days": 90}

    def set_enabled(self, profile, enabled):
        root = self._root(profile)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "recommendation_activity.json"
        tmp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps({"enabled": bool(enabled)}), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
        return self.status(profile)

    def _connect(self, profile):
        root = self._root(profile)
        root.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(root / "recommendation_events.sqlite", timeout=0.2)
        conn.execute("""CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY, recorded_at INTEGER NOT NULL,
            request_id TEXT NOT NULL, feed_id TEXT NOT NULL, model_version TEXT NOT NULL,
            action TEXT NOT NULL, mal_id INTEGER NOT NULL, position INTEGER NOT NULL,
            model_rank INTEGER, surface TEXT NOT NULL, schema_version INTEGER NOT NULL DEFAULT 1
        )""")
        conn.execute("""CREATE UNIQUE INDEX IF NOT EXISTS one_impression
            ON events(request_id, mal_id, surface) WHERE action='impression'""")
        conn.execute("CREATE INDEX IF NOT EXISTS activity_time ON events(recorded_at)")
        return conn

    def clear(self, profile):
        path = self._root(profile) / "recommendation_events.sqlite"
        if path.exists():
            with closing(self._connect(profile)) as conn, conn:
                conn.execute("PRAGMA secure_delete=ON")
                conn.execute("DELETE FROM events")
            # Compact the local activity store after the explicit clear action.
            with closing(sqlite3.connect(path)) as conn:
                conn.execute("VACUUM")

    def record(self, profile, *, request_id, feed_id, action, mal_id, position,
               model_rank=None, surface, event_id=None, model_version=MODEL_VERSION):
        if not profile or not self.status(profile)["enabled"]:
            return False
        if action not in EVENTS or surface not in SURFACES:
            raise ValueError("unknown activity action or surface")
        request_id = str(UUID(str(request_id)))
        event_id = str(UUID(str(event_id))) if event_id else str(uuid4())
        if len(feed_id) != 64 or any(c not in "0123456789abcdef" for c in feed_id):
            raise ValueError("invalid feed fingerprint")
        if type(mal_id) is not int or mal_id <= 0 or type(position) is not int or position < 1:
            raise ValueError("invalid anime or display position")
        if model_rank is not None and (type(model_rank) is not int or model_rank < 1):
            raise ValueError("invalid model rank")
        model_version = str(model_version).strip()
        if not model_version or len(model_version) > 200:
            raise ValueError("invalid model version")
        now = int(datetime.now(timezone.utc).timestamp())
        try:
            with closing(self._connect(profile)) as conn, conn:
                cursor = conn.execute("INSERT OR IGNORE INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                                      (event_id, now, request_id, feed_id, model_version, action,
                                       mal_id, position, model_rank, surface))
                inserted = cursor.rowcount == 1
                conn.execute("DELETE FROM events WHERE recorded_at < ?", (now - RETENTION_SECONDS,))
                conn.execute("""DELETE FROM events WHERE rowid IN
                    (SELECT rowid FROM events ORDER BY recorded_at DESC, rowid DESC LIMIT -1 OFFSET ?)""",
                             (MAX_EVENTS,))
                return inserted
        except (OSError, sqlite3.Error):
            # Logging must never prevent opening or saving a recommendation.
            return False


class ExposureTracker:
    """Continuous 50%-visibility dwell, supplied by the actual client viewport."""
    def __init__(self, dwell=1.0):
        self.dwell = dwell
        self.since = {}
        self.seen = set()

    def reset(self):
        self.since.clear()
        self.seen.clear()

    def update(self, visible_keys, now):
        visible = set(visible_keys)
        self.since = {k: t for k, t in self.since.items() if k in visible}
        ready = []
        for key in visible - self.seen:
            self.since.setdefault(key, now)
            if now - self.since[key] >= self.dwell:
                ready.append(key)
        return ready

    def acknowledge(self, key):
        self.seen.add(key)
        self.since.pop(key, None)
