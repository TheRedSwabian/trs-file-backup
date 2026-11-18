"""Tests for the retention rules: reading backup names back and selecting the backups to keep (spec FR-8)."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from trs_file_backup.backup import BackupManager
from trs_file_backup.retention import (
    ParsedBackup,
    RetentionRules,
    group_backups,
    is_valid_rule_value,
    parse_backup_name,
    select_backups_to_keep,
)

T = datetime(2026, 1, 13, 14, 30, 22)
T_TEXT = "2026_01_13__14_30_22"


def backup(original: str, timestamp: datetime) -> ParsedBackup:
    """Return the parsed backup of original at timestamp, as a real listing would give it."""
    return ParsedBackup(name=BackupManager.generate_backup_filename(original, timestamp), original=original, timestamp=timestamp)


def kept_times(backups: list[ParsedBackup], rules: RetentionRules, now: datetime) -> list[datetime]:
    """Return the timestamps of the kept backups, newest first."""
    return sorted((item.timestamp for item in select_backups_to_keep(backups, rules, now)), reverse=True)


class TestParseBackupName:
    """Reading a backup name back into original name and time (spec AC-8.6)."""

    def test_simple_name(self) -> None:
        assert parse_backup_name(f"report_{T_TEXT}.txt") == ParsedBackup(name=f"report_{T_TEXT}.txt", original="report.txt", timestamp=T)

    def test_several_dots_keep_all_but_the_last_in_the_stem(self) -> None:
        parsed = parse_backup_name(f"a.tar_{T_TEXT}.gz")

        assert parsed is not None
        assert (parsed.original, parsed.timestamp) == ("a.tar.gz", T)

    def test_no_suffix(self) -> None:
        parsed = parse_backup_name(f"Makefile_{T_TEXT}")

        assert parsed is not None
        assert (parsed.original, parsed.timestamp) == ("Makefile", T)

    def test_stem_that_itself_ends_in_a_timestamp(self) -> None:
        name = f"log_2025_05_05__05_05_05_{T_TEXT}.txt"

        parsed = parse_backup_name(name)

        assert parsed is not None
        assert (parsed.original, parsed.timestamp) == ("log_2025_05_05__05_05_05.txt", T)

    def test_timestamp_inside_the_suffix_is_not_read_as_backup_time(self) -> None:
        # The backup name of a.x at T is a_<T>.x, so a.x_<T> is no backup name of any original file
        assert parse_backup_name(f"a.x_{T_TEXT}") is None

    def test_invalid_date_is_no_backup(self) -> None:
        assert parse_backup_name("report_2026_13_45__14_30_22.txt") is None
        assert parse_backup_name("report_2026_02_30__14_30_22.txt") is None
        assert parse_backup_name("report_2026_01_13__24_00_00.txt") is None

    def test_unpadded_digits_are_no_backup(self) -> None:
        assert parse_backup_name("report_2026_1_13__14_30_22.txt") is None
        assert parse_backup_name("report_2026_01_13__4_30_22.txt") is None

    def test_non_ascii_digits_are_no_backup(self) -> None:
        # ARABIC-INDIC DIGIT ONE and FULLWIDTH DIGIT TWO count as digits for int() and for the regex class \d
        assert parse_backup_name("report_2026_0\u0661_13__14_30_22.txt") is None
        assert parse_backup_name("report_\uff12026_01_13__14_30_22.txt") is None

    def test_empty_original_name_is_no_backup(self) -> None:
        assert parse_backup_name(f"_{T_TEXT}") is None
        assert parse_backup_name(f"_{T_TEXT}.txt") is None

    def test_hidden_original_name_is_no_backup(self) -> None:
        # The backup name of .profile would be .profile_<T>; a hidden file is never backed up (spec AC-4.1)
        assert BackupManager.generate_backup_filename(".profile", T) == f".profile_{T_TEXT}"
        assert parse_backup_name(f".profile_{T_TEXT}") is None
        assert parse_backup_name(f".hidden_{T_TEXT}.txt") is None

    @pytest.mark.parametrize(
        "name",
        [
            "notes.txt",
            "",
            T_TEXT,
            f"report{T_TEXT}.txt",
            f"report_{T_TEXT}x.txt",
            f"report_{T_TEXT}.txt.bak",
            f"report-{T_TEXT}.txt",
            "report_2026_01_13_14_30_22.txt",
        ],
    )
    def test_foreign_files_are_no_backup(self, name: str) -> None:
        assert parse_backup_name(name) is None

    def test_temporary_file_is_no_backup(self) -> None:
        assert parse_backup_name(".trs-file-backup-0123456789ab.tmp") is None

    def test_log_file_is_no_backup(self) -> None:
        assert parse_backup_name("backup.log") is None

    def test_state_file_is_no_backup(self) -> None:
        assert parse_backup_name(".backup_state.json") is None

    def test_trailing_dot_name_round_trips(self) -> None:
        # Python 3.13 gives "a." an empty suffix, later versions the suffix "." (spec AC-2.2, KL-2); the round trip holds on both
        name = BackupManager.generate_backup_filename("a.", T)

        parsed = parse_backup_name(name)

        assert parsed is not None
        assert (parsed.original, parsed.timestamp) == ("a.", T)

    def test_trailing_dot_name_with_two_readings_uses_the_one_without_trailing_dot(self) -> None:
        # The example of KL-2: on Python 3.13 this is the backup name of both readings, on later versions of the first only
        earlier = datetime(2026, 1, 12, 9, 0, 0)
        name = f"a_2026_01_12__09_00_00._{T_TEXT}"
        both_readings = Path("a.").suffix == ""
        assert (BackupManager.generate_backup_filename("a_2026_01_12__09_00_00.", T) == name) is both_readings

        parsed = parse_backup_name(name)

        assert parsed is not None
        assert (parsed.original, parsed.timestamp) == (f"a._{T_TEXT}", earlier)

    def test_backup_of_name_ending_in_timestamp_and_dot_is_read_by_the_current_version(self) -> None:
        # On Python 3.13 this backup is misread (KL-2); from 3.14 on the dot follows the timestamp and the reading is unique
        original = "a_2026_01_12__09_00_00."
        name = BackupManager.generate_backup_filename(original, T)

        parsed = parse_backup_name(name)

        assert parsed is not None
        if Path("a.").suffix == "":
            assert (parsed.original, parsed.timestamp) == (f"a._{T_TEXT}", datetime(2026, 1, 12, 9, 0, 0))
        else:
            assert (parsed.original, parsed.timestamp) == (original, T)

    @pytest.mark.parametrize(
        "original",
        ["report.txt", "a.tar.gz", "Makefile", "a..b", "x_2025_05_05__05_05_05.txt", "a.x_2025_05_05__05_05_05", "with space.doc", "\u00e4rger.txt", "_.txt"],
    )
    @pytest.mark.parametrize("timestamp", [T, datetime(2027, 12, 31, 23, 59, 59), datetime(2026, 1, 1, 0, 0, 0)])
    def test_round_trip_against_generate_backup_filename(self, original: str, timestamp: datetime) -> None:
        name = BackupManager.generate_backup_filename(original, timestamp)

        assert parse_backup_name(name) == ParsedBackup(name=name, original=original, timestamp=timestamp)


class TestGroupBackups:
    """Grouping the names of a directory by original file (spec AC-8.7, AC-8.8)."""

    def test_groups_by_original_and_skips_names_that_are_no_backup(self) -> None:
        names = [
            f"report_{T_TEXT}.txt",
            "report_2026_01_14__08_00_00.txt",
            f"Report_{T_TEXT}.txt",
            "backup.log",
            ".backup_state.json",
            ".trs-file-backup-0123456789ab.tmp",
            "notes.txt",
        ]

        groups = group_backups(names)

        assert sorted(groups) == ["Report.txt", "report.txt"]
        assert sorted(item.name for item in groups["report.txt"]) == [f"report_{T_TEXT}.txt", "report_2026_01_14__08_00_00.txt"]
        assert [item.name for item in groups["Report.txt"]] == [f"Report_{T_TEXT}.txt"]

    def test_two_backups_in_the_same_second_of_different_files_are_two_groups(self) -> None:
        groups = group_backups([f"a_{T_TEXT}.txt", f"b_{T_TEXT}.txt"])

        assert {original: len(items) for original, items in groups.items()} == {"a.txt": 1, "b.txt": 1}


class TestRetentionRules:
    """The four rules and their allowed values (spec AC-8.1, AC-8.2, AC-8.16)."""

    def test_default_is_off(self) -> None:
        assert RetentionRules().is_off
        assert RetentionRules(0, 0, 0, 0).is_off

    @pytest.mark.parametrize("field", ["hours", "days", "weeks", "months"])
    @pytest.mark.parametrize("value", [1, -1])
    def test_any_rule_set_is_not_off(self, field: str, value: int) -> None:
        assert not RetentionRules(**{field: value}).is_off

    @pytest.mark.parametrize("value", [0, 1, 24, 10_000, -1])
    def test_valid_values(self, value: int) -> None:
        assert is_valid_rule_value(value)

    @pytest.mark.parametrize("value", [-2, -100, True, False, 1.5, 7.0, "7", None, [1]])
    def test_invalid_values(self, value: object) -> None:
        assert not is_valid_rule_value(value)

    @pytest.mark.parametrize("field", ["hours", "days", "weeks", "months"])
    def test_rules_reject_an_invalid_value(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            RetentionRules(**{field: -2})


class TestSelectBackupsToKeep:
    """Selecting the backups of one original file to keep (spec AC-8.1 to AC-8.5)."""

    NOW = datetime(2026, 3, 15, 12, 0, 0)

    def hourly(self, count: int) -> list[ParsedBackup]:
        """Return one backup per hour, the newest at NOW."""
        return [backup("r.txt", self.NOW - timedelta(hours=offset)) for offset in range(count)]

    def test_no_backups_keeps_nothing(self) -> None:
        assert select_backups_to_keep([], RetentionRules(days=1), self.NOW) == set()

    def test_all_rules_zero_keeps_everything(self) -> None:
        backups = self.hourly(100)

        assert select_backups_to_keep(backups, RetentionRules(), self.NOW) == set(backups)

    def test_newest_is_always_kept(self) -> None:
        backups = [backup("r.txt", datetime(2020, 1, 1)), backup("r.txt", datetime(2021, 6, 1))]

        assert kept_times(backups, RetentionRules(hours=1), self.NOW) == [datetime(2021, 6, 1)]

    def test_hours_keeps_backups_younger_than_n_hours(self) -> None:
        backups = self.hourly(10)

        assert kept_times(backups, RetentionRules(hours=3), self.NOW) == [self.NOW - timedelta(hours=offset) for offset in range(3)]

    def test_hours_boundary_exactly_n_hours_old_is_not_kept(self) -> None:
        backups = [backup("r.txt", self.NOW - timedelta(hours=2)), backup("r.txt", self.NOW - timedelta(hours=1, minutes=59, seconds=59))]
        older = backup("r.txt", self.NOW - timedelta(hours=3))

        kept = select_backups_to_keep([*backups, older], RetentionRules(hours=2), self.NOW)

        assert kept == {backups[1]}

    def test_hours_minus_one_keeps_every_backup(self) -> None:
        backups = [*self.hourly(5), backup("r.txt", datetime(2001, 1, 1))]

        assert select_backups_to_keep(backups, RetentionRules(hours=-1), self.NOW) == set(backups)

    def test_hours_too_large_for_a_time_span_keeps_every_backup(self) -> None:
        backups = [*self.hourly(3), backup("r.txt", datetime(1, 1, 1))]

        assert select_backups_to_keep(backups, RetentionRules(hours=10**12), self.NOW) == set(backups)

    def test_days_keeps_newest_per_counted_day(self) -> None:
        backups = [
            backup("r.txt", datetime(2026, 3, 15, 9)),
            backup("r.txt", datetime(2026, 3, 15, 8)),
            backup("r.txt", datetime(2026, 3, 14, 23)),
            backup("r.txt", datetime(2026, 3, 14, 1)),
            backup("r.txt", datetime(2026, 3, 13, 12)),
        ]

        assert kept_times(backups, RetentionRules(days=2), self.NOW) == [datetime(2026, 3, 15, 9), datetime(2026, 3, 14, 23)]

    def test_days_does_not_count_days_without_a_backup(self) -> None:
        # The file was untouched for months: the last three days with a backup are kept, however long ago
        backups = [backup("r.txt", datetime(2025, month, 10, 12)) for month in (1, 4, 7, 10)]

        assert kept_times(backups, RetentionRules(days=3), self.NOW) == [datetime(2025, 10, 10, 12), datetime(2025, 7, 10, 12), datetime(2025, 4, 10, 12)]

    def test_days_minus_one_keeps_newest_of_every_day(self) -> None:
        backups = [backup("r.txt", datetime(2026, 3, day, hour)) for day in (1, 5, 9) for hour in (8, 17)]

        assert kept_times(backups, RetentionRules(days=-1), self.NOW) == [datetime(2026, 3, day, 17) for day in (9, 5, 1)]

    def test_weeks_keeps_newest_per_iso_week(self) -> None:
        backups = [
            backup("r.txt", datetime(2026, 3, 15, 10)),  # Sunday, week 11
            backup("r.txt", datetime(2026, 3, 9, 10)),  # Monday, week 11
            backup("r.txt", datetime(2026, 3, 8, 10)),  # Sunday, week 10
            backup("r.txt", datetime(2026, 3, 2, 10)),  # Monday, week 10
            backup("r.txt", datetime(2026, 2, 27, 10)),  # Friday, week 9
        ]

        assert kept_times(backups, RetentionRules(weeks=2), self.NOW) == [datetime(2026, 3, 15, 10), datetime(2026, 3, 8, 10)]

    def test_iso_week_53_across_the_year_boundary_is_one_week(self) -> None:
        # 2026-12-28 to 2027-01-03 is ISO week 53 of 2026
        now = datetime(2027, 1, 10, 12)
        backups = [
            backup("r.txt", datetime(2027, 1, 4, 9)),  # week 1 of 2027
            backup("r.txt", datetime(2027, 1, 2, 9)),  # week 53 of 2026
            backup("r.txt", datetime(2026, 12, 31, 9)),  # week 53 of 2026
            backup("r.txt", datetime(2026, 12, 27, 9)),  # week 52 of 2026
        ]

        # Week 53 holds 31 December and 2 January; were it split by calendar year, weeks=3 would keep 31 December instead of 27 December
        assert kept_times(backups, RetentionRules(weeks=3), now) == [datetime(2027, 1, 4, 9), datetime(2027, 1, 2, 9), datetime(2026, 12, 27, 9)]

    def test_months_keeps_newest_per_calendar_month_across_the_month_boundary(self) -> None:
        backups = [
            backup("r.txt", datetime(2026, 3, 1, 0, 0, 0)),
            backup("r.txt", datetime(2026, 2, 28, 23, 59, 59)),
            backup("r.txt", datetime(2026, 2, 1, 0, 0, 0)),
            backup("r.txt", datetime(2026, 1, 31, 23, 59, 59)),
            backup("r.txt", datetime(2025, 3, 31, 12)),
        ]

        assert kept_times(backups, RetentionRules(months=2), self.NOW) == [datetime(2026, 3, 1), datetime(2026, 2, 28, 23, 59, 59)]

    def test_month_of_another_year_is_another_month(self) -> None:
        backups = [backup("r.txt", datetime(2026, 3, 1)), backup("r.txt", datetime(2025, 3, 31))]

        assert kept_times(backups, RetentionRules(months=2), self.NOW) == [datetime(2026, 3, 1), datetime(2025, 3, 31)]

    def test_weeks_minus_one_keeps_newest_of_every_week(self) -> None:
        backups = [backup("r.txt", datetime(2026, 3, day, hour)) for day in (2, 9, 16) for hour in (8, 17)]

        assert kept_times(backups, RetentionRules(weeks=-1), datetime(2026, 3, 20)) == [datetime(2026, 3, day, 17) for day in (16, 9, 2)]

    def test_months_minus_one_keeps_newest_of_every_month(self) -> None:
        backups = [backup("r.txt", datetime(year, month, day)) for year in (2024, 2025) for month in (1, 6) for day in (1, 20)]

        expected = [datetime(year, month, 20) for year in (2025, 2024) for month in (6, 1)]
        assert kept_times(backups, RetentionRules(months=-1), self.NOW) == expected

    def test_rules_combine_as_union(self) -> None:
        backups = [
            backup("r.txt", datetime(2026, 3, 15, 11)),  # newest
            backup("r.txt", datetime(2026, 3, 15, 10)),  # hours only
            backup("r.txt", datetime(2026, 3, 15, 1)),  # dropped: same day as a newer one, older than 3 hours
            backup("r.txt", datetime(2026, 3, 14, 20)),  # days only: newest of 14 March
            backup("r.txt", datetime(2026, 3, 14, 8)),  # dropped
            backup("r.txt", datetime(2026, 3, 2, 8)),  # weeks only: newest of ISO week 10 (week 11 runs from 9 to 15 March)
            backup("r.txt", datetime(2026, 1, 20, 8)),  # weeks and months: newest of ISO week 4 and of January
            backup("r.txt", datetime(2026, 1, 5, 8)),  # dropped: fourth counted week, January already kept
            backup("r.txt", datetime(2025, 12, 10, 8)),  # months only: newest of December, the third counted month
        ]
        rules = RetentionRules(hours=3, days=2, weeks=3, months=3)

        assert kept_times(backups, rules, self.NOW) == [
            datetime(2026, 3, 15, 11),
            datetime(2026, 3, 15, 10),
            datetime(2026, 3, 14, 20),
            datetime(2026, 3, 2, 8),
            datetime(2026, 1, 20, 8),
            datetime(2025, 12, 10, 8),
        ]

    def test_zero_turns_a_single_rule_off(self) -> None:
        backups = [backup("r.txt", datetime(2026, 3, day, 12)) for day in (10, 11, 12)]

        assert kept_times(backups, RetentionRules(hours=0, days=0, weeks=0, months=1), self.NOW) == [datetime(2026, 3, 12, 12)]

    def test_future_backup_counts_as_younger_than_n_hours(self) -> None:
        future = backup("r.txt", self.NOW + timedelta(days=30))
        past = backup("r.txt", self.NOW - timedelta(minutes=30))
        old = backup("r.txt", self.NOW - timedelta(hours=5))

        assert select_backups_to_keep([future, past, old], RetentionRules(hours=1), self.NOW) == {future, past}

    def test_future_backup_counts_in_its_period(self) -> None:
        # The future backup is the newest, so it is kept; it uses up the one counted day of days=1
        future = backup("r.txt", self.NOW + timedelta(days=30))
        today = backup("r.txt", self.NOW - timedelta(minutes=30))

        assert select_backups_to_keep([future, today], RetentionRules(days=1), self.NOW) == {future}
        assert select_backups_to_keep([future, today], RetentionRules(days=2), self.NOW) == {future, today}

    def test_two_backups_in_the_same_second_keep_one_by_name(self) -> None:
        # A real listing cannot give this (one original and one time make one name, KL-1); duplicate input still gives a stable result
        first = ParsedBackup(name="r_x", original="r.txt", timestamp=T)
        second = ParsedBackup(name="r_y", original="r.txt", timestamp=T)

        assert select_backups_to_keep([first, second], RetentionRules(days=1), T) == {second}
        assert select_backups_to_keep([second, first], RetentionRules(days=1), T) == {second}
        assert select_backups_to_keep([first, second], RetentionRules(hours=1), T) == {first, second}


class TestPlanRetention:
    """Splitting the backups of one original file into kept and deleted ones, for run, watch and cleanup (spec AC-8.1, AC-8.14)."""

    NOW = datetime(2026, 3, 15, 12, 0, 0)

    def test_splits_into_keep_and_delete_newest_first(self) -> None:
        from trs_file_backup.retention import plan_retention

        backups = [backup("r.txt", self.NOW - timedelta(days=offset)) for offset in (3, 0, 1, 2)]

        plan = plan_retention(backups, RetentionRules(days=2), self.NOW)

        assert [item.timestamp for item in plan.keep] == [self.NOW, self.NOW - timedelta(days=1)]
        assert [item.timestamp for item in plan.delete] == [self.NOW - timedelta(days=2), self.NOW - timedelta(days=3)]

    def test_all_rules_zero_deletes_nothing(self) -> None:
        from trs_file_backup.retention import plan_retention

        backups = [backup("r.txt", self.NOW - timedelta(days=offset)) for offset in range(5)]

        plan = plan_retention(backups, RetentionRules(), self.NOW)

        assert plan.delete == []
        assert len(plan.keep) == 5

    def test_always_keep_keeps_that_backup_against_the_rules(self) -> None:
        from trs_file_backup.retention import plan_retention

        just_made = backup("r.txt", self.NOW)
        future = backup("r.txt", self.NOW + timedelta(days=400))
        older = backup("r.txt", self.NOW - timedelta(days=3))

        plan = plan_retention([older, just_made, future], RetentionRules(days=1), self.NOW, always_keep=just_made.name)

        assert plan.keep == [future, just_made]
        assert plan.delete == [older]

    def test_no_backups_gives_an_empty_plan(self) -> None:
        from trs_file_backup.retention import plan_retention

        plan = plan_retention([], RetentionRules(days=1), self.NOW)

        assert plan.keep == []
        assert plan.delete == []
