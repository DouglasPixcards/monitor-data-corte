from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_hash(data: dict | list) -> str:
    bruto = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def make_snapshot_id() -> str:
    return str(uuid.uuid4())


def make_execution_id() -> str:
    return str(uuid.uuid4())