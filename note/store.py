from __future__ import annotations

import fcntl
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib import request
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from python_header import get, get_bool


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def backend() -> str:
    value = get("NOTE_DB_BACKEND").lower()
    aliases = {"postgresql": "postgres", "pgsql": "postgres", "mysql": "mariadb", "sqlite3": "sqlite"}
    value = aliases.get(value, value)
    if value not in {"file", "sqlite", "mariadb", "postgres"}:
        raise ValueError(f"unsupported NOTE_DB_BACKEND: {value}")
    return value


def table_name() -> str:
    prefix = get("NOTE_DB_PREFIX")
    if prefix and not VALID_IDENTIFIER.fullmatch(prefix):
        raise ValueError("NOTE_DB_PREFIX must be empty or a valid SQL identifier")
    return f"{prefix}_notes" if prefix else "notes"


def database_url(kind: str) -> str:
    if kind == "sqlite":
        sqlite_dir = ROOT / "sqlite"
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_dir / 'note.sqlite3'}"
    driver = "postgresql+psycopg" if kind == "postgres" else "mysql+pymysql"
    host = get("NOTE_DB_URL")
    port = get("NOTE_DB_PORT")
    user = quote_plus(get("NOTE_DB_USER"))
    password = quote_plus(get("NOTE_DB_PW"))
    name = quote_plus(get("NOTE_DB_NAME"))
    return f"{driver}://{user}:{password}@{host}:{port}/{name}"


def timestamp(payload: dict) -> datetime:
    raw = payload.get("timestamp")
    return datetime.fromtimestamp(float(raw) / 1000).astimezone() if raw else datetime.now().astimezone()


def note_directory(payload: dict) -> Path:
    configured = Path(get("NOTE_PATH")).expanduser()
    if configured.is_absolute():
        return configured.resolve()
    return (Path(str(payload["workspace"])).expanduser() / configured).resolve()


def media_directory(payload: dict, now: datetime, kind: str) -> Path:
    if kind == "file":
        root = Path(str(payload["note_path"]))
    elif kind == "sqlite":
        root = ROOT / "sqlite" / "media"
    else:
        configured = Path(get("NOTE_MEDIA_PATH") or "media").expanduser()
        root = configured if configured.is_absolute() else ROOT / configured
    target = root.resolve() / f"{now:%Y.%m.%d}"
    target.mkdir(parents=True, exist_ok=True)
    return target


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    target = directory / f"{stem}{suffix}"
    index = 1
    while target.exists():
        target = directory / f"{stem}_{index:02d}{suffix}"
        index += 1
    return target


def persist_assets(payload: dict, now: datetime, kind: str) -> list[dict]:
    if not any((payload.get("media"), payload.get("contacts"), payload.get("location"))):
        return []
    directory = media_directory(payload, now, kind)
    assets: list[dict] = []
    for item in payload.get("media") or []:
        source = Path(str(item.get("source_path") or "")).expanduser()
        if not source.is_absolute():
            source = Path(str(item.get("workspace_dir") or payload.get("workspace") or ROOT)) / source
        source = source.resolve()
        if not source.is_file():
            continue
        mime_type = str(item.get("mime_type") or mimetypes.guess_type(source.name)[0] or "")
        suffix = source.suffix.lower() or mimetypes.guess_extension(mime_type) or ".bin"
        target = unique_path(directory, f"{now:%H.%M.%S}", suffix)
        shutil.copy2(source, target)
        assets.append(
            {
                "kind": "media",
                "path": str(target),
                "original_name": source.name,
                "mime_type": mime_type,
                "metadata": {},
            }
        )
    structured = [("contact", item) for item in payload.get("contacts") or []]
    if payload.get("location"):
        structured.append(("location", payload["location"]))
    for asset_kind, metadata in structured:
        path = ""
        if kind == "file":
            target = unique_path(directory, f"{now:%H.%M.%S}_{asset_kind}", ".json")
            target.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            path = str(target)
        assets.append(
            {
                "kind": asset_kind,
                "path": path,
                "original_name": "",
                "mime_type": "application/json",
                "metadata": metadata,
            }
        )
    return assets


def store_file(payload: dict, now: datetime) -> dict:
    directory = Path(str(payload["note_path"])).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{now:%Y.%m.%d}.md"
    message = str(payload["message"]).rstrip()
    with target.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.seek(0, os.SEEK_END)
        if handle.tell() and not target.read_text(encoding="utf-8").endswith("\n"):
            handle.write("\n")
        handle.write(f"{message}  \n{now:%H:%M:%S}\n\n")
        handle.flush()
        os.fsync(handle.fileno())
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    return {"path": str(target)}


