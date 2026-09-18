"""Notification text builders. No Home Assistant imports, so they are testable."""

from __future__ import annotations

try:
    from .models import Occurrence
except ImportError:  # pragma: no cover - loaded standalone (tests) as a top-level module
    from models import Occurrence


def _subject(occ: Occurrence) -> str:
    return occ.lesson.subject or occ.lesson.subject_short or "Óra"


def _join(*parts) -> str:
    return " · ".join(p for p in parts if p)


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


def live_state(current, upcoming, today, hu: bool = True) -> tuple[str, str]:
    """A one-line summary of the live action: in lesson, break, or done for the day."""
    if current is not None:
        subject = _subject(current)
        room = f" · 📍 {current.room}" if current.room else ""
        if hu:
            return ("Filc – élő állapot", f"ÓRA: {subject}{room} · vége {current.end:%H:%M}")
        return ("Filc – live status", f"IN LESSON: {subject}{room} · ends {current.end:%H:%M}")

    if upcoming is not None and upcoming.date == today:
        subject = _subject(upcoming)
        room = f" · 📍 {upcoming.room}" if upcoming.room else ""
        if hu:
            return ("Filc – élő állapot", f"SZÜNET · következő: {subject}{room} · {upcoming.start:%H:%M}")
        return ("Filc – live status", f"BREAK · next: {subject}{room} · {upcoming.start:%H:%M}")

    if upcoming is not None:
        subject = _subject(upcoming)
        if hu:
            return ("Filc – élő állapot", f"NINCS TÖBB ÓRA · következő: {subject} · {upcoming.date} {upcoming.start:%H:%M}")
        return ("Filc – live status", f"NO MORE TODAY · next: {subject} · {upcoming.date} {upcoming.start:%H:%M}")

    if hu:
        return ("Filc – élő állapot", "NINCS ÓRA")
    return ("Filc – live status", "NO LESSONS")


def school_state(current, upcoming, today, hu: bool = True) -> str:
    """One-word state for the school_state sensor."""
    if current is not None:
        return "Óra" if hu else "In lesson"
    if upcoming is not None and upcoming.date == today:
        return "Szünet" if hu else "Break"
    if upcoming is not None:
        return "Nincs több óra ma" if hu else "No more today"
    return "Nincs óra" if hu else "No lessons"


def live_activity(current, upcoming, now, hu: bool = True) -> dict:
    """Payload fields for a Live Activity / Live Update (no HA imports).

    The companion app replaces `message` with the chronometer timer on iOS and
    hides `critical_text` when `progress` is set, so the lesson name and room are
    sent in `critical_text` (visible next to the timer) and no progress bar is used.
    `now` must be a timezone-aware datetime in the school timezone.
    """
    if current is not None:
        subject = _subject(current)
        critical_text = _join(
            current.room,
            current.lesson.subject_short or subject,
            current.teacher_short,
        )
        when = max(int((current.end - now).total_seconds()), 1)
        return {
            "title": "Filc",
            "message": subject,
            "critical_text": critical_text,
            "chronometer": True,
            "when": when,
            "when_relative": True,
        }

    if upcoming is not None and upcoming.date == now.date():
        subject = _subject(upcoming)
        if hu:
            message = f"Szünet\n{subject}"
        else:
            message = f"Break\n{subject}"
        critical_text = _join(
            upcoming.room, upcoming.teacher_short
        )
        when = max(int((upcoming.start - now).total_seconds()), 1)
        return {
            "title": "Filc",
            "message": message,
            "critical_text": critical_text,
            "chronometer": True,
            "when": when,
            "when_relative": True,
        }

    if upcoming is not None:
        subject = _subject(upcoming)
        room = f" · 📍 {upcoming.room}" if upcoming.room else ""
        if hu:
            message = (
                f"Nincs több óra ma · {subject}{room} · "
                f"{upcoming.date} {upcoming.start:%H:%M}"
            )
        else:
            message = (
                f"No more today · {subject}{room} · "
                f"{upcoming.date} {upcoming.start:%H:%M}"
            )
        return {"title": "Filc", "message": message}

    return {"title": "Filc", "message": "Nincs óra" if hu else "No lessons"}
