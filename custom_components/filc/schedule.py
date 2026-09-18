"""Pure schedule logic for the Filc integration. No Home Assistant or aiohttp imports."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

try:
    from .const import SCHOOL_TZ, WEEKDAY_MAP
    from .models import Lesson, Occurrence
except ImportError:  # pragma: no cover - loaded standalone (tests) as top-level modules
    from const import SCHOOL_TZ, WEEKDAY_MAP
    from models import Lesson, Occurrence


def local_date(iso_utc: str, tz: str = SCHOOL_TZ) -> dt.date:
    """Convert a UTC ISO datetime string to a local date in the school timezone.

    Midnight UTC (00:00Z) is 02:00 Budapest, i.e. the same calendar day.
    """
    value = iso_utc.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(ZoneInfo(tz)).date()


def lesson_matches_groups(lesson: Lesson, selected_group_ids) -> bool:
    """Return True if a lesson is visible for the user's selected groups.

    Rule: include if `group_ids` is empty, OR the lesson is entire-class,
    OR the lesson's groups intersect the user's selected group ids.
    """
    if not lesson.group_ids:
        return True
    if lesson.entire_class:
        return True
    return bool(lesson.group_ids & set(selected_group_ids or []))


def _parse_time(value: str) -> dt.time:
    parts = value.split(":")
    return dt.time(int(parts[0]), int(parts[1]))


def _make_occurrence(
    lesson: Lesson,
    date: dt.date,
    start: str | None = None,
    end: str | None = None,
    room: str | None = None,
    teacher: str | None = None,
    moved: bool = False,
) -> Occurrence:
    tz = ZoneInfo(SCHOOL_TZ)
    start_dt = dt.datetime.combine(date, _parse_time(start or lesson.start), tzinfo=tz)
    end_dt = dt.datetime.combine(date, _parse_time(end or lesson.end), tzinfo=tz)
    if room is None:
        room = lesson.rooms[0] if lesson.rooms else None
    if teacher is None:
        teacher = lesson.teachers[0] if lesson.teachers else None
    teacher_short = lesson.teacher_shorts[0] if lesson.teacher_shorts else None
    return Occurrence(
        lesson=lesson,
        date=date,
        start=start_dt,
        end=end_dt,
        room=room,
        teacher=teacher,
        teacher_short=teacher_short,
        moved=moved,
    )


def _iter_moved(moved_lessons):
    """Yield flattened moved-lesson dicts from the raw API shape."""
    for ml in moved_lessons or []:
        moved = ml.get("movedLesson") or {}
        yield {
            "date": moved.get("date"),
            "dayDefinition": ml.get("dayDefinition"),
            "period": ml.get("period"),
            "classroom": ml.get("classroom"),
            "lessons": ml.get("lessons") or [],
        }


def occurrences_for_date(
    date: dt.date,
    lessons: list[Lesson],
    selected_group_ids,
    moved_lessons,
    substitutions,
) -> list[Occurrence]:
    """Build the ordered list of occurrences for a single date."""
    all_lessons = {lesson.id: lesson for lesson in lessons}

    # 1. Base occurrences from the weekly schedule.
    base: dict[str, Occurrence] = {}
    for lesson in lessons:
        if lesson.weekday != date.isoweekday():
            continue
        if not lesson_matches_groups(lesson, selected_group_ids):
            continue
        base[lesson.id] = _make_occurrence(lesson, date)

    # 2. Moved lessons.
    for ml in _iter_moved(moved_lessons):
        if not ml["date"]:
            continue
        if local_date(ml["date"]) == date:
            # Moved TO this date: replace/insert at the target day/period/room.
            period = ml["period"] or {}
            classroom = ml["classroom"] or {}
            target_room = classroom.get("short") or classroom.get("name") or None
            for raw_lesson in ml["lessons"]:
                lid = raw_lesson.get("id")
                lesson = all_lessons.get(lid) or Lesson.from_raw(raw_lesson, WEEKDAY_MAP)
                base[lid] = _make_occurrence(
                    lesson,
                    date,
                    start=period.get("startTime") or lesson.start,
                    end=period.get("endTime") or lesson.end,
                    room=target_room,
                    moved=True,
                )
        else:
            # Moved AWAY to a different date: drop the original slot on this date.
            for raw_lesson in ml["lessons"]:
                lid = raw_lesson.get("id")
                lesson = all_lessons.get(lid) or Lesson.from_raw(raw_lesson, WEEKDAY_MAP)
                if lesson.weekday == date.isoweekday():
                    base.pop(lid, None)

    # 3. Substitutions.
    for sub in substitutions or []:
        meta = sub.get("substitution") or {}
        if not meta.get("date"):
            continue
        if local_date(meta["date"]) != date:
            continue
        teacher = sub.get("teacher") or {}
        substituter = meta.get("substituter")
        for lid in sub.get("lessons") or []:
            occ = base.get(lid)
            if occ is None:
                continue
            if substituter is None:
                occ.cancelled = True
            else:
                occ.substituted = True
                if teacher:
                    name = " ".join(
                        filter(None, [teacher.get("firstName"), teacher.get("lastName")])
                    ).strip()
                    occ.teacher = name or teacher.get("short") or substituter
                    occ.teacher_short = teacher.get("short") or None
                else:
                    occ.teacher = substituter
                    occ.teacher_short = None

    # 4. Sort by start time.
    return sorted(base.values(), key=lambda o: o.start)


def current_occurrence(now, lessons, selected_group_ids, moved_lessons, substitutions):
    """Return the non-cancelled occurrence currently in progress (last match), else None."""
    result = None
    for occ in occurrences_for_date(
        now.date(), lessons, selected_group_ids, moved_lessons, substitutions
    ):
        if occ.cancelled:
            continue
        if occ.start <= now < occ.end:
            result = occ
    return result


def next_occurrence(
    now, lessons, selected_group_ids, moved_lessons, substitutions, max_days: int = 14
):
    """Return the first non-cancelled occurrence after `now`, scanning day by day."""
    for offset in range(max_days + 1):
        day = now.date() + dt.timedelta(days=offset)
        for occ in occurrences_for_date(
            day, lessons, selected_group_ids, moved_lessons, substitutions
        ):
            if occ.cancelled:
                continue
            if occ.start > now:
                return occ
    return None


def first_occurrence_after_day(
    now, lessons, selected_group_ids, moved_lessons, substitutions, max_days: int = 14
):
    """First non-cancelled occurrence on the first date AFTER now.date() that has any."""
    for offset in range(1, max_days + 1):
        day = now.date() + dt.timedelta(days=offset)
        for occ in occurrences_for_date(
            day, lessons, selected_group_ids, moved_lessons, substitutions
        ):
            if not occ.cancelled:
                return occ
    return None


def expand_range(
    start_date: dt.date,
    end_date: dt.date,
    lessons,
    selected_group_ids,
    moved_lessons,
    substitutions,
) -> list[Occurrence]:
    """Return every occurrence (including cancelled) in the inclusive date range."""
    result: list[Occurrence] = []
    day = start_date
    while day <= end_date:
        result.extend(
            occurrences_for_date(day, lessons, selected_group_ids, moved_lessons, substitutions)
        )
        day += dt.timedelta(days=1)
    return result


def now() -> dt.datetime:
    """Current time in the school timezone."""
    return dt.datetime.now(ZoneInfo(SCHOOL_TZ))


def today() -> dt.date:
    """Current date in the school timezone."""
    return now().date()
