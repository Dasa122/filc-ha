"""Unit tests for the pure schedule logic. Run with plain pytest, no HA/aiohttp."""

import datetime as dt
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

# Load the pure modules by file path as top-level modules, avoiding
# custom_components/filc/__init__.py which imports Home Assistant.
COMPONENT_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "filc"
sys.path.insert(0, str(COMPONENT_DIR))

import schedule  # noqa: E402
from models import Lesson  # noqa: E402

TZ = ZoneInfo("Europe/Budapest")
MONDAY = dt.date(2026, 9, 21)
OTHER_MONDAY = dt.date(2026, 9, 28)

OSZTALYFONOKI_ID = "lesson-ofo"
DIGITALIS_ID = "lesson-digitalis"
GROUP_INFO1 = "group-info1"


def _day(name="Hétfő", short="Hé", days=("1",)):
    return {"id": "day-mon", "name": name, "short": short, "days": list(days)}


def _period(no, start="08:00:00", end="08:45:00"):
    return {"id": f"period-{no}", "period": no, "startTime": start, "endTime": end}


def _subject(name, short):
    return {"id": f"subject-{short}", "name": name, "short": short}


def _teacher(name, short=None):
    return {"id": f"teacher-{name}", "name": name, "short": short or name}


def _classroom(name, short=None):
    return {"id": f"room-{name}", "name": name, "short": short or name}


def _lesson(id_, period, subject, teachers=(), classrooms=(), groups=(), groups_ids=()):
    return {
        "id": id_,
        "day": _day(),
        "period": period,
        "subject": subject,
        "teachers": list(teachers),
        "classrooms": list(classrooms),
        "cohorts": [{"id": "cohort-9a", "name": "9.A", "short": "9.A"}],
        "groups": list(groups),
        "groupsIds": list(groups_ids),
        "weekDefinition": None,
        "weeksDefinitionId": None,
        "periodsPerWeek": 1,
        "termDefinitionId": None,
    }


def _fixtures():
    period_1 = _period(1, "08:00:00", "08:45:00")
    period_4 = _period(4, "10:50:00", "11:35:00")

    info1 = {"id": GROUP_INFO1, "name": "info1", "divisionTag": "4", "entireClass": False}

    ofo_raw = _lesson(
        OSZTALYFONOKI_ID,
        period_1,
        _subject("Osztályfőnöki", "Ofő"),
        teachers=[_teacher("Teszt Tanár")],
        classrooms=[_classroom("A.101", "A101")],
    )
    digitalis_raw = _lesson(
        DIGITALIS_ID,
        period_4,
        _subject("Digitális kultúra", "DiKu"),
        teachers=[_teacher("Mészáros Tamás", "Mészáros")],
        classrooms=[_classroom("A.118 - Informatika", "A118")],
        groups=[info1],
        groups_ids=[GROUP_INFO1],
    )

    lessons = [Lesson.from_raw(ofo_raw), Lesson.from_raw(digitalis_raw)]

    moved_lessons = [
        {
            "classroom": {"id": "room-b021", "name": "B.021", "short": "B021"},
            "dayDefinition": {"id": "day-mon", "name": "Hétfő", "short": "Hé", "days": ["1"]},
            "lessons": [ofo_raw],
            "movedLesson": {
                "id": "moved-1",
                "date": "2026-09-21T00:00:00.000Z",
                "room": "room-b021",
                "startingDay": "day-mon",
                "startingPeriod": "period-1",
                "comment": None,
            },
            "period": period_1,
        }
    ]

    substitutions = [
        {
            "lessons": [OSZTALYFONOKI_ID],
            "substitution": {
                "id": "sub-cancel",
                "date": "2026-09-21T00:00:00.000Z",
                "substituter": None,
                "comment": None,
            },
            "teacher": None,
        },
        {
            "lessons": [DIGITALIS_ID],
            "substitution": {
                "id": "sub-swap",
                "date": "2026-09-21T00:00:00.000Z",
                "substituter": "teacher-nagy",
                "comment": None,
            },
            "teacher": {"firstName": "Nagy", "lastName": "Péter", "short": "Nagy P."},
        },
    ]

    return lessons, moved_lessons, substitutions


def _occurrences(date, selected=()):
    lessons, moved, subs = _fixtures()
    return schedule.occurrences_for_date(date, lessons, selected, moved, subs)


def test_local_date():
    assert schedule.local_date("2026-09-21T00:00:00.000Z") == dt.date(2026, 9, 21)
    # 23:30 UTC is 01:30 the next day in Budapest (CEST, +02:00).
    assert schedule.local_date("2026-09-21T23:30:00.000Z") == dt.date(2026, 9, 22)


