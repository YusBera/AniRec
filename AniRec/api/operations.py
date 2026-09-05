"""The transport-independent half of ``WorkerController``.

This is the same object the desktop already has, with ``QThread`` swapped for
a worker thread and Qt signals swapped for a per-operation event log. The
semantics are copied deliberately, because they are the ones the application's
behaviour was tuned against:

* an operation is identified by ``operation_key(kind, profile_id)``, the exact
  key ``gui/workers/operations.py`` already mints;
* one running operation per key, and a second start is refused rather than
  queued - the guard that stops "Recommend 5 more" from launching twice;
* a finished-but-not-yet-reaped handle is retired on the next start instead of
  refusing it, which is the fix recorded as BUG1 in ``controller.py``;
* cancellation is cooperative through ``CancellationToken``, never forced;
* the terminal event sequence is ``started`` -> (``progress``|``step``)* ->
  (``result``|``error``|``cancelled``) -> ``finished``.

One thing genuinely differs, and it is a consequence of HTTP rather than a
design choice. A Qt client connects its slots *before* the worker starts, so
it cannot miss an event. An HTTP client learns the operation id from the
response to the request that started it, by which point the work may already
have emitted several events - or finished. So every event is appended to a
retained log and the stream replays that log before following the live queue.
A client that connects late sees the whole operation; a client that reconnects
after a dropped connection sees it again rather than hanging on a stream that
will never speak. This is why every event carries a monotonic ``seq``.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterator

from ..application.pipeline import CancellationToken
from ..errors import CancelledError, presentable_error
from ..models import PipelineProgress


class OperationAlreadyRunningError(RuntimeError):
    """Raised when a key that is still running is started again."""


class OperationState(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


# How long a finished operation's event log is kept so a client that asks late
# still gets an answer. Ten minutes is well past any reasonable page reload
# and far short of a memory concern at these volumes.
RETENTION_SECONDS = 600.0


@dataclass
class _Event:
    seq: int
    event: str
    data: dict[str, Any]


@dataclass
class OperationRecord:
    key: str
    kind: str
    profile_id: str
    state: OperationState = OperationState.RUNNING
    token: CancellationToken = field(default_factory=CancellationToken)
    events: list[_Event] = field(default_factory=list)
    started_at: float = field(default_factory=time.monotonic)
    finished_at: float | None = None
    condition: threading.Condition = field(
        default_factory=lambda: threading.Condition(threading.Lock())
    )

    @property
    def is_running(self) -> bool:
        return self.state is OperationState.RUNNING

    def append(self, event: str, data: dict[str, Any] | None = None) -> None:
        with self.condition:
            self.events.append(_Event(len(self.events), event, dict(data or {})))
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        return {
            "id": self.key,
            "kind": self.kind,
            "profile_id": self.profile_id,
            "state": self.state.value,
            "event_count": len(self.events),
        }

    def follow(self, *, poll_seconds: float = 0.5) -> Iterator[dict[str, Any]]:
        """Replay every event, then follow live ones until ``finished``.

        Yields plain dictionaries so the caller decides the wire format; the
        SSE route is the only thing that knows about ``text/event-stream``.
        """
        index = 0
        while True:
            with self.condition:
                while index >= len(self.events):
                    if not self.is_running:
                        return
                    # A bounded wait rather than an unbounded one, so a
                    # disconnected client's generator is collected when the
                    # server tears the response down.
                    self.condition.wait(poll_seconds)
                    if index >= len(self.events) and not self.is_running:
                        return
                pending = list(self.events[index:])
                index = len(self.events)
            for item in pending:
                yield {"seq": item.seq, "event": item.event, "data": item.data}
                if item.event == "finished":
                    return


class OperationRegistry:
    """Owns every in-flight operation and its retained event log."""

    def __init__(self, *, retention_seconds: float = RETENTION_SECONDS) -> None:
        self._records: dict[str, OperationRecord] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self._retention = retention_seconds

    # -- inspection -------------------------------------------------------

    def get(self, key: str) -> OperationRecord | None:
        with self._lock:
            return self._records.get(key)

    def is_running(self, key: str) -> bool:
        record = self.get(key)
        return bool(record and record.is_running)

    def active(self) -> tuple[OperationRecord, ...]:
        with self._lock:
            return tuple(r for r in self._records.values() if r.is_running)

    def all(self) -> tuple[OperationRecord, ...]:
        with self._lock:
            return tuple(self._records.values())

    # -- lifecycle --------------------------------------------------------

    def start(
        self,
        key: str,
        kind: str,
        profile_id: str,
        handler: Callable[[CancellationToken, Callable[[PipelineProgress], None]], Any],
        *,
        serialize_result: Callable[[Any], dict[str, Any]] | None = None,
    ) -> OperationRecord:
        key = key.strip()
        if not key:
            raise ValueError("operation_key is required.")
        with self._lock:
            self._evict_expired_locked()
            existing = self._records.get(key)
            if existing is not None and existing.is_running:
                raise OperationAlreadyRunningError(
                    f"Operation is already running: {key}"
                )
            # A finished handle is retired rather than refusing the next start.
            # Same reasoning as the BUG1 fix in controller.py.
            record = OperationRecord(key=key, kind=kind, profile_id=profile_id)
            self._records[key] = record

        def report(progress: PipelineProgress) -> None:
            record.append("progress", progress.to_dict())
            record.append(
                "step", {"stage_id": progress.stage_id, "message": progress.message}
            )

        def run() -> None:
            record.append("started", {"kind": kind, "profile_id": profile_id})
            try:
                record.token.raise_if_cancelled()
                result = handler(record.token, report)
                record.token.raise_if_cancelled()
            except CancelledError:
                record.state = OperationState.CANCELLED
                record.append("cancelled", {})
            except Exception as error:  # noqa: BLE001 - mapped, never re-raised
                record.state = OperationState.FAILED
                record.append("error", error_payload(error))
            else:
                record.state = OperationState.SUCCEEDED
                payload = serialize_result(result) if serialize_result else {}
                record.append("result", payload)
            finally:
                record.finished_at = time.monotonic()
                record.append("finished", {"state": record.state.value})

        thread = threading.Thread(
            target=run, name=f"AniRecOperation-{key}", daemon=True
        )
        with self._lock:
            self._threads[key] = thread
        thread.start()
        return record

    def cancel(self, key: str) -> bool:
        record = self.get(key)
        if record is None or not record.is_running:
            return False
        record.token.cancel()
        return True

    def shutdown(self, timeout_seconds: float = 5.0) -> bool:
        """Cancel everything cooperatively and wait. Never forced."""
        with self._lock:
            records = tuple(self._records.values())
            threads = tuple(self._threads.values())
        for record in records:
            record.token.cancel()
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        stopped = True
        for thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(remaining)
            if thread.is_alive():
                stopped = False
        return stopped

    def _evict_expired_locked(self) -> None:
        now = time.monotonic()
        stale = [
            key
            for key, record in self._records.items()
            if record.finished_at is not None
            and now - record.finished_at > self._retention
        ]
        for key in stale:
            self._records.pop(key, None)
            self._threads.pop(key, None)


def error_payload(error: Exception) -> dict[str, Any]:
    """The same redacted, traceback-free model the desktop error dialog gets."""
    presentable = presentable_error(error)
    return {
        "code": presentable.code,
        "title": presentable.title,
        "description": presentable.description,
        "solution": presentable.solution,
        "retryable": presentable.retryable,
    }
