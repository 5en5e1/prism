"""Backend-owned modes, discovered from prompt files.

A "mode" is just a markdown file in ``app/prompts/modes/<key>.md``:

* file present                -> the mode exists
* file contents               -> the instruction prompt
* optional first ``# Heading``-> the button label (else derived from key)

So adding/renaming/removing a mode or editing its prompt is purely a file
operation -- no code change, no restart (files are read on demand). The
extension fetches ``{key,label}`` and sends back a key; the backend resolves
the instruction and composes the final prompt.

Pure/IO-light and decoupled from page-transformation logic.
"""
import re
from pathlib import Path

_MODES_DIR = Path(__file__).resolve().parent.parent / "prompts" / "modes"

# Mode keys come from the client (selected_mode) and are turned into a file
# path, so they must be strictly validated to prevent path traversal.
_VALID_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

_CUSTOMIZATION_HEADER = (
    "--- USER CUSTOMIZATION (apply on top of the above; refine it, "
    "do not discard the base intent) ---"
)


def _humanize(key: str) -> str:
    """Fallback label from a key: 'dark-mode' -> 'Dark Mode', 'mode3' ->
    'Mode 3'."""
    spaced = re.sub(r"[-_]+", " ", key)
    spaced = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", spaced)
    return spaced.strip().title()


def _split_label_and_body(raw: str, key: str) -> tuple[str, str]:
    """An optional leading ``# Label`` line names the mode; the rest is the
    instruction body. No heading -> label derived from the key."""
    text = raw.lstrip("ï»¿").strip()
    if not text:
        return _humanize(key), ""
    first, _, rest = text.partition("\n")
    if first.startswith("# "):
        return first[2:].strip() or _humanize(key), rest.strip()
    return _humanize(key), text


def _mode_path(key: str) -> Path | None:
    if not key or not _VALID_KEY.match(key):
        return None
    return _MODES_DIR / f"{key}.md"


def is_known_mode(mode: str | None) -> bool:
    """True if ``mode`` is None (no mode) or a valid key with a prompt file."""
    if mode is None:
        return True
    path = _mode_path(mode)
    return path is not None and path.is_file()


def list_modes() -> list[dict[str, str]]:
    """Modes for the extension to render (key + label only), sorted by key.
    Discovered from the prompt files on every call so changes are live."""
    modes: list[dict[str, str]] = []
    try:
        files = sorted(_MODES_DIR.glob("*.md"))
    except OSError:
        return modes
    for path in files:
        key = path.stem
        if not _VALID_KEY.match(key):
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        label, _ = _split_label_and_body(raw, key)
        modes.append({"key": key, "label": label})
    return modes


def instruction_for(mode: str | None) -> str:
    """The instruction prompt for a mode ("" if none/unknown/blank)."""
    path = _mode_path(mode) if mode else None
    if path is None or not path.is_file():
        return ""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    _, body = _split_label_and_body(raw, mode or "")
    return body


def compose_prompt(mode: str | None, user_prompt: str | None) -> str:
    """Merge the mode's instruction (base) with the user prompt (modifier).

    * user only            -> the user prompt
    * mode only            -> the mode instruction
    * mode + user          -> instruction, then a clearly delimited user layer
    * neither (both blank) -> "" (caller rejects as malformed)

    A blank instruction (placeholder mode file) is treated as absent, so a
    moded request never yields a malformed "empty-base + modifier" prompt.
    """
    base = instruction_for(mode).strip()
    user = (user_prompt or "").strip()
    if base and user:
        return f"{base}\n\n{_CUSTOMIZATION_HEADER}\n{user}"
    return base or user
