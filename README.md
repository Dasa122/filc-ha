# Filc for Home Assistant

A custom integration that brings your [Filc](https://filc.petrik.hu) school
timetable into Home Assistant: a **calendar** with your lessons plus sensors
that show the **current lesson, the next lesson, a live countdown and the room** —
so it looks great on your phone (iPhone **and** Android via the Home Assistant
companion app).

## Features

- `calendar.filc_<class>` — every lesson as a calendar event, with substitutions
  (`helyettesítés`) and moved lessons (`teremcsere / áthelyezés`), and cancellations
  marked `ELMARAD`.
- `sensor.filc_current_lesson` — the subject happening now, or `Szünet` during a break.
- `sensor.filc_next_lesson` — the next subject, with its **room** and teacher.
- `sensor.filc_current_lesson_end` / `sensor.filc_next_lesson_start` — timestamp
  sensors (`device_class: timestamp`) so Home Assistant shows a **live countdown**
  automatically on every dashboard and widget.
- `binary_sensor.filc_in_lesson` — on during a lesson, off during breaks (great for
  phone automations such as silencing notifications).
- Optional **phone notifications** — pick your phone in the integration options and
  Filc reminds you before lessons and at breaks (no YAML).

The current/next logic is aware of **substitutions**, **moved lessons** and
**cancelled lessons**, and it uses your real group choices (English/PE/IT splits)
when you provide an API key.

## Installation

### HACS (recommended)

1. HACS → **⋮** → **Custom repositories**.
2. Add `https://github.com/dasa122/filc-ha` with category **Integration**.
3. Install **Filc**, then restart Home Assistant.

### Manual

Copy `custom_components/filc/` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

1. **Settings → Devices & Services → Add Integration → Filc.**
2. **Server URL** — leave the default (`https://filc.petrik.hu`) unless you self-host.
3. **API key (optional)** — see below. With a key, the group picker is pre-filled with
   the groups you selected in the live Filc app.
4. **Class** — pick your class from the list.
5. **Groups** — pick one group per split (e.g. *angol*, *tesi*, *info*).

### Creating an API key (optional)

Filc has no API-key screen yet, but the endpoint exists. Easiest way:

1. Open Filc in your browser and log in.
2. DevTools → **Network** → right-click any `/api/...` request → **Copy as cURL**.
3. Adapt it into a create-key request (paste the session cookie from the copied cURL):

```bash
curl -s -X POST https://filc.petrik.hu/api/users/me/api-keys \
  -H 'Content-Type: application/json' \
  -b '<paste your filc session cookie here>' \
  -d '{"name":"home-assistant"}' | jq -r .data.rawKey
```

The raw key is shown **only once**. Paste it into the integration. Without a key the
integration still works — you simply pick your groups by hand.

> Without a key the integration reads only public timetable data. A key additionally
> unlocks your personal group selection (and, in a future release, notifications).

## Entities

| Entity | Description |
| --- | --- |
| `calendar.filc_<class>` | Lessons, substitutions and moved lessons |
| `sensor.filc_current_lesson` | Current subject (or `Szünet`), room, teacher, `ends_at` |
| `sensor.filc_next_lesson` | Next subject, room, teacher, `starts_at` |
| `sensor.filc_current_lesson_end` | Timestamp → live countdown to the end of the lesson |
| `sensor.filc_next_lesson_start` | Timestamp → live countdown to the next lesson |
| `binary_sensor.filc_in_lesson` | On during a lesson |

Entity ids depend on your class (e.g. `sensor.filc_9a_current_lesson`).

## On your phone (iPhone & Android)

Everything is standard Home Assistant, so both the iOS and Android companion apps
render it natively — no platform-specific setup:

- **Entities card** — the two timestamp sensors show *"in 23 minutes"* automatically.
- **Widgets** — add `sensor.filc_next_lesson` to a home-screen widget on either OS.
- **Calendar** — `calendar.filc_<class>` works in the HA calendar view in both apps.

A compact dashboard card that works on both platforms:

```yaml
type: markdown
content: >
  ## {{ states('sensor.filc_current_lesson') }}
  {% if state_attr('sensor.filc_current_lesson','room') %}
  📍 {{ state_attr('sensor.filc_current_lesson','room') }} ·
  {{ state_attr('sensor.filc_current_lesson','teacher') or '' }}
  {% endif %}
  {% set end = state_attr('sensor.filc_current_lesson','ends_at') %}
  {% if end %}⏳ vége: {{ ((as_timestamp(end) - now().timestamp()) / 60) | round(0) }} perc{% endif %}

  **Következő:** {{ states('sensor.filc_next_lesson') }}
  {% if state_attr('sensor.filc_next_lesson','room') %}· 📍 {{ state_attr('sensor.filc_next_lesson','room') }}{% endif %}
  {% set start = state_attr('sensor.filc_next_lesson','starts_at') %}
  {% if start %}({{ ((as_timestamp(start) - now().timestamp()) / 60) | round(0) }} perc){% endif %}
```

Example automation — silence your phone during lessons:

```yaml
automation:
  - alias: Filc – ne zavarjanak órán
    trigger:
      - platform: state
        entity_id: binary_sensor.filc_9a_in_lesson
        to: "on"
    action:
      - service: notify.mobile_app_your_phone
        data:
          message: "Óra kezdődött"
```

## Show it on a specific phone

**Display (dashboard / widgets).** Each phone signs in to Home Assistant as a user and sees that user's default dashboard:

- **Per-phone dashboard** — *Settings → Dashboards → open your Filc dashboard → Visibility* → restrict it to the user account that phone is signed in with. Or set the default dashboard on that user's profile (click the user → *Default dashboard*).
- **Same dashboard on both phones** — add the cards from [`examples/mobile_dashboard.yaml`](examples/mobile_dashboard.yaml); they render identically on iOS and Android.
- **Home-screen widgets** — add `sensor.filc_<class>_next_lesson` and the timestamp sensors to a widget on either OS. Widgets are local to that phone.

**Built-in phone picker (no YAML).** Open the integration's **Configure** dialog
(*Settings → Devices & Services → Filc → Configure*). The **Notification phone**
dropdown lists your phones (the `notify.mobile_app_*` services); pick one and Filc
then sends, on its own:

- a reminder *N minutes* before each lesson (*Reminder before lesson*), and
- a *break summary* when a lesson ends (*Send break summary*), showing the next
  subject and room.

Leave the dropdown on *(kikapcsolva)/(disabled)* to turn notifications off. This
works on both iPhone and Android and needs no automation.

Prefer automations? The same entities drive them — see
[`examples/automation_next_lesson.yaml`](examples/automation_next_lesson.yaml)
(`phone_service` variable, or a [`notify` group](https://www.home-assistant.io/integrations/notify.group/)
for several phones) and
[`examples/automation_in_lesson_dnd.yaml`](examples/automation_in_lesson_dnd.yaml).

### See it inside the integration

- **Sensors / entities** — *Settings → Devices & Services → Filc → click the class*. Every entity
  (`current_lesson`, `next_lesson`, the two timestamp countdown sensors, `in_lesson`, the calendar
  and the button) is listed there, under one device per class.
- **Test live actions button** — press `button.filc_<class>_test_live_actions` to send the *current*
  live action to the selected phone and to the Home Assistant notification area. Handy to verify
  the phone target and the message text without waiting for a lesson.
  Pressing it starts a **Live Activity** (iOS) / **Live Update** (Android) on the
  selected phone: the card stays on the Lock Screen / Dynamic Island. In a lesson it
  shows the current subject, its room and the end time with a live progress bar and a
  countdown to the end; during a break it reads as a break, counts down to when the
  break ends and shows the next lesson with its room. It needs a phone selected in *Configure → Notification
  phone*; without one the button only posts to the Home Assistant notification area.
  The activity is identified by the tag `filc_<class>`; sending
  `{"message": "clear_notification", "data": {"tag": "filc_<class>"}}` to the same
  phone ends it.
- **Download diagnostics** — *Filc → ⋮ → Download diagnostics* returns the resolved current/next
  lesson, counts and the active timetable (the API key is redacted).

## Troubleshooting

- **`cannot_connect`** — the public server may be down; check <https://filc.petrik.hu/api/ping>.
- **Wrong split shown** — open the integration **Configure** and pick the right group.
- **Countdown stuck** — the countdown is rendered by Home Assistant itself; make sure
  your device clock is correct. Raw timestamps are exposed as attributes.

## Development

```bash
python -m pytest tests/ -q          # pure-logic tests, no HA needed (needs: pip install pytest)
python -m py_compile custom_components/filc/*.py
```

### Try the schedule logic against live data

`tools/live_check.py` fetches real Filc data and prints the resolved day plus the
current/next/break state — no Home Assistant required:

```bash
python tools/live_check.py --class 9.A --groups info1,tesi2                        # right now
python tools/live_check.py --class 9.A --groups info1,tesi2 --at "2026-09-17 09:50" # simulate a break
python tools/live_check.py --class 9.A --groups info1,tesi2 --date 2026-09-18       # a substitution day
python tools/live_check.py --class 9.A --groups info1,tesi2 --simulate             # replay a whole day (starts, breaks, notifications)
python tools/live_check.py --class 9.A --groups info1,tesi2 --watch --interval 15   # live monitor, refreshes every 15s
python tools/live_check.py --class 9.A --api-key "<key>"                            # use your selected groups
```

`--simulate` prints the exact timeline the integration produces: each lesson start,
each break (with the next subject + room), and the notification text it would send
(`--lead` minutes before the lesson, `--no-break` to skip break notices, `--lang en`
for English). `--watch` shows the live state until you press Ctrl-C — leave it
running during a real school day to see it switch between `IN LESSON` and `BREAK`.

The schedule maths (`schedule.py`) is deliberately free of Home Assistant imports so
it can be tested in isolation.

## Roadmap

- Notification feed / door lock events — the API supports them, but they need an API
  key and Filc currently ships no key-management UI.

## Credits

The brand icon and logo are the official Filc assets from the
[filcdev/filc](https://github.com/filcdev/filc) project (AGPL-3.0), used here to
identify the service this integration connects to.

## License

MIT © 2026 dasa122
