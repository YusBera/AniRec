"""HTTP boundary over the existing AniRec service layer.

Run it with::

    .\\.venv\\Scripts\\python.exe -m AniRec.api

The desktop application does not use this yet and is unaffected by it. It
exists so a second client can be written against the same services, and so
the operation model - keys, single-flight, cooperative cancellation, the
terminal event sequence - has a transport that is not Qt signals.
"""

from .app import create_app
from .container import ApiContainer, build_container
from .operations import (
    OperationAlreadyRunningError,
    OperationRecord,
    OperationRegistry,
    OperationState,
)

__all__ = [
    "ApiContainer",
    "OperationAlreadyRunningError",
    "OperationRecord",
    "OperationRegistry",
    "OperationState",
    "build_container",
    "create_app",
]
