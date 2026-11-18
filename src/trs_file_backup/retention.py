"""Retention rules: read backup names back and decide which backups to keep (spec FR-8).

Nothing here touches the file system: backup.list_backup_groups() lists the backups and backup.delete_backup() deletes one.
All times are naive local time, as the backup names are written (spec AC-2.2, AC-8.4).
"""

import re
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass, fields
from datetime import date, datetime, timedelta

# The setting keys of the rules are "retention.<field>" (spec FR-8); the state file uses the field names (spec AC-8.15)
RULE_FIELDS = ("hours", "days", "weeks", "months")
NO_LIMIT = -1
# No two times lie further apart than this; a larger hours rule keeps every backup, also when timedelta could not hold it
_MAX_HOURS = (datetime.max - datetime.min) // timedelta(hours=1)

# "_YYYY_MM_DD__HH_MM_SS" as AC-2.2 writes it: ASCII digits only, because \d also matches other Unicode digits
_TIMESTAMP = re.compile(r"_([0-9]{4})_([0-9]{2})_([0-9]{2})__([0-9]{2})_([0-9]{2})_([0-9]{2})")
_TIMESTAMP_LENGTH = len("_YYYY_MM_DD__HH_MM_SS")


def is_valid_rule_value(value: object) -> bool:
    """Tell whether value is an allowed rule: a whole number 0 or more, or -1 (spec AC-8.2, AC-8.16).

    A bool is rejected although Python treats it as an int, because the state file must hold a JSON integer.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= NO_LIMIT


@dataclass(frozen=True)
class RetentionRules:
    """The four retention rules (spec FR-8): 0 turns a rule off, -1 means no limit."""

    hours: int = 0
    days: int = 0
    weeks: int = 0
    months: int = 0

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if not is_valid_rule_value(value):
                raise ValueError(f"Invalid retention rule {field.name}: {value!r} (allowed: 0 or more, or -1)")

    @property
    def is_off(self) -> bool:
        """True when all rules are 0, so no backup is deleted (spec AC-8.3)."""
        return all(getattr(self, name) == 0 for name in RULE_FIELDS)


@dataclass(frozen=True)
class ParsedBackup:
    """A backup name read back into the original file name and the time of the backup (spec AC-8.6)."""

    name: str
    original: str
    timestamp: datetime


def _reading_at(name: str, start: int) -> ParsedBackup | None:
    """Return the reading of name with the timestamp starting at index start, if it gives name back."""
    # Imported here: backup imports state, and state imports this module for the rules
    from trs_file_backup.backup import BackupManager

    match = _TIMESTAMP.fullmatch(name, start, start + _TIMESTAMP_LENGTH)
    if match is None:
        return None
    year, month, day, hour, minute, second = (int(part) for part in match.groups())
    try:
        timestamp = datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None
    original = name[:start] + name[start + _TIMESTAMP_LENGTH :]
    # A hidden file is never backed up (spec AC-4.1)
    if not original or original.startswith("."):
        return None
    if BackupManager.generate_backup_filename(original, timestamp) != name:
        return None
    return ParsedBackup(name=name, original=original, timestamp=timestamp)


def parse_backup_name(name: str) -> ParsedBackup | None:
    """Read a backup name back into original file name and time, or return None when it is no backup name (spec AC-8.6).

    The name is a backup of original O at time T only when generate_backup_filename(O, T) gives exactly this name.
    The timestamp can therefore stand only right before the suffix, that is before the last dot, or at the end of the name.
    When both readings give the name back (an original name ending with a dot on Python 3.13),
    the reading whose original name does not end with a dot is used (spec KL-2).
    """
    starts = {len(name) - _TIMESTAMP_LENGTH}
    last_dot = name.rfind(".")
    if last_dot >= 0:
        starts.add(last_dot - _TIMESTAMP_LENGTH)
    readings = [reading for start in sorted(starts) if start >= 0 and (reading := _reading_at(name, start)) is not None]
    if not readings:
        return None
    return min(readings, key=lambda reading: reading.original.endswith("."))


def group_backups(names: Iterable[str]) -> dict[str, list[ParsedBackup]]:
    """Group the backup names by original file name, compared case-sensitively; other names are left out (spec AC-8.7, AC-8.8)."""
    groups: dict[str, list[ParsedBackup]] = {}
    for name in names:
        parsed = parse_backup_name(name)
        if parsed is not None:
            groups.setdefault(parsed.original, []).append(parsed)
    return groups


def _iso_week(timestamp: datetime) -> tuple[int, int]:
    iso = timestamp.isocalendar()
    return iso.year, iso.week


def _calendar_day(timestamp: datetime) -> date:
    return timestamp.date()


def _calendar_month(timestamp: datetime) -> tuple[int, int]:
    return timestamp.year, timestamp.month


def _newest_per_period(newest_first: list[ParsedBackup], count: int, period_of: Callable[[datetime], Hashable]) -> set[ParsedBackup]:
    """Keep the newest backup of each of the first count periods that hold a backup, newest period first (spec AC-8.5)."""
    if count == 0:
        return set()
    kept: dict[Hashable, ParsedBackup] = {}
    for item in newest_first:
        period = period_of(item.timestamp)
        if period in kept:
            continue
        if count != NO_LIMIT and len(kept) == count:
            break
        kept[period] = item
    return set(kept.values())


def select_backups_to_keep(backups: Iterable[ParsedBackup], rules: RetentionRules, now: datetime) -> set[ParsedBackup]:
    """Return the backups of one original file that the rules keep (spec AC-8.1 to AC-8.5).

    A backup is kept when at least one rule keeps it, and the newest backup is always kept.
    When all rules are 0, every backup is kept.
    Of two backups with the same time, the one with the greater name counts as newer, so the result does not depend on the input order.
    """
    newest_first = sorted(backups, key=lambda item: (item.timestamp, item.name), reverse=True)
    if rules.is_off or not newest_first:
        return set(newest_first)

    keep = {newest_first[0]}
    if rules.hours == NO_LIMIT or rules.hours > _MAX_HOURS:
        keep.update(newest_first)
    elif rules.hours > 0:
        # A time after now gives a negative age, so a backup from the future counts as younger than N hours (spec AC-8.4)
        keep.update(item for item in newest_first if now - item.timestamp < timedelta(hours=rules.hours))
    keep |= _newest_per_period(newest_first, rules.days, _calendar_day)
    keep |= _newest_per_period(newest_first, rules.weeks, _iso_week)
    keep |= _newest_per_period(newest_first, rules.months, _calendar_month)
    return keep


@dataclass(frozen=True)
class RetentionPlan:
    """The backups of one original file split into those the rules keep and those they delete, each newest first."""

    keep: list[ParsedBackup]
    delete: list[ParsedBackup]


def plan_retention(backups: Iterable[ParsedBackup], rules: RetentionRules, now: datetime, always_keep: str | None = None) -> RetentionPlan:
    """Split the backups of one original file into kept and deleted ones by select_backups_to_keep (spec AC-8.1 to AC-8.5).

    The backup named always_keep is kept whatever the rules say: run and watch pass the backup they have just made (spec AC-8.9).
    """
    newest_first = sorted(backups, key=lambda item: (item.timestamp, item.name), reverse=True)
    keep = select_backups_to_keep(newest_first, rules, now)
    kept = [item for item in newest_first if item in keep or item.name == always_keep]
    return RetentionPlan(keep=kept, delete=[item for item in newest_first if item not in kept])
