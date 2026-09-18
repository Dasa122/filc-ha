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


def live_activity(current, upcoming, now, hu: bool = True) -> dict:
    """Payload fields for a Live Activity / Live Update (no HA imports).

    The companion app replaces `message` with the chronometer timer on iOS and
    hides `critical_text` when `progress` is set, so the lesson name and room are
    sent in `critical_text` (visible next to the timer) and no progress bar is used.
    `now` must be a timezone-aware datetime in the school timezone.
    """
    if current is not None:
        subject = _subject(current)
        short = current.lesson.subject_short or subject
        room = f" · 📍 {current.room}" if current.room else ""
        short_room = f" · {current.room}" if current.room else ""
        remaining = max(int((current.end - now).total_seconds()), 1)
        if hu:
            message = f"{subject}{room} · vége {current.end:%H:%M}"
        else:
            message = f"{subject}{room} · ends {current.end:%H:%M}"
        return {
            "title": "Filc",
            "message": message,
            "critical_text": f"{short}{short_room}",
            "chronometer": True,
            "when": remaining,
            "when_relative": True,
        }

    if upcoming is not None and upcoming.date == now.date():
        subject = _subject(upcoming)
        short = upcoming.lesson.subject_short or subject
        room = f" · 📍 {upcoming.room}" if upcoming.room else ""
        short_room = f" · {upcoming.room}" if upcoming.room else ""
        until = max(int((upcoming.start - now).total_seconds()), 1)
        if hu:
            message = f"Szünet vége {upcoming.start:%H:%M} · {subject}{room}"
            critical = f"Szünet · {short}{short_room}"
        else:
            message = f"Break ends {upcoming.start:%H:%M} · {subject}{room}"
            critical = f"Break · {short}{short_room}"
        return {
            "title": "Filc",
            "message": message,
            "critical_text": critical,
            "chronometer": True,
            "when": until,
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
