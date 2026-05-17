"""Modes discovered from prompt files: registry, resolution, composition."""
import pytest
from pydantic import ValidationError

from app.core import modes
from app.core.modes import (
    compose_prompt,
    instruction_for,
    is_known_mode,
    list_modes,
)
from app.schemas.envelope import ProcessRequest


@pytest.fixture
def modes_dir(tmp_path, monkeypatch):
    """Isolate mode discovery to a temp dir."""
    monkeypatch.setattr(modes, "_MODES_DIR", tmp_path)
    return tmp_path


# --- discovery is purely file-driven ---------------------------------------

def test_dropping_a_file_creates_a_mode(modes_dir):
    (modes_dir / "cartoon.md").write_text("Make it look hand-drawn.", "utf-8")
    assert {"key": "cartoon", "label": "Cartoon"} in list_modes()
    assert is_known_mode("cartoon")
    assert instruction_for("cartoon") == "Make it look hand-drawn."


def test_label_from_heading_else_humanized_key(modes_dir):
    (modes_dir / "dark-mode.md").write_text("# Night Owl\nGo dark.", "utf-8")
    (modes_dir / "mode3.md").write_text("", "utf-8")
    by_key = {m["key"]: m["label"] for m in list_modes()}
    assert by_key["dark-mode"] == "Night Owl"          # heading wins
    assert by_key["mode3"] == "Mode 3"                  # humanized fallback
    # heading line is not part of the instruction body
    assert instruction_for("dark-mode") == "Go dark."


def test_removing_file_removes_mode(modes_dir):
    f = modes_dir / "focus.md"
    f.write_text("Focus.", "utf-8")
    assert is_known_mode("focus")
    f.unlink()
    assert not is_known_mode("focus")
    assert instruction_for("focus") == ""


def test_unknown_and_traversal_keys_rejected(modes_dir):
    assert not is_known_mode("nope")
    # path traversal / bad chars never resolve to a file
    assert not is_known_mode("../../etc/passwd")
    assert not is_known_mode("a/b")
    assert instruction_for("../secrets") == ""


def test_list_modes_is_key_label_only(modes_dir):
    (modes_dir / "focus.md").write_text("x", "utf-8")
    assert all(set(m) == {"key", "label"} for m in list_modes())


# --- composition ------------------------------------------------------------

def test_user_only(modes_dir):
    assert compose_prompt(None, "make it blue") == "make it blue"


def test_blank_mode_file_degrades_to_user_prompt(modes_dir):
    (modes_dir / "focus.md").write_text("", "utf-8")
    assert compose_prompt("focus", "round images") == "round images"


def test_mode_plus_user_layers(modes_dir):
    (modes_dir / "focus.md").write_text("Strip distractions.", "utf-8")
    out = compose_prompt("focus", "keep the nav")
    assert out.startswith("Strip distractions.")
    assert "USER CUSTOMIZATION" in out
    assert out.rstrip().endswith("keep the nav")
    assert compose_prompt("focus", "") == "Strip distractions."  # mode only


def test_neither_is_empty(modes_dir):
    assert compose_prompt(None, "") == ""


# --- ProcessRequest validation parity --------------------------------------

def _req(**kw):
    return ProcessRequest(**{"page_url": "u", "html": "<html></html>", **kw})


def test_no_instruction_field_on_request():
    assert "mode_instruction_prompt" not in ProcessRequest.model_fields


def test_no_mode_requires_user_prompt():
    with pytest.raises(ValidationError):
        _req(user_prompt="  ")


def test_unknown_mode_rejected():
    with pytest.raises(ValidationError):
        _req(selected_mode="definitely-not-a-mode", user_prompt="x")


def test_known_mode_allows_empty_user_prompt():
    # Use whatever mode files actually ship; design is file-driven.
    real = list_modes()
    if not real:
        pytest.skip("no mode prompt files present")
    key = real[0]["key"]
    assert _req(selected_mode=key, user_prompt="").selected_mode == key


# --- endpoint reflects whatever prompt files exist -------------------------

def test_modes_endpoint_matches_prompt_dir(client):
    from app.core.modes import _MODES_DIR

    r = client.get("/api/v1/modes")
    assert r.status_code == 200
    body = r.json()["modes"]
    expected_keys = {p.stem for p in _MODES_DIR.glob("*.md")}
    assert {m["key"] for m in body} == expected_keys
    assert all(set(m) == {"key", "label"} for m in body)