def test_lesson_matches_groups():
    no_group = Lesson(
        id="x", weekday=1, period_no=1, start="08:00", end="08:45", subject="s", subject_short="s"
    )
    grouped = Lesson(
        id="y", weekday=1, period_no=1, start="08:00", end="08:45",
        subject="s", subject_short="s", group_ids={"g1"},
    )
    whole = Lesson(
        id="z", weekday=1, period_no=1, start="08:00", end="08:45",
        subject="s", subject_short="s", group_ids={"g2"}, entire_class=True,
    )
    assert schedule.lesson_matches_groups(no_group, []) is True
    assert schedule.lesson_matches_groups(no_group, ["g1"]) is True
    assert schedule.lesson_matches_groups(grouped, []) is False
    assert schedule.lesson_matches_groups(grouped, ["g1"]) is True
    assert schedule.lesson_matches_groups(grouped, ["g9"]) is False
    assert schedule.lesson_matches_groups(whole, []) is True


def test_occurrences_sorted_and_group_filter():
    # With both groups selected: two occurrences, sorted by start time.
    occs = _occurrences(MONDAY, selected={GROUP_INFO1})
    assert [o.lesson.id for o in occs] == [OSZTALYFONOKI_ID, DIGITALIS_ID]
    assert occs[0].start < occs[1].start

    # Empty selection excludes the group lesson, keeps the no-group lesson.
    occs_empty = _occurrences(MONDAY, selected=set())
    assert [o.lesson.id for o in occs_empty] == [OSZTALYFONOKI_ID]


def test_moved_lesson_room_and_absence():
    # On the moved date the lesson appears in the target room.
    occs = _occurrences(MONDAY, selected={GROUP_INFO1})
    by_id = {o.lesson.id: o for o in occs}
    assert by_id[OSZTALYFONOKI_ID].moved is True
    assert by_id[OSZTALYFONOKI_ID].room == "B021"

    # On another Monday the lesson is moved away (absent).
    occs_other = _occurrences(OTHER_MONDAY, selected={GROUP_INFO1})
    assert [o.lesson.id for o in occs_other] == [DIGITALIS_ID]


def test_substitutions():
    occs = _occurrences(MONDAY, selected={GROUP_INFO1})
    by_id = {o.lesson.id: o for o in occs}
    assert by_id[OSZTALYFONOKI_ID].cancelled is True
    assert by_id[DIGITALIS_ID].substituted is True
    assert by_id[DIGITALIS_ID].teacher == "Nagy Péter"
    assert by_id[DIGITALIS_ID].cancelled is False


def test_current_occurrence():
    lessons, moved, subs = _fixtures()
    now = dt.datetime(2026, 9, 28, 11, 0, tzinfo=TZ)
    occ = schedule.current_occurrence(now, lessons, {GROUP_INFO1}, moved, subs)
    assert occ is not None
    assert occ.lesson.id == DIGITALIS_ID


def test_current_break_and_next():
    lessons, moved, subs = _fixtures()
    # 09:00 Monday: break, no current lesson; next is Digitális kultúra at 10:50.
    now = dt.datetime(2026, 9, 28, 9, 0, tzinfo=TZ)
    assert schedule.current_occurrence(now, lessons, {GROUP_INFO1}, moved, subs) is None
    nxt = schedule.next_occurrence(now, lessons, {GROUP_INFO1}, moved, subs)
    assert nxt is not None
    assert nxt.lesson.id == DIGITALIS_ID
    assert nxt.start == dt.datetime(2026, 9, 28, 10, 50, tzinfo=TZ)


def test_next_across_week():
    lessons, moved, subs = _fixtures()
    # After the last Monday lesson, the next occurrence is the following Monday.
    now = dt.datetime(2026, 9, 28, 12, 0, tzinfo=TZ)
    nxt = schedule.next_occurrence(now, lessons, {GROUP_INFO1}, moved, subs)
    assert nxt is not None
    assert nxt.lesson.id == DIGITALIS_ID
    assert nxt.date == dt.date(2026, 10, 5)


def test_expand_range():
    lessons, moved, subs = _fixtures()
    occs = schedule.expand_range(
        MONDAY, OTHER_MONDAY, lessons, {GROUP_INFO1}, moved, subs
    )
    # Monday (moved+cancelled+substituted) + next Monday (Digitális only).
    assert [o.lesson.id for o in occs] == [OSZTALYFONOKI_ID, DIGITALIS_ID, DIGITALIS_ID]


def test_first_occurrence_after_day():
    # Sunday 2026-09-20; tomorrow is Monday 2026-09-21.
    now = dt.datetime(2026, 9, 20, 12, 0, tzinfo=TZ)
    tomorrow = now.date() + dt.timedelta(days=1)
    lesson = Lesson(
        id="tomorrow", weekday=tomorrow.isoweekday(), period_no=1,
        start="08:00", end="08:45", subject="s", subject_short="s",
    )
    occ = schedule.first_occurrence_after_day(now, [lesson], set(), [], [])
    assert occ is not None
    assert occ.date == tomorrow
    assert occ.start == dt.datetime(2026, 9, 21, 8, 0, tzinfo=TZ)

    # No lessons in range -> None.
    assert schedule.first_occurrence_after_day(now, [], set(), [], [], max_days=7) is None
