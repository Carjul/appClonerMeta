from datetime import datetime, timezone
from bson import ObjectId


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def oid(value: str) -> ObjectId:
    return ObjectId(value)


def serialize_doc(doc: dict) -> dict:
    if not doc:
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out
