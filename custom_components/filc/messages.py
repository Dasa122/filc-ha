"""Notification text builders. No Home Assistant imports, so they are testable."""

from __future__ import annotations

try:
    from .models import Occurrence
except ImportError:  # pragma: no cover - loaded standalone (tests) as a top-level module
    from models import Occurrence


def _subject(occ: Occurrence) -> str:
    return occ.lesson.subject or occ.lesson.subject_short or "Óra"


def reminder(occ: Occurrence, lead_minutes: int, hu: bool = True) -> tuple[str, str]:
    """The 'next lesson soon' notification for one occurrence."""
    subject = _subject(occ)
    room = f" · 📍 {occ.room}" if occ.room else ""
    teacher = f" · {occ.teacher}" if occ.teacher else ""
    if hu:
        return (
            f"Következő óra {lead_minutes} perc múlva",
            f"{subject}{room}{teacher} · kezdés {occ.start:%H:%M}",
        )
    return (
        f"Next lesson in {lead_minutes} minutes",
        f"{subject}{room}{teacher} · starts {occ.start:%H:%M}",
    )


def break_message(next_occ: Occurrence, hu: bool = True) -> tuple[str, str]:
    """The break summary pointing at the next lesson."""
    subject = _subject(next_occ)
    room = f" · 📍 {next_occ.room}" if next_occ.room else ""
    if hu:
        return ("Szünet", f"Következő: {subject}{room} · {next_occ.start:%H:%M}")
    return ("Break", f"Next: {subject}{room} · {next_occ.start:%H:%M}")
