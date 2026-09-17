"""Constants for the Filc integration."""

DOMAIN = "filc"
DEFAULT_BASE_URL = "https://filc.petrik.hu"
API_PREFIX = "/api"
SCHOOL_TZ = "Europe/Budapest"
DEFAULT_SCAN_INTERVAL = 300

# Fallback weekday mapping (ISO weekday 1=Mon .. 5=Fri) used only when a
# lesson's `day.days` list is absent.
WEEKDAY_MAP = {
    "Hétfő": 1,
    "Hé": 1,
    "Kedd": 2,
    "Ke": 2,
    "Szerda": 3,
    "Sz": 3,
    "Csütörtök": 4,
    "Cs": 4,
    "Péntek": 5,
    "Pé": 5,
}

# Config entry / options keys
CONF_BASE_URL = "base_url"
CONF_API_KEY = "api_key"
CONF_COHORT_ID = "cohort_id"
CONF_COHORT_NAME = "cohort_name"
CONF_TIMETABLE_ID = "timetable_id"
CONF_SELECTED_GROUP_IDS = "selected_group_ids"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_NOTIFY_LEAD = "notify_lead"
CONF_NOTIFY_ON_BREAK = "notify_on_break"

DEFAULT_NOTIFY_LEAD = 5
DEFAULT_NOTIFY_ON_BREAK = True
