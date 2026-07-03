from __future__ import annotations

import fcntl
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from python_header import get


VALID_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def backend() -> str:
    value = get("NOTE_DB_BACKEND", "file").lower()
    aliases = {"postgresql": "postgres", "pgsql": "postgres", "mysql": "mariadb", "sqlite3": "sqlite"}
    value = aliases.get(value, value)
    if value not in {"file", "sqlite", "mariadb", "postgres"}:
        raise ValueError(f"unsupported NOTE_DB_BACKEND: {value}")
    return value


def table_name() -> str:
    prefix = get("NOTE_DB_PREFIX", "note")
    if prefix and not VALID_IDENTIFIER.fullmatch(prefix):
        raise ValueError("NOTE_DB_PREFIX must be empty or a valid SQL identifier")
    return f"{prefix}_notes" if prefix else "notes"


def database_url(kind: str) -> str:
    if kind == "sqlite":
        sqlite_dir = ROOT / "sqlite"
        sqlite_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{sqlite_dir / 'note.sqlite3'}"
    driver = "postgresql+psycopg" if kind == "postgres" else "mysql+pymysql"
    host = get("NOTE_DB_URL", "127.0.0.1")
    port = get("NOTE_DB_PORT", "5432" if kind == "postgres" else "3306")
    user = quote_plus(get("NOTE_DB_USER"))
    password = quote_plus(get("NOTE_DB_PW"))
    name = quote_plus(get("NOTE_DB_NAME", "note"))
    return f"{driver}://{user}:{password}@{host}:{port}/{name}"


def timestamp(payload: dict) -> datetime:
    raw = payload.get("timestamp")
    zone = ZoneInfo(get("NOTE_TIMEZONE", "Europe/Vienna"))
    return datetime.fromtimestamp(float(raw) / 1000, zone) if raw else datetime.now(zone)


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

    engine = create_engine(database_url(kind), future=True, pool_pre_ping=kind != "sqlite")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True), Note


def store_sql(payload: dict, now: datetime, kind: str) -> dict:
    factory, Note = sql_context(kind)
    with factory.begin() as session:
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
    return {"id": note_id, "table": table_name()}


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
    zone = ZoneInfo(get("NOTE_TIMEZONE", "Europe/Vienna"))
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
                created = datetime.combine(date, datetime.strptime(block_lines[-1].strip(), "%H:%M:%S").time(), zone)
            except ValueError:
                continue
            if cutoff is None or created >= cutoff:
                rows.append((created, "\n".join(block_lines[:-1]).rstrip()))
    return format_notes(rows)


def show_sql(kind: str, cutoff: datetime | None) -> str:
    factory, Note = sql_context(kind)
    zone = ZoneInfo(get("NOTE_TIMEZONE", "Europe/Vienna"))
    with factory() as session:
        records = session.query(Note).order_by(Note.note_date.asc(), Note.note_time.asc(), Note.id.asc()).all()
    rows = []
    for row in records:
        created = datetime.combine(row.note_date, row.note_time, zone)
        if cutoff is None or created >= cutoff:
            rows.append((created, row.message))
    return format_notes(rows)


def main() -> None:
    payload = json.load(sys.stdin)
    kind = backend()
    if payload.get("action") == "show":
        hours = payload.get("hours")
        zone = ZoneInfo(get("NOTE_TIMEZONE", "Europe/Vienna"))
        cutoff = datetime.now(zone) - timedelta(hours=float(hours)) if hours is not None else None
        output = show_file(payload, cutoff) if kind == "file" else show_sql(kind, cutoff)
        print(json.dumps({"backend": kind, "text": output}))
        return
    if not str(payload.get("message") or "").strip():
        raise ValueError("note message is empty")
    now = timestamp(payload)
    result = store_file(payload, now) if kind == "file" else store_sql(payload, now, kind)
    print(json.dumps({**result, "backend": kind, "date": f"{now:%Y-%m-%d}", "time": f"{now:%H:%M:%S}"}))


if __name__ == "__main__":
    main()