def sql_context(kind: str):
    from sqlalchemy import Column, Date, Integer, String, Text, Time, create_engine
    from sqlalchemy.orm import DeclarativeBase, sessionmaker

    class Base(DeclarativeBase):
        pass

    class Note(Base):
        __tablename__ = table_name()
        id = Column(Integer, primary_key=True)
        message = Column(Text, nullable=False)
        note_date = Column(Date, nullable=False)
        note_time = Column(Time, nullable=False)
        channel = Column(String(80), nullable=False, default="")
        account_id = Column(String(255), nullable=False, default="")
        sender_id = Column(String(255), nullable=False, default="")
        message_id = Column(String(255), nullable=False, default="")

    class NoteAsset(Base):
        __tablename__ = f"{table_name()}_assets"
        id = Column(Integer, primary_key=True)
        note_id = Column(Integer, nullable=True, index=True)
        kind = Column(String(32), nullable=False)
        path = Column(Text, nullable=False, default="")
        original_name = Column(Text, nullable=False, default="")
        mime_type = Column(String(255), nullable=False, default="")
        metadata_json = Column(Text, nullable=False, default="{}")
        note_date = Column(Date, nullable=False)
        note_time = Column(Time, nullable=False)

    engine = create_engine(database_url(kind), future=True, pool_pre_ping=kind != "sqlite")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True), Note, NoteAsset


def store_sql(payload: dict, now: datetime, kind: str, assets: list[dict] | None = None) -> dict:
    factory, Note, NoteAsset = sql_context(kind)
    with factory.begin() as session:
        note_id = None
        if payload["message"]:
            row = Note(
                message=str(payload["message"]),
                note_date=now.date(),
                note_time=now.time().replace(tzinfo=None),
                channel=str(payload.get("channel") or ""),
                account_id=str(payload.get("account_id") or ""),
                sender_id=str(payload.get("sender_id") or ""),
                message_id=str(payload.get("message_id") or ""),
            )
            session.add(row)
            session.flush()
            note_id = row.id
        for asset in assets or []:
            session.add(
                NoteAsset(
                    note_id=note_id,
                    kind=asset["kind"],
                    path=asset["path"],
                    original_name=asset["original_name"],
                    mime_type=asset["mime_type"],
                    metadata_json=json.dumps(asset["metadata"], ensure_ascii=False),
                    note_date=now.date(),
                    note_time=now.time().replace(tzinfo=None),
                )
            )
    return {"id": note_id, "table": table_name(), "assets": assets or []}


def format_notes(rows: list[tuple[datetime, str]]) -> str:
    if not rows:
        return "No notes."
    lines: list[str] = []
    current_date = None
    for created, message in rows:
        date = created.strftime("%Y.%m.%d")
        if date != current_date:
            if lines:
                lines.append("")
            lines.extend([f"## {date}", ""])
            current_date = date
        lines.extend([f"{message.rstrip()}  ", created.strftime("%H:%M:%S"), ""])
    return "\n".join(lines).rstrip()


def show_file(payload: dict, cutoff: datetime | None) -> str:
    directory = Path(str(payload["note_path"])).expanduser().resolve()
    rows: list[tuple[datetime, str]] = []
    for target in sorted(directory.glob("????.??.??.md")) if directory.exists() else []:
        try:
            date = datetime.strptime(target.stem, "%Y.%m.%d").date()
        except ValueError:
            continue
        for block in target.read_text(encoding="utf-8").split("\n\n"):
            block_lines = block.rstrip().splitlines()
            if len(block_lines) < 2:
                continue
            try:
                created = datetime.combine(date, datetime.strptime(block_lines[-1].strip(), "%H:%M:%S").time()).astimezone()
            except ValueError:
                continue
            if cutoff is None or created >= cutoff:
                rows.append((created, "\n".join(block_lines[:-1]).rstrip()))
    return format_notes(rows)


def show_sql(kind: str, cutoff: datetime | None) -> str:
    factory, Note, _ = sql_context(kind)
    with factory() as session:
        records = session.query(Note).order_by(Note.note_date.asc(), Note.note_time.asc(), Note.id.asc()).all()
    rows = []
    for row in records:
        created = datetime.combine(row.note_date, row.note_time).astimezone()
        if cutoff is None or created >= cutoff:
            rows.append((created, row.message))
    return format_notes(rows)


def feedback(text: str) -> str:
    return text if get_bool("NOTE_FEEDBACK") else ""


def trigger_type() -> str:
    value = get("NOTE_TRIGGER_TYPE").lower()
    if value not in {"none", "webhook", "cli"}:
        raise ValueError(f"unsupported NOTE_TRIGGER_TYPE: {value}")
    return value


def trigger_configured() -> bool:
    return trigger_type() != "none" and bool(get("NOTE_TRIGGER"))


def prompt_text() -> str:
    configured = Path(get("NOTE_PROMPT")).expanduser()
    prompt_path = configured if configured.is_absolute() else ROOT / configured
    return prompt_path.read_text(encoding="utf-8").strip()


