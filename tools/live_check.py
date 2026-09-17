#!/usr/bin/env python3
"""Live check for the Filc integration's schedule logic.

Fetches real data from the Filc API and prints the resolved timetable for a
class, so the "current lesson / next lesson / break" behaviour can be verified
without running Home Assistant.

Examples:
    python tools/live_check.py --class 9.A --groups info1,tesi2
    python tools/live_check.py --class 9.A --groups info1,tesi2 --at "2026-09-17 09:00"
    python tools/live_check.py --class 9.A --groups info1,tesi2 --date 2026-09-18
    python tools/live_check.py --class 9.A --api-key "<filc api key>"
"""

from __future__ import annotations

import argparse
import calendar  # noqa: F401 - cache stdlib calendar before the component dir shadows it
import json
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "filc"))

import schedule  # noqa: E402
from models import Lesson  # noqa: E402

TZ = ZoneInfo("Europe/Budapest")
WEEKDAYS = [
    "Hétfő",
    "Kedd",
    "Szerda",
    "Csütörtök",
    "Péntek",
    "Szombat",
    "Vasárnap",
]


def api_get(base: str, path: str, params: dict | None = None, api_key: str = ""):
    url = base.rstrip("/") + "/api" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/json")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if not payload.get("success"):
        raise SystemExit(f"API error for {path}: {payload}")
    return payload["data"]


def resolve_cohort(base: str, name: str) -> tuple[dict, dict]:
    timetable = api_get(base, "/timetable/timetables/latestValid")
    cohorts = api_get(base, f"/timetable/cohorts/getAllForTimetable/{timetable['id']}")
    wanted = name.strip().lower()
    for cohort in cohorts:
        if cohort["name"].lower() == wanted or cohort["short"].lower() == wanted:
            return timetable, cohort
    names = ", ".join(sorted(c["name"] for c in cohorts))
    raise SystemExit(f"Class '{name}' not found. Available: {names}")


def resolve_groups(groups: list[dict], names: str, api_key: str) -> set[str]:
    if names:
        wanted = {n.strip().lower() for n in names.split(",") if n.strip()}
        available = {(g.get("name") or "").lower() for g in groups}
        missing = wanted - available
        if missing:
            listing = ", ".join(sorted(g.get("name", "?") for g in groups))
            raise SystemExit(f"Unknown group(s): {', '.join(sorted(missing))}. Available: {listing}")
        return {g["id"] for g in groups if (g.get("name") or "").lower() in wanted}
    if api_key:
        return {g["id"] for g in groups if g.get("selected")}
    return set()


def fmt_occurrence(occ) -> str:
    flags = []
    if occ.cancelled:
        flags.append("ELMARAD")
    if occ.substituted:
        flags.append("helyettesítés")
    if occ.moved:
        flags.append("áthelyezés")
    subject = occ.lesson.subject or occ.lesson.subject_short or "?"
    return (
        f"{occ.start:%H:%M}-{occ.end:%H:%M}  {subject:<26} {(occ.room or '-'):<10} "
        f"{(occ.teacher or '-'):<22} {' '.join(flags)}".rstrip()
    )


def minutes(delta: timedelta) -> str:
    total = int(delta.total_seconds() // 60)
    return f"{total} perc" if total >= 0 else f"{-total} perccel ezelőtt"


def main() -> int:
    parser = argparse.ArgumentParser(description="Live schedule check")
    parser.add_argument("--url", default="https://filc.petrik.hu")
    parser.add_argument("--class", dest="klass", required=True, help="class name, e.g. 9.A")
    parser.add_argument("--groups", default="", help="comma-separated group names, e.g. info1,tesi2")
    parser.add_argument("--api-key", default="", help="optional API key (uses your selected groups)")
    parser.add_argument("--at", default="", help='simulate a moment: "YYYY-MM-DD HH:MM"')
    parser.add_argument("--date", default="", help="print a specific day: YYYY-MM-DD")
    args = parser.parse_args()

    timetable, cohort = resolve_cohort(args.url, args.klass)

    lessons_raw = api_get(
        args.url,
        f"/timetable/lessons/getForCohort/{cohort['id']}",
        {"timetableId": timetable["id"]},
    )
    substitutions = (
        api_get(args.url, f"/timetable/substitutions/cohort/{cohort['id']}") or {}
    ).get("substitutions", [])
    moved = api_get(args.url, f"/timetable/movedLessons/cohort/{cohort['id']}/relevant")
    groups = api_get(args.url, f"/timetable/groups/getForCohort/{cohort['id']}")

    selected = resolve_groups(groups, args.groups, args.api_key)
    lessons = [Lesson.from_raw(raw) for raw in lessons_raw]

    now = (
        datetime.strptime(args.at, "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
        if args.at
        else schedule.now()
    )
    day = date.fromisoformat(args.date) if args.date else now.date()

    occurrences = schedule.occurrences_for_date(day, lessons, selected, moved, substitutions)

    chosen = ", ".join(sorted(g["name"] for g in groups if g["id"] in selected))
    print(f"Filc        : {args.url}  ({timetable['name']})")
    print(f"Class       : {cohort['name']}  ({len(lessons)} lessons/week)")
    print(f"Groups      : {chosen or '(all / none selected)'}")
    print(f"Now         : {now:%Y-%m-%d %H:%M %Z}  ({WEEKDAYS[now.weekday()]})")
    print(f"\nTimetable for {day} ({len(occurrences)} lessons):")
    if not occurrences:
        print("  (no lessons)")
    for occ in occurrences:
        marker = "   <== NOW" if now.date() == day and occ.start <= now < occ.end else ""
        print("  " + fmt_occurrence(occ) + marker)

    if now.date() == day:
        current = schedule.current_occurrence(now, lessons, selected, moved, substitutions)
        upcoming = schedule.next_occurrence(now, lessons, selected, moved, substitutions)
        print("\n--- live actions ---")
        if current is not None:
            subject = current.lesson.subject or current.lesson.subject_short or "?"
            print(f"STATE       : IN LESSON -> {subject}  ({current.room or '-'})")
            print(f"ENDS IN     : {minutes(current.end - now)}")
        elif upcoming is not None and upcoming.date == day:
            subject = upcoming.lesson.subject or upcoming.lesson.subject_short or "?"
            print("STATE       : BREAK")
            print(f"NEXT LESSON : {subject}  ({upcoming.room or '-'}, {upcoming.teacher or '-'})")
            print(f"STARTS IN   : {minutes(upcoming.start - now)}")
        else:
            print("STATE       : NO MORE LESSONS TODAY")
        if upcoming is not None:
            subject = upcoming.lesson.subject or upcoming.lesson.subject_short or "?"
            print(
                f"upcoming    : {subject} on {upcoming.date} at {upcoming.start:%H:%M}"
                f"  ({minutes(upcoming.start - now)})"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
