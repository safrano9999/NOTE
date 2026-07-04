# NOTE

NOTE captures notes deterministically without an LLM call.

## Python runtime

NOTE requires Python and the packages listed in `requirements.txt`. Its bootstrap first uses an
available `python3` and tries `pip` when dependencies are missing; if no usable Python environment
is available, it installs `uv` locally, creates `.venv`, and installs Python and the requirements
without requiring root access.

## Normal AI operation

- `/note <text>` stores a note independently of the active AI model.
- `/note show` displays all notes.
- `/note show 48h` displays notes from the last 48 hours.
- Notes can use Markdown files, SQLite, MariaDB, or PostgreSQL.

## Patched non-AI operation

With the deterministic OpenClaw patch and the `dummy/note` model selected, every normal
non-command message is stored directly as a note. Slash commands are never stored. The NOTE
plugin handles storage and feedback before any model call, while `dummy/dummy` remains the
general deterministic gateway model without note capture.

Optional CLI or webhook triggers can process a note after it has been stored.
