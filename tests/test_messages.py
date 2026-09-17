"""Unit tests for the notification message builders. Plain python, no HA."""

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "filc"
sys.path.insert(0, str(COMPONENT_DIR))

import messages  # noqa: E402
from models import Lesson, Occurrence  # noqa: E402

TZ = ZoneInfo("Europe/Budapest")


def _occ(room="A118", teacher="Mészáros Tamás", start=(10, 50), end=(11, 35)):
    lesson = Lesson(
        id="l1",
        weekday=1,
        period_no=4,
        start=f"{start[0]:02d}:{start[1]:02d}",
        end=f"{end[0]:02d}:{end[1]:02d}",
        subject="Digitális kultúra",
        subject_short="DiKu",
    )
    return Occurrence(
        lesson=lesson,
        date=dt.date(2026, 9, 21),
        start=dt.datetime(2026, 9, 21, *start, tzinfo=TZ),
        end=dt.datetime(2026, 9, 21, *end, tzinfo=TZ),
        room=room,
        teacher=teacher,
    )


def test_reminder_hu():
    title, message = messages.reminder(_occ(), 5, hu=True)
    assert title == "Következő óra 5 perc múlva"
    assert message == "Digitális kultúra · 📍 A118 · Mészáros Tamás · kezdés 10:50"


def test_reminder_en():
    title, message = messages.reminder(_occ(), 3, hu=False)
    assert title == "Next lesson in 3 minutes"
    assert message == "Digitális kultúra · 📍 A118 · Mészáros Tamás · starts 10:50"


def test_reminder_without_room_or_teacher():
    _title, message = messages.reminder(_occ(room=None, teacher=None), 5, hu=True)
    assert message == "Digitális kultúra · kezdés 10:50"


def test_break_hu():
    title, message = messages.break_message(_occ(), hu=True)
    assert title == "Szünet"
    assert message == "Következő: Digitális kultúra · 📍 A118 · 10:50"


def test_break_en():
    title, message = messages.break_message(_occ(), hu=False)
    assert title == "Break"
    assert message == "Next: Digitális kultúra · 📍 A118 · 10:50"


def test_subject_short_fallback():
    lesson = Lesson(
        id="x", weekday=1, period_no=1, start="08:00", end="08:45",
        subject="", subject_short="Ofő",
    )
    occ = Occurrence(
        lesson=lesson,
        date=dt.date(2026, 9, 21),
        start=dt.datetime(2026, 9, 21, 8, 0, tzinfo=TZ),
        end=dt.datetime(2026, 9, 21, 8, 45, tzinfo=TZ),
    )
    _title, message = messages.reminder(occ, 5, hu=True)
    assert "Ofő" in message


def test_live_state_in_lesson_hu():
    occ = _occ()
    notifier = messages.live_state(occ, occ, dt.date(2026, 9, 21), hu=True)
    title, message = notifier
    assert title == "Filc – élő állapot"
    assert message.startswith("ÓRA: Digitális kultúra · 📍 A118")
    assert "vége 11:35" in message


def test_live_state_break_hu():
    title, message = messages.live_state(None, _occ(), dt.date(2026, 9, 21), hu=True)
    assert title == "Filc – élő állapot"
    assert message.startswith("SZÜNET · következő: Digitális kultúra")
    assert "10:50" in message


def test_live_state_no_more_today_hu():
    title, message = messages.live_state(None, _occ(), dt.date(2026, 9, 22), hu=True)
    assert message.startswith("NINCS TÖBB ÓRA")
    assert "2026-09-21" in message


def test_live_state_none_hu():
    title, message = messages.live_state(None, None, dt.date(2026, 9, 21), hu=True)
    assert message == "NINCS ÓRA"


def test_live_state_en():
    occ = _occ()
    title, message = messages.live_state(occ, occ, dt.date(2026, 9, 21), hu=False)
    assert title == "Filc – live status"
    assert message.startswith("IN LESSON: Digitális kultúra")
