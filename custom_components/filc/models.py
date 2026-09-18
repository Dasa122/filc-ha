"""Data models for the Filc integration. No Home Assistant or aiohttp imports."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class Lesson:
    """A single weekly lesson definition."""

    id: str
    weekday: int  # ISO weekday, 1=Mon .. 5=Fri
    period_no: int
    start: str  # "HH:MM"
    end: str  # "HH:MM"
    subject: str
    subject_short: str
    teachers: list[str] = field(default_factory=list)
    teacher_shorts: list[str] = field(default_factory=list)
    rooms: list[str] = field(default_factory=list)
    group_ids: set[str] = field(default_factory=set)
    entire_class: bool = False

    @classmethod
    def from_raw(cls, raw: dict, weekday_map: dict | None = None) -> "Lesson":
        """Build a Lesson from an EnrichedLesson API payload."""
        weekday_map = weekday_map or {}
        day = raw.get("day") or {}
        period = raw.get("period") or {}
        subject = raw.get("subject") or {}

        teachers = []
        teacher_shorts = []
        for t in raw.get("teachers") or []:
            name = t.get("name")
            if not name:
                continue
            teachers.append(name)
            teacher_shorts.append(t.get("short") or name)
        rooms = []
        for c in raw.get("classrooms") or []:
            rooms.append(c.get("short") or c.get("name") or "")

        group_ids = set(raw.get("groupsIds") or [])
        if not group_ids:
            group_ids = {g.get("id") for g in raw.get("groups") or [] if g.get("id")}
        entire_class = any(g.get("entireClass") for g in raw.get("groups") or [])

        days = day.get("days") or []
        if days:
            weekday = int(days[0])
        else:
            weekday = weekday_map.get(day.get("name", ""), 0)

        subject_name = subject.get("name") if subject else ""
        subject_short = subject.get("short") if subject else ""
        if not subject_short:
            subject_short = subject_name

        return cls(
            id=raw.get("id", ""),
            weekday=weekday,
            period_no=int(period.get("period", 0)),
            start=(period.get("startTime") or "00:00")[:5],
            end=(period.get("endTime") or "00:00")[:5],
            subject=subject_name,
            subject_short=subject_short,
            teachers=teachers,
            teacher_shorts=teacher_shorts,
            rooms=rooms,
            group_ids=group_ids,
            entire_class=entire_class,
        )


@dataclass
class Occurrence:
    """A concrete instance of a lesson on a specific date."""

    lesson: Lesson
    date: dt.date
    start: dt.datetime
    end: dt.datetime
    room: str | None = None
    teacher: str | None = None
    teacher_short: str | None = None
    moved: bool = False
    cancelled: bool = False
    substituted: bool = False


@dataclass
class ScheduleData:
    """The result of one coordinator update."""

    lessons: list[Lesson]
    periods: list[dict]
    substitutions: list[dict]
    moved_lessons: list[dict]
    selected_group_ids: set[str]
    timetable: dict