def trigger_environment(note: dict) -> dict[str, str]:
    return {
        "NOTE_PROMPT": prompt_text(),
        "NOTE_MESSAGE": str(note["message"]),
        "NOTE_DATE": str(note["date"]),
        "NOTE_TIME": str(note["time"]),
        "NOTE_PATH": str(note["note_path"]),
        "NOTE_CHANNEL": str(note.get("channel") or ""),
        "NOTE_ACCOUNT_ID": str(note.get("account_id") or ""),
        "NOTE_SENDER_ID": str(note.get("sender_id") or ""),
        "NOTE_MESSAGE_ID": str(note.get("message_id") or ""),
    }


def execute_trigger(note: dict) -> None:
    kind = trigger_type()
    target = get("NOTE_TRIGGER")
    if kind == "none" or not target:
        return
    trigger_env = trigger_environment(note)
    if kind == "cli":
        subprocess.run(
            target,
            cwd=ROOT,
            env={**os.environ, **trigger_env},
            shell=True,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return
    body = json.dumps(
        {
            "prompt": trigger_env["NOTE_PROMPT"],
            "message": trigger_env["NOTE_MESSAGE"],
            "date": trigger_env["NOTE_DATE"],
            "time": trigger_env["NOTE_TIME"],
            "path": trigger_env["NOTE_PATH"],
            "channel": trigger_env["NOTE_CHANNEL"],
            "account_id": trigger_env["NOTE_ACCOUNT_ID"],
            "sender_id": trigger_env["NOTE_SENDER_ID"],
            "message_id": trigger_env["NOTE_MESSAGE_ID"],
        }
    ).encode()
    token = os.path.expandvars("$SHADOWED_N8N_TOKEN")
    headers = {"Content-Type": "application/json"}
    if token != "$SHADOWED_N8N_TOKEN":
        headers["Authorization"] = f"Bearer {token}"
    with request.urlopen(
        request.Request(os.path.expandvars(target), data=body, headers=headers, method="POST"),
        timeout=300,
    ) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status}")


def save(payload: dict) -> dict:
    message = str(payload.get("message") or "").strip()
    if not message and not any((payload.get("media"), payload.get("contacts"), payload.get("location"))):
        raise ValueError("note is empty")
    payload = {**payload, "message": message, "note_path": str(note_directory(payload))}
    kind = backend()
    now = timestamp(payload)
    assets = persist_assets(payload, now, kind)
    if kind == "file":
        stored = store_file(payload, now) if message else {"path": str(Path(payload["note_path"]))}
        stored["assets"] = assets
    else:
        stored = store_sql(payload, now, kind, assets)
    note = {
        **payload,
        **stored,
        "backend": kind,
        "date": f"{now:%Y-%m-%d}",
        "time": f"{now:%H:%M:%S}",
    }
    text_only = bool(message) and not any((payload.get("media"), payload.get("contacts"), payload.get("location")))
    triggered = text_only and trigger_configured()
    reply = "✅ Note saved.\nTrigger fired." if triggered else "✅ Note saved."
    if not text_only:
        reply = ""
    return {"ok": True, "reply": feedback(reply), "trigger": triggered, "note": note}


def show(payload: dict, hours: float | None = None) -> dict:
    payload = {**payload, "note_path": str(note_directory(payload))}
    kind = backend()
    cutoff = datetime.now().astimezone() - timedelta(hours=hours) if hours is not None else None
    output = show_file(payload, cutoff) if kind == "file" else show_sql(kind, cutoff)
    return {"ok": True, "reply": output, "trigger": False}


def command(payload: dict) -> dict:
    message = str(payload.get("message") or "").strip()
    if not message:
        return {"ok": True, "reply": "Usage: /note <message>", "trigger": False}
    match = re.fullmatch(r"show(?:\s+(\d+(?:[.,]\d+)?)h)?", message, re.IGNORECASE)
    if match:
        hours = float(match.group(1).replace(",", ".")) if match.group(1) else None
        if hours is not None and hours <= 0:
            return {"ok": True, "reply": "Usage: /note show [hours]h", "trigger": False}
        return show(payload, hours)
    if re.match(r"^show\b", message, re.IGNORECASE):
        return {"ok": True, "reply": "Usage: /note show or /note show <hours>h", "trigger": False}
    return save(payload)


def main() -> None:
    payload = json.load(sys.stdin)
    action = str(payload.get("action") or "save")
    try:
        if action == "command":
            result = command(payload)
        elif action == "show":
            result = show(payload, payload.get("hours"))
        elif action == "trigger":
            execute_trigger(dict(payload["note"]))
            result = {"ok": True, "status": feedback("✅ Trigger completed.")}
        elif action == "save":
            result = save(payload)
        else:
            raise ValueError(f"unsupported NOTE action: {action}")
    except Exception as exc:
        label = "Trigger" if action == "trigger" else "Note"
        result = {
            "ok": False,
            "reply": feedback(f"❌ {label} processing failed."),
            "status": feedback("❌ Trigger failed.") if action == "trigger" else "",
            "error": str(exc),
            "trigger": False,
        }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
