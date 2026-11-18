# File Backup Feature Specification

## Overview

The trs-file-backup monitors a source directory and creates timestamped backup copies of modified files to a destination directory.

**Implementation Language:** Python; the minimum version is set by `requires-python` in `pyproject.toml`

The tool shall be implemented as a Python command-line application with comprehensive help functionality.

## Functional Requirements

### FR-1: Source Directory Monitoring

**ID:** FR-1
**Title:** Monitor source directory for modified files
**Description:** The system shall identify all files in a source directory that have been modified since the last backup operation.

**Acceptance Criteria:**

- AC-1.1: The system shall accept a source directory path as input
- AC-1.2: The system shall monitor only files in the top-level directory (no subdirectories)
- AC-1.3: The system shall ignore all subdirectories and their contents
- AC-1.4: The system shall compare file modification timestamps against the last backup timestamp
- AC-1.5: The system shall handle invalid or non-existent source directories with clear error messages

### FR-2: File Backup Creation

**ID:** FR-2
**Title:** Create timestamped backup copies
**Description:** The system shall copy modified files to a destination directory with timestamps in the filename.

**Acceptance Criteria:**

- AC-2.1: The system shall copy each modified file to the destination directory
- AC-2.2: The destination filename shall follow the pattern `{stem}_YYYY_MM_DD__HH_MM_SS{suffix}`, with the time the backup is made in local time.
  `{stem}` and `{suffix}` are the parts `Path.stem` and `Path.suffix` of `pathlib` give for the original file name:
  `{suffix}` is the last dot and what follows it, and it is empty for a name without a dot or a hidden name such as `.profile`.
  For a name that ends with a dot, Python 3.13 gives an empty suffix and later versions give the suffix `.` (KL-2)
- AC-2.3: Example: `report.txt` → `report_2026_01_13__14_30_22.txt`
- AC-2.4: The timestamp shall use 24-hour format (HH: 00-23)
- AC-2.5: All backup files shall be stored flat in the destination directory (no subdirectories)
- AC-2.6: If the destination directory does not exist, it shall be created automatically
- AC-2.7: `run` shall copy the modified files without waiting between or before the copies;
  the debounce delay applies only to `watch` (AC-5.4, AC-5.5), and `run --debounce` only saves it (AC-3.8)
- AC-2.8: The system shall copy the data to a temporary file `.trs-file-backup-<12 random hexadecimal digits>.tmp` in the destination directory
  and give it the backup name only when the data is complete.
  The temporary name has a fixed length of 33 characters, so a long backup name does not make it too long for the file system.
  If the data copy or the rename fails, the system shall remove the temporary file, also when it is read-only, and leave a file that already has the backup name unchanged.
  If only the metadata copy (times, permission bits) fails, the backup shall be kept without a message, because its data is complete.
  A temporary file left behind by a process that was killed during the copy stays in the destination directory

### FR-3: State Persistence

**ID:** FR-3
**Title:** Track last backup timestamp
**Description:** The system shall persist the timestamp of the last successful backup to determine which files have changed.

**Acceptance Criteria:**

- AC-3.1: The system shall store the last backup timestamp in a state file (`.backup_state.json`)
- AC-3.2: The state file shall be stored in the destination (backup) directory
- AC-3.3: The state file shall contain both source and destination directory paths
- AC-3.4: On first run (no state file exists), all files shall be backed up
- AC-3.5: The state file shall be updated after each successful backup operation.
  It shall store the modification time read before the copy, so a version written during the copy is backed up by the next run or debounce
- AC-3.6: The state file shall store the exclusion patterns, the debounce delay and the retention rules (the saved settings);
  `init` saves the values given to it, and `config` changes them (FR-7).
  AC-8.15 defines how the retention rules are saved and loaded
- AC-3.7: `run` and `watch` shall use the saved exclusion patterns when `--exclude` is not given, and the saved debounce delay when `--debounce` is not given
- AC-3.8: A given `--exclude` shall replace the saved user patterns (not be added to them), and a given `--debounce` shall replace the saved delay.
  The new values shall be saved in the state file, also when `run` finds no modified files.
  Only `run --dry-run` never writes the state file.
  `--debounce 0` is a given value.
- AC-3.9: Without a state file, `run` and `watch` shall use the defaults: no user patterns and a debounce delay of 2 seconds
- AC-3.10: The pattern `.backup_state.json` shall appear exactly once in the exclusion patterns that `init`, `run`, `watch` and `config` use and save;
  a pattern given twice shall be saved once
- AC-3.11: For every command, the directory given with `--destination` shall be the destination: the state file shall be read from and written to it,
  and backups shall go into it, also when the `destination_path` stored in the state file names another directory (a copied or moved backup folder).
  Every write of the state file shall store the given directory as `destination_path`.
- AC-3.12: When a state file exists and the `--source` given to `run` or `watch` is another directory than the saved `source_path`,
  the command shall stop before it backs up, writes the state file or the log, or starts watching: it shall print an error that names the saved source
  and says to use another backup folder or to run `init` again, and exit with code 1.
  Both paths are compared after they are made absolute and normalised; on Windows, a difference in letter case alone is not a different directory.
  Without a state file there is no check, and `init` always starts a new state.

### FR-4: Exclusion Patterns

**ID:** FR-4
**Title:** Exclude specific files and directories
**Description:** The system shall allow exclusion of certain files and directories from backup.

**Acceptance Criteria:**

- AC-4.1: The system shall exclude hidden files (starting with `.`)
- AC-4.2: The system shall exclude the state file itself from backup
- AC-4.3: Users shall be able to provide additional exclusion patterns via CLI parameter `--exclude`
- AC-4.4: Multiple exclusion patterns can be specified by repeating the `--exclude` parameter
- AC-4.5: Exclusion patterns shall support wildcards (e.g., `*.log`, `temp_*`)
- AC-4.6: Exclusion patterns shall be matched against the filename only (not paths)
- AC-4.7: All subdirectories are automatically excluded (only top-level files are processed)
- AC-4.8: AC-3.6 to AC-3.10 define how exclusion patterns are saved and which patterns `run` and `watch` use
- AC-4.9: `init`, `run` and `watch` shall use an `--exclude` value without leading and trailing whitespace, as `config` does (AC-7.6).
  A pattern that is empty or consists of whitespace only, contains a path separator (`/` or `\`), or is `.` or `..`
  can never match a bare file name (AC-4.6) and shall be rejected; every other pattern is accepted.
  `init`, `run` and `watch` shall reject it with a usage error that names `--exclude`, the pattern and the reason (exit code 2),
  before anything is written.
  Such a pattern in an existing state file, saved by an older version, shall be dropped silently when the state file is read,
  because it cannot be used as a file-name pattern.

### FR-5: Real-Time File System Monitoring

**ID:** FR-5
**Title:** Watch mode for continuous file monitoring
**Description:** The system shall provide a watch mode that continuously monitors the source directory
and automatically backs up files when they are modified, created or moved into it.

**Acceptance Criteria:**

- AC-5.1: The system shall provide a `watch` command that runs continuously
- AC-5.2: The system shall detect file modification, creation and move events in real-time using file system monitoring
- AC-5.3: The system shall trigger a backup automatically when a file is modified
- AC-5.4: The system shall wait for a file to be fully written before backing it up (debounce mechanism)
- AC-5.5: The system shall use the configured debounce delay, default 2 seconds (no backup if another event for the file arrives within that delay).
  AC-3.6 to AC-3.9 define which delay is used
- AC-5.6: The system shall handle files that are locked or being written by another process (skip with warning); AC-6.18 defines how a lock is recognised
- AC-5.7: The system shall log each backup operation with timestamp
- AC-5.8: The system shall continue running until explicitly stopped by the user (Ctrl+C)
- AC-5.9: The watch mode shall respect all exclusion patterns defined for the backup
- AC-5.10: A file created in the source directory, or moved or renamed into it, shall trigger a backup like a modified file (AC-5.3 to AC-5.9).
  For a move or rename, the new name decides; a file moved from the source directory into a subdirectory is ignored (AC-1.3).
  The console and the log name the kind of event: `File modified: <name>`, `File created: <name>` or `File moved: <name>`
- AC-5.11: If the state file cannot be saved after a successful backup, the console and the log shall show the error `Cannot save state file: <reason>`.
  The backup still counts and is logged as backed up, and the watch mode continues

### FR-6: Activity Logging

**ID:** FR-6
**Title:** Log all script activities to a log file
**Description:** The system shall document all activities, operations, and errors in a log file stored in the destination directory.

**Acceptance Criteria:**

- AC-6.1: The system shall create a log file named `backup.log` in the destination directory
- AC-6.2: The log file shall be created during `init` command
- AC-6.3: If the log file does not exist during `run` or `watch` command, it shall be created automatically
- AC-6.4: Each log entry shall include timestamp in format `YYYY-MM-DD HH:MM:SS`
- AC-6.5: Each log entry shall include a log level: `INFO`, `WARNING`, or `ERROR`
- AC-6.6: Log entry format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`
- AC-6.7: The system shall log successful backup operations with level `INFO`
- AC-6.8: The system shall log warnings (e.g., file skipped, locked file as AC-6.18 defines it) with level `WARNING`
- AC-6.9: The system shall log errors (e.g., no access, permission denied, copy failed as AC-6.18 defines them) with level `ERROR`
- AC-6.10: The log file shall be a plain text file with UTF-8 encoding
- AC-6.11: Log entries shall be appended to the existing log file (not overwritten)
- AC-6.12: All script interruptions and exceptions shall be logged with appropriate level
- AC-6.13: Each session shall start with a session header logging source path, destination path,
  and the exclusion patterns and debounce delay the session actually uses (after AC-3.7 to AC-3.10 are applied).
  The last line of the header shall list the four retention rules (AC-8.1) in this form, also when they are 0: `Retention rules: hours 24, days 7, weeks 4, months -1`
- AC-6.14: Each session shall end with a session summary logging completion status and statistics
- AC-6.15: During a session, settings (paths, excludes, retention rules) shall not be logged repeatedly
- AC-6.16: All excluded files encountered during a `watch` session shall be logged with level `WARNING`; `run` logs no excluded files
- AC-6.17: The log entry for an excluded file (AC-6.16) shall give the reason: `File excluded: <name> (hidden file)` for a hidden file (AC-4.1),
  also for the state file, and `File excluded: <name> (matches: <pattern>)` with the first exclusion pattern that matches the name
- AC-6.18: When `run` or `watch` cannot back up a file because of an operating system error, the console and the log shall name the cause,
  and the system shall continue with the next file:
  - Locked file: Windows error 32 (sharing violation) or 33 (lock violation), `BlockingIOError`, or error number `EBUSY`.
    Level `WARNING`, message `File locked, skipping: <name>`.
    A locked file on Windows raises `PermissionError`, so the Windows error decides, not the error number `EACCES`
  - Missing permission: any other `PermissionError`. Level `ERROR`, message `Permission denied: <name>`
  - Any other error, e.g. disk full, path too long, or a file deleted between scan and copy:
    level `ERROR`, message `Backup failed: <name> (<reason>)`, where `<reason>` is the error text from the operating system, else the message of the error

**Log Level Usage:**

- **INFO**: Successful operations (session started, backup started, file backed up, old backup deleted (AC-8.13), operation completed, session ended)
- **WARNING**: Non-critical issues (file skipped due to exclusion, file locked as AC-6.18 defines it, file not initially backed up,
  backup locked and not deleted (AC-8.13))
- **ERROR**: Critical errors (permission denied and copy failed as AC-6.18 defines them, state file not saved in watch mode (AC-5.11),
  source directory not found,
  backup not deleted, destination not listed or rules not applied for retention (AC-8.13))

### FR-7: Show and Edit the Saved Settings

**ID:** FR-7
**Title:** Show and edit the saved settings on the console
**Description:** The system shall print the settings saved in the state file
and let the user change single settings in a menu or with one command,
without running `init` again.

**Acceptance Criteria:**

- AC-7.1: `config show --destination <path>` shall print the saved settings without asking anything:
  the source directory, the debounce delay, the user exclusion patterns numbered from 1, and the retention rules as AC-7.16 shows them.
  The pattern `.backup_state.json` is not listed, because it is always excluded (AC-3.10).
  An empty list of user patterns shall be printed as `(none)`.
- AC-7.2: `config --destination <path>` shall open a menu when standard input is a terminal; otherwise it shall behave like `config show`
- AC-7.3: The menu shall show the settings as in AC-7.1 and offer these actions:
  change the debounce delay, add a pattern, remove a pattern by its number, clear all user patterns, change a retention rule (AC-7.17),
  save and quit, quit without saving
- AC-7.4: The source directory shall be read-only, and the list of tracked files shall be neither shown nor changed
- AC-7.5: A new debounce delay shall be a whole number of 0 or more seconds; a negative number shall be rejected and asked for again
- AC-7.6: A new pattern shall be stored without leading and trailing whitespace.
  Adding a pattern that is already listed, or `.backup_state.json`, shall leave the list unchanged and say so;
  a pattern that AC-4.9 rejects shall be rejected with its reason, and the list stays unchanged.
- AC-7.7: Removing by a number that is not in the list shall print a message and leave the list unchanged; the menu continues, `config` does not exit
- AC-7.8: Clearing shall remove all user patterns; `.backup_state.json` stays excluded (AC-3.10)
- AC-7.9: After each change, the menu shall show the settings again and mark what differs from the state file:
  a changed delay, a new pattern, a removed pattern, a changed retention rule (AC-7.16)
- AC-7.10: Nothing shall be written before the user chooses "save".
  Save shall write the patterns, the delay and the retention rules through the atomic state file update (see Implementation Notes)
  and keep the source directory and the tracked files as the state file holds them at that moment.
- AC-7.11: Quitting with unsaved changes shall ask for confirmation.
  When the input ends before "save", nothing is saved; the exit code is 1 if changes were lost, else 0.
- AC-7.12: Without a state file in the destination directory, `config`, `config show` and `config set`
  shall print an error that says to run `init` first,
  exit with code 1, and create nothing.
  A state file that cannot be read shall also give an error and exit code 1; AC-8.16 defines the same for an invalid retention rule.
- AC-7.13: When `config` saves, in the menu or with `config set`, it shall write a session to `backup.log` as FR-6 describes:
  the session header with command `config` and the saved settings, one line that names the changes, and the session end.
  The line names a changed rule by its key, for example `Settings changed: retention.days 7 -> 9`.
  `config show`, and quitting without saving, shall not write to `backup.log`.
  When the state file was saved but `backup.log` cannot be written, the settings shall stay saved;
  `config` shall print an error that says the settings were saved and names `backup.log`, and exit with code 1.
- AC-7.14: Saved changes take effect at the next start of `run`, `watch` or `cleanup` (AC-3.7).
  `run` and `watch` read the state file at their start and keep the settings in memory, the retention rules included;
  `watch` writes them back after each backup and `run` at its end, which overwrites a change that `config` saved meanwhile.
  Stop a running `watch` and wait for a running `run` to finish before using `config`.
- AC-7.15: The text that `config` prints, apart from paths and patterns, shall use ASCII characters only
- AC-7.16: The retention rules shall be shown as a block that starts with `  Retention: `; further lines are indented by 13 spaces, as the patterns are.
  The block lists each rule that is not 0, in the order hours, days, weeks, months, with these texts:

  | Rule | Value N greater than 0 | Value -1 |
  | --- | --- | --- |
  | `retention.hours` | `keep all backups of the last N hours` | `keep all backups` |
  | `retention.days` | `keep the last backup per day for N days` | `keep the last backup per day forever` |
  | `retention.weeks` | `keep the last backup per week for N weeks` | `keep the last backup per week forever` |
  | `retention.months` | `keep the last backup per month for N months` | `keep the last backup per month forever` |

  For N = 1 the unit is singular (`1 hour`, `1 day`, `1 week`, `1 month`).
  When all four rules are 0, the block is the single line `  Retention: off (no backup is ever deleted)`.
  In the menu, a rule that differs from the state file gets the mark `   (changed)` at the end of its line.
  A rule that is 0 in the menu but not in the state file is listed as `hours rule: off   (changed)` (or `days`, `weeks`, `months`),
  unless all four are 0: then the single line `off` gets the mark.
- AC-7.17: The menu action `[5] change retention` shall first ask which rule to change, with the line
  `  [1] hours   [2] days   [3] weeks   [4] months` and the prompt `Choose [1/2/3/4]`.
  It shall then ask for the new value, with the current value of the menu as default (Enter keeps it):

  | Rule | Prompt |
  | --- | --- |
  | `retention.hours` | `Keep every backup younger than how many hours (0 = off, -1 = no limit)` |
  | `retention.days` | `Keep the last backup per day for how many days (0 = off, -1 = no limit)` |
  | `retention.weeks` | `Keep the last backup per week for how many weeks (0 = off, -1 = no limit)` |
  | `retention.months` | `Keep the last backup per month for how many months (0 = off, -1 = no limit)` |

  A choice that is not offered, or a value that is not a whole number, shall be asked for again.
  A whole number below -1 shall be rejected with `The value must be 0 or more, or -1 (no limit).` and asked for again.
  The menu then continues as after any other change (AC-7.9).
- AC-7.18: `config show KEY --destination <path>` shall print only the saved value of one setting, as a whole number on one line, for example `12`.
  The keys are `debounce` (seconds), `retention.hours`, `retention.days`, `retention.weeks` and `retention.months`, written exactly so.
  The exclusion patterns have no key: they are a list and are changed in the menu or with `--exclude`.
  An unknown key shall end the command with an error that names the valid keys, and exit code 1.
- AC-7.19: `config set KEY VALUE --destination <path>` shall change one setting (keys as in AC-7.18) and save it at once, without a menu.
  VALUE is a whole number of ASCII digits with an optional leading minus sign; a negative value needs no `--` before it.
  It shall be checked as the menu checks it: `debounce` as AC-7.5 allows, a retention rule as AC-8.2 allows.
  An unknown key, or a value that is not valid for the key, shall end the command with exit code 1 and an error that names the valid keys or values; nothing is written.
  A valid value shall be saved as AC-7.10 describes for "save", and logged as AC-7.13 describes.
  `config set` shall then print the note of AC-7.14 and `Saved <KEY> = <VALUE> to <state file>. The change takes effect at the next start of 'run', 'watch' or 'cleanup'.`
  When the value is already saved, `config set` shall print `<KEY> is already <VALUE>; nothing was written.`, write nothing, and exit with code 0

### FR-8: Backup Retention

**ID:** FR-8
**Title:** Thin out old backups by saved retention rules
**Description:** The system shall delete old backups of each original file by four saved rules:
recent backups stay complete, older ones are kept only per day, week or month.
The rules follow the model of `borg prune` and `restic forget`: count periods, keep the newest backup in each period.

| Setting key | The rule keeps |
| --- | --- |
| `retention.hours` | every backup younger than N hours |
| `retention.days` | the newest backup of each of the last N days that have a backup |
| `retention.weeks` | the newest backup of each of the last N weeks that have a backup |
| `retention.months` | the newest backup of each of the last N months that have a backup |

**Acceptance Criteria:**

- AC-8.1: The system shall support the four retention rules in the table above, each a whole number.
  A backup shall be kept when at least one rule keeps it, and is deleted when no rule keeps it, except when all rules are 0 (AC-8.3).
  The newest backup of each original file shall always be kept, whatever the rules say.
  In `run` and `watch`, the backup just made is kept as well (AC-8.9).
- AC-8.2: The value 0 shall turn a rule off.
  The value -1 shall mean no limit: `retention.days`, `retention.weeks` and `retention.months` keep the newest backup of every period,
  and `retention.hours` keeps every backup.
  A value below -1 is invalid; AC-7.17 and AC-7.19 reject it when it is entered, and AC-8.16 defines what happens when it is stored.
- AC-8.3: When all four rules are 0 (the default), no backup shall be deleted.
  `run` and `watch` then do not list the destination directory for retention, and `cleanup` does what AC-8.14 says for this case.
- AC-8.4: The time of a backup shall be read from its name (AC-2.2), as local time; the modification time of the file is not used (KL-4).
  "Now" is the time of the system clock when the rules are applied to the backups of one original file.
  `retention.hours` keeps a backup when now minus its time is less than N hours.
  A backup whose time lies after now (the clock was changed) counts as younger than N hours for any N greater than 0, and is not kept by the value 0.
- AC-8.5: A day shall be a calendar date,
  a week an ISO week (Monday to Sunday, identified by ISO year and week number, so a week across New Year is one week),
  and a month a calendar month of a year.
  For each period rule, the periods that hold at least one backup of the original file are counted, newest period first;
  periods without a backup are not counted, so a file left unchanged for months keeps its last states.
  The rule keeps the newest backup in each of the first N counted periods.
  A backup whose time lies after now counts in its period like any other backup.
- AC-8.6: Only a regular file in the destination directory shall be a backup candidate; directories and symbolic links are not.
  Its name is a backup of the original file name O at time T when the backup name of O at T (AC-2.2) is exactly this name.
  T must be a valid date and time written with ASCII digits as in AC-2.2; O must not be empty and must not start with a dot,
  because a hidden file is never backed up (AC-4.1).
  When two readings give the name back, the reading whose original name does not end with a dot shall be used (KL-2).
- AC-8.7: Backups shall be grouped by their original file name, compared case-sensitively:
  backups of `Report.txt` and of `report.txt` are two groups, and each group keeps its newest backup (AC-8.1, KL-3)
- AC-8.8: A file that is not a backup by AC-8.6 shall never be deleted, for example the state file, `backup.log`, a temporary file (AC-2.8) or a foreign file
- AC-8.9: In `run` and `watch`, the rules shall be applied to the group of a source file
  after its backup is complete (renamed from the temporary file, AC-2.8),
  the state records the backup (AC-3.5), and `watch` has updated its pending files for this backup.
  This holds also when the state file could not be saved (AC-5.11), because the backup still counts.
  Deleting before the copy would leave one backup fewer than the rules promise if the copy failed.
  After a failed or skipped backup, the rules are not applied for that file.
  The backup just made shall never be deleted, whatever the rules and the times in the names say,
  because it holds the current state of the file: a backup whose time lies after now (AC-8.4) or one from the repeated hour of a clock change (KL-4)
  can sort as newer and would otherwise leave it unkept.
  So retention in `run` and `watch` may keep one backup more than AC-8.1 says, never one fewer.
- AC-8.10: `run` shall list the destination directory at most once and add each new backup to that list itself.
  When that listing fails, `run` shall report it once and delete nothing more in this run.
  `watch` shall list the destination directory each time it applies the rules.
- AC-8.11: Retention shall run in its own error guard:
  a failed listing, a failed deletion or any other error while the rules are applied is reported (AC-8.13);
  it never fails the backup, never changes the count of backed up files or the exit code of `run`, and never ends `watch`
- AC-8.12: `run --dry-run` shall delete nothing and list nothing for retention; `cleanup --dry-run` shows what the rules would delete (AC-8.14)
- AC-8.13: When a deletion fails for missing permission (AC-6.18) and the backup is read-only,
  the system shall clear its read-only bit and try the deletion once more.
  When that try still fails, the system shall set the read-only bit again;
  a failure to set it again is not reported separately, because the failed deletion is already reported.
  A backup that is already gone is no error and is not reported, and it counts as deleted, because the goal is reached.
  The console and the log shall report:
  - Each deleted backup: level `INFO`, message `Deleted old backup: <name>`
  - A backup that cannot be deleted because it is locked, as AC-6.18 recognises a lock: level `WARNING`, message `Backup locked, not deleted: <name>`
  - A backup that cannot be deleted for any other cause: level `ERROR`, message `Cannot delete backup: <name> (<reason>)`, with `<reason>` as in AC-6.18
  - A failed listing of the destination directory: level `ERROR`, message `Cannot list backups in <destination>: <reason>`
  - Any other error while the rules are applied to the backups of the original file `<original>`: level `ERROR`, message `Retention failed for <original>: <reason>`

  A backup that cannot be deleted is skipped; the system continues with the next one.
- AC-8.14: `cleanup --destination <path> [--dry-run]` shall apply the saved rules to every group of backups in the destination directory.
  - It takes no rule options and lists the destination directory once.
  - Without a state file, or with a state file that cannot be read,
    it shall end as AC-7.12 describes for `config` (exit code 1, nothing created),
    so it never thins out a folder that trs-file-backup does not manage.
  - When all rules are 0, it shall print `Retention is off: no rule is set, so no backup is deleted.`, write nothing, and exit with code 0.
  - `--dry-run` shall delete nothing, write nothing to `backup.log`,
    and list per original file which backups are kept and which would be deleted,
    as the `cleanup` command section shows: original files sorted by name, case-sensitively, and backups newest first.
  - A run without `--dry-run` shall print each deletion or failure (AC-8.13) and the summary `Deleted <deleted> of <to delete> old backups`,
    as the `cleanup` command section shows.
    `<deleted>` counts as AC-8.13 defines.
    It shall write one session to `backup.log` (FR-6) with command `cleanup`, the same lines,
    and the summary `Session summary: <deleted> of <to delete> old backups deleted`.
  - It shall exit with code 1 when the listing or at least one deletion failed, else 0.
  - It shall not write the state file.
- AC-8.15: The rules shall be saved in the state file as the object `retention` with the integer keys `hours`, `days`, `weeks` and `months`.
  `init` saves all four as 0.
  A state file without `retention`, or without one of its keys, shall load the missing rules as 0, so existing setups delete nothing.
  No command takes the rules as command-line options: they are changed with `config` only (FR-7).
  `run` and `watch` write the rules back as they read them, and a running `watch` keeps the rules it started with (AC-7.14).
- AC-8.16: A stored rule that is not a JSON integer (for example `true`, `1.5`, `"7"` or `null`), or that AC-8.2 does not allow, is invalid;
  so is a `retention` value that is not an object, and a key inside `retention` other than the four of AC-8.15 (for example `hourz`),
  so a typing error fails loudly instead of being ignored.
  `run`, `watch`, `cleanup`, `config`, `config show` and `config set` shall then stop
  before they back up, delete, or write the state file or the log:
  they print an error that names the state file, the key, the value and the allowed values (0 or more, or -1), and exit with code 1.
  The rule must be corrected in the state file, or a new state started with `init`

## Non-Functional Requirements

### NFR-1: Performance

- The system shall handle directories with up to 10,000 files efficiently (< 30 seconds)
- File copying shall provide progress indication for large files (> 10 MB)

### NFR-2: Error Handling

- All file system errors shall be logged with clear error messages
- Permission errors shall not stop the entire backup process
- A summary report shall be provided after each backup run

### NFR-3: Usability

- The CLI interface shall provide clear help messages
- Installing the package shall install exactly one command, `trs-file-backup`; the former alias `bcs` was removed in 4.0.0
- Progress shall be visible during backup operations
- The system shall report the number of files backed up successfully
- The tool shall provide a `--help` / `-h` option for the main command and all subcommands
- Help messages shall include command descriptions, parameter explanations, and usage examples
- Users shall be able to use the tool without reading external documentation
- The console output of all commands shall use ASCII markers (`OK`, `ERROR`, `WARNING`, `->`), so it stays readable on any console code page
- A character in a path that the console encoding cannot show shall be printed as `?`; it shall not end the command, also when the output goes into a pipe or a file
- File names, paths and error messages shall appear on the console exactly as they are: text such as `[red]` or `:fire:` in a name is printed, not read as formatting or emoji code

### NFR-4: Help System

**ID:** NFR-4
**Title:** Comprehensive command-line help
**Description:** The system shall provide built-in help functionality that allows users to understand and use all features without external documentation.

**Requirements:**

- The main command shall display overview help listing all available commands
- Each subcommand shall have detailed help including:
  - Command purpose and description
  - Required and optional parameters with explanations
  - Usage examples
  - Common use cases
- Help text shall be accessible via `--help` or `-h`; `trs-file-backup` without a command shall show the main help.
  A command without its required options shall print a usage error that names the missing option and points to the help option `-h` (exit code 2).
- Error messages shall suggest relevant help commands when parameters are missing or invalid

## CLI Interface Specification

### Main Command Help

**Syntax:**

```bash
trs-file-backup --help
# or
trs-file-backup -h
# or
trs-file-backup
```

**Output:**

```text
Usage: trs-file-backup [OPTIONS] COMMAND [ARGS]...

  trs-file-backup - Monitor and backup modified files with timestamps

  This tool helps you create timestamped backups of modified files from a
  source directory to a destination directory. It supports one-time backups,
  initialization, and continuous monitoring.

Options:
  --version, -v  Show version and exit
  --help, -h     Show this message and exit

Commands:
  run     Execute a one-time backup of modified files
  init    Initialize backup tracking for a directory
  watch   Continuously monitor and backup files in real-time
  config  Show and edit the saved settings (debounce delay, exclusion patterns and retention rules)
  cleanup Delete old backups by the saved retention rules

Use 'trs-file-backup COMMAND --help' for more information on a specific command.

Examples:
  trs-file-backup run --source ./myproject --destination ./backup
  trs-file-backup watch --source ./myproject --destination ./backup
```

### Command: `run`

**Purpose:** Execute a backup operation

**Syntax:**

```bash
trs-file-backup run --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>] [--dry-run]
# Help
trs-file-backup run --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times).
  It replaces the saved patterns; without it, the saved patterns are used (AC-3.7, AC-3.8)
- `--debounce`: Debounce delay in seconds that `watch` uses (optional); `run` itself copies without waiting (AC-2.7).
  It replaces the saved value; without it, the saved value is used, or 2 if none is saved (AC-3.7 to AC-3.9)
- `--dry-run`: Show what would be backed up without actually copying files (optional); it deletes no old backup (AC-8.12)

After each backup, `run` applies the saved retention rules to the backups of that file (AC-8.9).

**Help Output:**

```bash
Usage: trs-file-backup run [OPTIONS]

  Execute a one-time backup of modified files

  This command scans the source directory for files that have been modified
  since the last backup and creates timestamped copies in the destination
  directory. Only files changed after the last backup run are processed.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated).
                          Replaces the saved patterns; if not given, the saved
                          patterns are used
  --debounce INTEGER      Seconds to wait in watch mode; run itself copies
                          without waiting. Replaces the saved value; if not
                          given, the saved value is used
                          [default: (saved value, else 2)]
  --dry-run              Show what would be backed up without copying
  --help, -h             Show this message and exit

Examples:
  # Basic backup
  trs-file-backup run --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Exclude log files
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log"

  # Multiple exclusions; save a debounce delay of 5 seconds for watch
  trs-file-backup run --source ./src --destination ./backup --exclude "*.log" --exclude "temp_*" --debounce 5

  # Preview without copying
  trs-file-backup run --source ./src --destination ./backup --dry-run
```

**Command Output:**

```text
Scanning source directory: C:\Projects\MyApp
Found 4 modified files
Backing up files...
  OK main.py -> main_2026_01_13__14_30_21.py
  Deleted old backup: main_2026_01_12__09_10_00.py
  OK readme.md -> readme_2026_01_13__14_30_21.md
  OK config.yaml -> config_2026_01_13__14_30_21.yaml
  WARNING File locked, skipping: database.db

Successfully backed up 3 files to C:\Backup\MyApp
Failed: 1 files
Logging to: C:\Backup\MyApp\backup.log
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:30:20] [INFO] ========== Session Started ==========
[2026-01-13 14:30:20] [INFO] Command: run
[2026-01-13 14:30:20] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:30:20] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:30:20] [INFO] Exclusion patterns: .backup_state.json, *.log, temp_*
[2026-01-13 14:30:20] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:30:20] [INFO] Retention rules: hours 24, days 7, weeks 4, months -1
[2026-01-13 14:30:20] [INFO] Found 4 modified files
[2026-01-13 14:30:21] [INFO] Backed up: main.py → main_2026_01_13__14_30_21.py
[2026-01-13 14:30:21] [INFO] Deleted old backup: main_2026_01_12__09_10_00.py
[2026-01-13 14:30:21] [INFO] Backed up: readme.md → readme_2026_01_13__14_30_21.md
[2026-01-13 14:30:21] [INFO] Backed up: config.yaml → config_2026_01_13__14_30_21.yaml
[2026-01-13 14:30:21] [WARNING] File locked, skipping: database.db
[2026-01-13 14:30:21] [INFO] Backup operation completed: 3 of 4 files backed up
[2026-01-13 14:30:21] [INFO] Session summary: 3 of 4 files backed up
[2026-01-13 14:30:21] [INFO] ========== Session Ended ==========
```

In this example, the destination also holds `main_2026_01_12__17_45_03.py`.
`main_2026_01_12__09_10_00.py` is older than 24 hours and is not the newest backup of its day, week or month, so no rule keeps it.

### Command: `init`

**Purpose:** Initialize backup tracking for a directory

**Syntax:**

```bash
trs-file-backup init --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>]
# Help
trs-file-backup init --help
```

**Parameters:**

- `--source`: Path to the source directory (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times)
- `--debounce`: Seconds that `watch` waits before a backup; `run` copies without waiting, see AC-2.7 (optional, default: 2)

**Help Output:**

```bash
Usage: trs-file-backup init [OPTIONS]

  Initialize backup tracking for a directory

  This command sets up backup tracking by creating a state file in the
  destination directory. The next 'run' or 'watch' command will back up all files (first
  full backup). Subsequent runs will only backup modified files.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated)
  --debounce INTEGER      Seconds to wait in watch mode; run copies without
                          waiting  [default: 2]
  --help, -h             Show this message and exit

Examples:
  # Basic initialization
  trs-file-backup init --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Initialize with exclusions and custom debounce
  trs-file-backup init --source ./src --destination ./backup --exclude "*.log" --exclude "*.tmp" --debounce 5

Note:
  Exclusion patterns and debounce setting specified here are saved.
  Later 'run' and 'watch' commands use them, unless they are given --exclude or --debounce, which replaces the saved value.
  The retention rules are saved as 0 (off); change them with 'config'.
```

**Command Output:**

```text
OK Initialized backup tracking for C:\Projects\MyApp
State file saved to C:\Backup\MyApp\.backup_state.json
Log file created: C:\Backup\MyApp\backup.log
Next run will back up all files.
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:25:10] [INFO] ========== Session Started ==========
[2026-01-13 14:25:10] [INFO] Command: init
[2026-01-13 14:25:10] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:25:10] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:25:10] [INFO] Exclusion patterns: .backup_state.json, *.log, *.tmp
[2026-01-13 14:25:10] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:25:10] [INFO] Retention rules: hours 0, days 0, weeks 0, months 0
[2026-01-13 14:25:10] [INFO] State file created: .backup_state.json
[2026-01-13 14:25:10] [INFO] Backup tracking initialized successfully
[2026-01-13 14:25:10] [INFO] ========== Session Ended ==========
```

### Command: `watch`

**Purpose:** Continuously monitor source directory and backup files automatically when modified, created or moved into it (AC-5.10)

**Syntax:**

```bash
trs-file-backup watch --source <path> --destination <path> [--exclude <pattern>] [--debounce <seconds>]
# Help
trs-file-backup watch --help
```

**Parameters:**

- `--source`: Path to the source directory to monitor (required)
- `--destination`: Path to the destination backup directory (required)
- `--exclude`: File-name pattern to exclude, see AC-4.6 and AC-4.9 (optional, can be specified multiple times).
  It replaces the saved patterns; without it, the saved patterns are used (AC-3.7, AC-3.8)
- `--debounce`: Seconds to wait after a file is modified, created or moved in, before backup (optional).
  It replaces the saved value; without it, the saved value is used, or 2 if none is saved (AC-3.7 to AC-3.9)

After each backup, `watch` applies the retention rules it started with to the backups of that file (AC-8.9).

**Help Output:**

```bash
Usage: trs-file-backup watch [OPTIONS]

  Continuously monitor and backup files in real-time

  This command starts a file system monitor that watches the source directory
  for changes. When a file is modified, created or moved into it, it
  automatically creates a timestamped backup after a short delay (debounce).
  The monitor runs until you press Ctrl+C.

Options:
  --source PATH           Source directory to monitor [required]
  --destination PATH      Destination backup directory [required]
  --exclude PATTERN       File-name patterns to exclude (can be repeated).
                          Replaces the saved patterns; if not given, the saved
                          patterns are used
  --debounce INTEGER      Seconds to wait after a file is modified, created
                          or moved in, before backup. Replaces the saved
                          value; if not given, the saved value is used
                          [default: (saved value, else 2)]
  --help, -h             Show this message and exit

Examples:
  # Basic watch mode
  trs-file-backup watch --source C:\Projects\MyApp --destination C:\Backup\MyApp

  # Watch with exclusions
  trs-file-backup watch --source ./src --destination ./backup --exclude "*.log"

  # Custom debounce delay (5 seconds)
  trs-file-backup watch --source ./src --destination ./backup --debounce 5

Tips:
  - Use Ctrl+C to stop monitoring
  - Debounce prevents backing up files that are still being written
  - Subdirectories are ignored; hidden files (starting with .) are excluded
```

**Command Output:**

```text
Starting file system monitor for C:\Projects\MyApp
Watching for changes... (Press Ctrl+C to stop)
Logging to: C:\Backup\MyApp\backup.log

[2026-01-13 14:32:15] File modified: main.py
[2026-01-13 14:32:17] Backing up: main.py -> main_2026_01_13__14_32_17.py OK

[2026-01-13 14:35:22] File modified: readme.md
[2026-01-13 14:35:24] Backing up: readme.md -> readme_2026_01_13__14_35_24.md OK

[2026-01-13 14:39:05] File created: notes.txt
[2026-01-13 14:39:07] Backing up: notes.txt -> notes_2026_01_13__14_39_07.txt OK

Ctrl+C detected. Stopping file system monitor...
```

**Log File Example (backup.log):**

```text
[2026-01-13 14:32:00] [INFO] ========== Session Started ==========
[2026-01-13 14:32:00] [INFO] Command: watch
[2026-01-13 14:32:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:32:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:32:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 14:32:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:32:00] [INFO] Retention rules: hours 0, days 0, weeks 0, months 0
[2026-01-13 14:32:00] [INFO] Watch mode started, monitoring for changes...
[2026-01-13 14:32:15] [INFO] File modified: main.py
[2026-01-13 14:32:17] [INFO] Backed up: main.py → main_2026_01_13__14_32_17.py
[2026-01-13 14:35:22] [INFO] File modified: readme.md
[2026-01-13 14:35:24] [INFO] Backed up: readme.md → readme_2026_01_13__14_35_24.md
[2026-01-13 14:38:10] [WARNING] File excluded: temp.log (matches: *.log)
[2026-01-13 14:39:05] [INFO] File created: notes.txt
[2026-01-13 14:39:07] [INFO] Backed up: notes.txt → notes_2026_01_13__14_39_07.txt
[2026-01-13 14:40:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 14:40:00] [INFO] Session summary: 3 of 3 files backed up
[2026-01-13 14:40:00] [INFO] ========== Session Ended ==========
```

### Command: `config`

**Purpose:** Show and edit the settings saved in the state file (FR-7)

**Syntax:**

```bash
trs-file-backup config --destination <path>
trs-file-backup config show [KEY] --destination <path>
trs-file-backup config set KEY VALUE --destination <path>
# Help
trs-file-backup config --help
trs-file-backup config show --help
trs-file-backup config set --help
```

**Parameters:**

- `--destination`: Path to the destination backup directory that holds the state file (required).
  It may stand before or after `show` and `set`.
- `KEY`: `debounce`, `retention.hours`, `retention.days`, `retention.weeks` or `retention.months` (AC-7.18)
- `VALUE`: A whole number that the key allows (AC-7.19)

**Help Output:**

```bash
Usage: trs-file-backup config [OPTIONS] COMMAND [ARGS]...

  Show and edit the saved settings (debounce delay, exclusion patterns and
  retention rules).

  Without a subcommand, this opens a menu to change the debounce delay, to add,
  remove or clear exclusion patterns and to change the retention rules.
  Nothing is written before you choose save.
  When input does not come from a terminal, it prints the settings like 'config show'.
  The source directory cannot be changed here.

Options:
  --destination PATH  Destination backup directory that holds the state file
  --help, -h          Show this message and exit

Commands:
  show  Print the saved settings, or only the value of one setting.
  set   Change one setting and save it at once.

Keys for 'show KEY' and 'set KEY VALUE':
  debounce          Seconds that watch waits before a backup (0 or more)
  retention.hours   Keep every backup younger than N hours
  retention.days    Keep the last backup per day for N days
  retention.weeks   Keep the last backup per week for N weeks
  retention.months  Keep the last backup per month for N months
  A retention rule is 0 (off), a positive number, or -1 (no limit).

Examples:
  # Open the menu
  trs-file-backup config --destination C:\Backup\MyApp

  # Print the saved settings only
  trs-file-backup config show --destination ./backup

  # Print one value, then change it
  trs-file-backup config show retention.days --destination ./backup
  trs-file-backup config set retention.days 12 --destination ./backup

  # Keep one backup per month forever
  trs-file-backup config set retention.months -1 --destination ./backup

Note:
  Stop a running 'watch' and wait for a running 'run' to finish first: both write their own
  settings back to the state file and would overwrite your changes.
  Saved changes take effect at the next start of 'run', 'watch' or 'cleanup'.
```

**Command Output (`config show`):**

```text
Saved settings
  Source:    C:\Projects\MyApp   (read-only)
  Debounce:  5 s
  Excluded:  1) *.log
             2) temp_*
  Retention: keep all backups of the last 24 hours
             keep the last backup per day for 7 days
             keep the last backup per week for 4 weeks
             keep the last backup per month forever
```

Without any rule, the retention block is the single line `  Retention: off (no backup is ever deleted)` (AC-7.16).

**Command Output (`config show retention.days`):**

```text
7
```

**Command Output (`config set retention.days 12`):**

```text
Stop a running 'watch' and wait for a running 'run' to finish first: both write their own settings back and would overwrite your changes.
Saved retention.days = 12 to C:\Backup\MyApp\.backup_state.json. The change takes effect at the next start of 'run', 'watch' or 'cleanup'.
```

**Menu (`config`), after the delay was set to 0 and pattern 2 was removed:**

```text
Saved settings
  Source:    C:\Projects\MyApp   (read-only)
  Debounce:  0 s   (changed)
  Excluded:  1) *.log
  Removed:   temp_*
  Retention: keep all backups of the last 24 hours
             keep the last backup per day for 7 days
             keep the last backup per week for 4 weeks
             keep the last backup per month forever
Unsaved changes: choose s to save them.

  [1] change debounce   [2] add pattern   [3] remove pattern
  [4] clear patterns    [5] change retention
  [s] save and quit     [q] quit without saving
Choose [1/2/3/4/5/s/q]: s
Saved to C:\Backup\MyApp\.backup_state.json. The changes take effect at the next start of 'run', 'watch' or 'cleanup'.
```

Before the first list, the menu prints the note to stop a running `watch` and wait for a running `run` to finish first.
A pattern added in the menu is marked `(new)`.

**Menu (`config`), changing a retention rule (AC-7.17):**

```text
Choose [1/2/3/4/5/s/q]: 5
  [1] hours   [2] days   [3] weeks   [4] months
Choose [1/2/3/4]: 2
Keep the last backup per day for how many days (0 = off, -1 = no limit) (7): 9
```

The menu then shows the settings again, with `keep the last backup per day for 9 days   (changed)` in the retention block.

**Log File Example (backup.log), after the save of the first menu example:**

```text
[2026-01-13 15:10:04] [INFO] ========== Session Started ==========
[2026-01-13 15:10:04] [INFO] Command: config
[2026-01-13 15:10:04] [INFO] Source: C:\Projects\MyApp
[2026-01-13 15:10:04] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 15:10:04] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 15:10:04] [INFO] Debounce delay: 0 seconds
[2026-01-13 15:10:04] [INFO] Retention rules: hours 24, days 7, weeks 4, months -1
[2026-01-13 15:10:04] [INFO] Settings changed: debounce delay 5 -> 0 seconds; removed pattern temp_*
[2026-01-13 15:10:04] [INFO] ========== Session Ended ==========
```

### Command: `cleanup`

**Purpose:** Delete old backups by the saved retention rules (AC-8.14)

**Syntax:**

```bash
trs-file-backup cleanup --destination <path> [--dry-run]
# Help
trs-file-backup cleanup --help
```

**Parameters:**

- `--destination`: Path to the destination backup directory that holds the state file (required)
- `--dry-run`: Show per original file which backups are kept and which would be deleted, without deleting (optional)

**Help Output:**

```bash
Usage: trs-file-backup cleanup [OPTIONS]

  Delete old backups by the saved retention rules

  This command applies the retention rules saved in the state file to the
  backups of every original file in the destination directory. Only files
  whose name is a backup name can be deleted, and the newest backup of each
  original file is always kept. Change the rules with 'config'.

Options:
  --destination PATH  Destination backup directory that holds the state file
                      [required]
  --dry-run           Show what would be kept and deleted, without deleting
  --help, -h          Show this message and exit

Examples:
  # Preview what the saved rules would delete
  trs-file-backup cleanup --destination ./backup --dry-run

  # Delete the old backups
  trs-file-backup cleanup --destination ./backup

  # Try another rule: change it, then preview
  trs-file-backup config set retention.days 14 --destination ./backup
  trs-file-backup cleanup --destination ./backup --dry-run
```

**Command Output (`cleanup --dry-run`):**

```text
Dry run: nothing is deleted.
main.py
  keep    main_2026_01_13__14_30_21.py
  keep    main_2026_01_12__17_45_03.py
  delete  main_2026_01_12__09_10_00.py
readme.md
  keep    readme_2026_01_13__14_30_21.md
  keep    readme_2026_01_02__17_00_00.md
  delete  readme_2026_01_02__08_00_00.md

Would delete 2 of 6 backups
```

**Command Output (`cleanup`):**

```text
Applying retention rules to C:\Backup\MyApp
  Deleted old backup: main_2026_01_12__09_10_00.py
  WARNING Backup locked, not deleted: readme_2026_01_02__08_00_00.md

Deleted 1 of 2 old backups
Logging to: C:\Backup\MyApp\backup.log
```

This run deletes what the dry run above predicts, but `readme_2026_01_02__08_00_00.md` is locked by another program.
The run exits with code 1, because one deletion failed (AC-8.14).

**Log File Example (backup.log), for this run:**

```text
[2026-01-13 15:20:00] [INFO] ========== Session Started ==========
[2026-01-13 15:20:00] [INFO] Command: cleanup
[2026-01-13 15:20:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 15:20:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 15:20:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 15:20:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 15:20:00] [INFO] Retention rules: hours 24, days 7, weeks 4, months -1
[2026-01-13 15:20:00] [INFO] Deleted old backup: main_2026_01_12__09_10_00.py
[2026-01-13 15:20:00] [WARNING] Backup locked, not deleted: readme_2026_01_02__08_00_00.md
[2026-01-13 15:20:00] [INFO] Session summary: 1 of 2 old backups deleted
[2026-01-13 15:20:00] [INFO] ========== Session Ended ==========
```

## Data Structures

### State File Format (`.backup_state.json`)

```json
{
  "source_path": "C:\\Projects\\MyApp",
  "destination_path": "C:\\Backup\\MyApp",
  "log_file": "backup.log",
  "debounce_seconds": 2,
  "excluded_patterns": [
    ".backup_state.json",
    "*.log",
    "temp_*"
  ],
  "retention": {
    "hours": 24,
    "days": 7,
    "weeks": 4,
    "months": -1
  },
  "files": {
    "main.py": 1736772622.5,
    "readme.md": 1736772625.8,
    "config.yaml": 1736772626.3
  }
}
```

**Notes:**

- The state file is stored in the destination (backup) directory
- On Windows, an antivirus or the indexer may hold the new file for a moment, so the final rename is tried up to 5 times, 0.1 seconds apart, before the save fails
- `source_path`: The source directory being monitored; AC-3.12 defines what happens when `run` or `watch` gets another one
- `destination_path`: The destination backup directory; AC-3.11 defines which directory counts when the folder was copied or moved
- `log_file`: Name of the log file (always `backup.log`)
- `debounce_seconds`: Debounce delay in seconds that `watch` waits before a backup (default: 2); `run` does not wait (AC-2.7)
- `excluded_patterns`: `.backup_state.json`, followed by the user-specified exclusion patterns for filenames
- The user-specified patterns are the ones last given with `--exclude` or saved by `config`; AC-3.6 to AC-3.10 and FR-7 define when they are saved and used
- Patterns support wildcards: `*` (any characters), `?` (single character)
- Subdirectories are always excluded automatically
- `retention`: The four retention rules (FR-8); AC-8.15 defines how they are saved and loaded, AC-8.16 what an invalid rule does

### Log File Format (`backup.log`)

Plain text file with UTF-8 encoding, one log entry per line.

**Format:** `[YYYY-MM-DD HH:MM:SS] [LEVEL] message`

**Session Structure:**

Each execution of `init`, `run`, `watch` or `cleanup`, and each save in the `config` menu or with `config set`, creates a session;
`config show`, quitting `config` without saving, a `config set` that changes nothing (AC-7.13, AC-7.19),
`cleanup --dry-run` and a `cleanup` without any rule (AC-8.14) write nothing.
A session has:

1. Session header with configuration
2. Operation log entries
3. Session footer with summary

**Example multi-session log:**

```text
[2026-01-13 10:00:00] [INFO] ========== Session Started ==========
[2026-01-13 10:00:00] [INFO] Command: init
[2026-01-13 10:00:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 10:00:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 10:00:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 10:00:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 10:00:00] [INFO] Retention rules: hours 0, days 0, weeks 0, months 0
[2026-01-13 10:00:00] [INFO] Backup tracking initialized successfully
[2026-01-13 10:00:00] [INFO] ========== Session Ended ==========

[2026-01-13 14:30:20] [INFO] ========== Session Started ==========
[2026-01-13 14:30:20] [INFO] Command: run
[2026-01-13 14:30:20] [INFO] Source: C:\Projects\MyApp
[2026-01-13 14:30:20] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 14:30:20] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 14:30:20] [INFO] Debounce delay: 2 seconds
[2026-01-13 14:30:20] [INFO] Retention rules: hours 0, days 0, weeks 0, months 0
[2026-01-13 14:30:20] [INFO] Found 3 modified files
[2026-01-13 14:30:22] [INFO] Backed up: main.py → main_2026_01_13__14_30_22.py
[2026-01-13 14:30:26] [ERROR] Permission denied: secure.dat
[2026-01-13 14:30:28] [INFO] Backed up: readme.md → readme_2026_01_13__14_30_28.md
[2026-01-13 14:30:30] [INFO] Backup operation completed: 2 of 3 files backed up
[2026-01-13 14:30:30] [INFO] Session summary: 2 of 3 files backed up
[2026-01-13 14:30:30] [INFO] ========== Session Ended ==========

[2026-01-13 16:00:00] [INFO] ========== Session Started ==========
[2026-01-13 16:00:00] [INFO] Command: watch
[2026-01-13 16:00:00] [INFO] Source: C:\Projects\MyApp
[2026-01-13 16:00:00] [INFO] Destination: C:\Backup\MyApp
[2026-01-13 16:00:00] [INFO] Exclusion patterns: .backup_state.json, *.log
[2026-01-13 16:00:00] [INFO] Debounce delay: 2 seconds
[2026-01-13 16:00:00] [INFO] Retention rules: hours 0, days 0, weeks 0, months 0
[2026-01-13 16:00:00] [INFO] Watch mode started, monitoring for changes...
[2026-01-13 16:15:30] [INFO] File modified: config.yaml
[2026-01-13 16:15:32] [INFO] Backed up: config.yaml → config_2026_01_13__16_15_32.yaml
[2026-01-13 16:20:00] [INFO] Watch mode stopped by user (Ctrl+C)
[2026-01-13 16:20:00] [INFO] Session summary: 1 of 1 files backed up
[2026-01-13 16:20:00] [INFO] ========== Session Ended ==========
```

**Log Entry Types:**

- **Session boundaries**: `========== Session Started/Ended ==========`
- **Configuration**: Command, paths, exclusion patterns, debounce delay and retention rules logged once at session start
- **Operations**: File backups, deleted old backups, exclusions, errors during session
- **Summary**: Statistics and completion status at session end

## Known Limitations

Behaviour that is known, not wanted, and accepted for now.
Each entry names the decision, so that it is not reported again as a new defect.

### KL-1: Two backups of one file within the same second share a name

The backup name has a resolution of one second (AC-2.2).
When the same file is backed up twice within one second, both backups get the same name,
and the newer complete backup replaces the older one (`os.replace`, AC-2.8).
Only the newer version is kept; a failed copy still leaves the older backup unchanged (AC-2.8).
This was already the behaviour before AC-2.8; the test `test_a_successful_backup_replaces_a_file_of_the_same_name` in `tests/test_backup.py` pins it.

**Decision (2026-11-18):** known and accepted for now.
With the default debounce delay of 2 seconds (AC-5.5), `watch` rarely backs up one file twice within one second.
One `run` backs up each file at most once; only two runs started within the same second can collide.
A change, for example a counter suffix for a name that is already taken, needs its own issue and changes AC-2.2 and that test on purpose.

### KL-2: Retention can misread the backups of a file whose name ends with a dot

Retention reads the original file and the time back from the backup name (AC-8.6).
For an original name that ends with a dot, this reading is not always unique, and it depends on the Python version (AC-2.2):

- On Python 3.13, one name can be the backup name of two original files.
  `a_2026_01_12__09_00_00._2026_01_13__14_30_22` is the backup of `a._2026_01_13__14_30_22` made on 12 January,
  and also the backup of `a_2026_01_12__09_00_00.` made on 13 January.
  AC-8.6 uses the reading whose original name does not end with a dot.
  A backup of the second file is therefore grouped with the first file and given the wrong time,
  so the rules may delete it earlier, or keep it longer, than they would for its real group.
- From Python 3.14 on, the name of such a backup has the dot after the timestamp (`a_2026_01_13__14_30_22.`), and no name has two readings.
  A backup made with Python 3.13 (`a._2026_01_13__14_30_22`) is then no backup name of `a.` any more:
  retention never deletes it, and it is not grouped with the newer backups of `a.`.

Windows cannot create a file name that ends with a dot, so this happens only on Linux and macOS.
In the second case, retention deletes no backup by mistake; in the first case, the newest backup of each group is still kept (AC-8.1).

**Decision (2026-11-18):** known and accepted for now, together with the design of the retention rules (issue #27).
A change needs its own issue, for example a backup name that does not depend on how `pathlib` splits a name ending with a dot.

### KL-3: Retention groups backups by case-sensitive file names

Retention groups the backups by their original file name and compares the names case-sensitively (AC-8.7).
When a source file is renamed only in its letter case, for example from `report.txt` to `Report.txt`, the old and the new backups form two groups.
The rules thin out each group on its own, and each group keeps its newest backup (AC-8.1),
so together they can keep more backups than the rules would keep for a single group, because each group counts its own periods.

**Decision (2026-11-18):** documented, not changed, together with the design of the retention rules (issue #27).

### KL-4: Retention ignores daylight saving time

Backup names carry local time without a time zone (AC-2.2), and retention reads the time of a backup from its name (AC-8.4).
Around a change of daylight saving time, ages and the order of backups can therefore be off by one hour:

- When the clocks go forward, `retention.hours` sees every backup made before the change as one hour older than it is,
  so a backup near the end of the N hours can be deleted up to one hour early.
- When the clocks go back, backups made before the change look one hour younger and are kept up to one hour longer.
- When the clocks go back, a backup made in the repeated hour can sort before an older backup from the first pass of that hour,
  so the rules can keep the older one as the newest backup of the file and delete the really newer one.
  `run` and `watch` never delete the backup they have just made (AC-8.9), so there this hits only older backups;
  `cleanup` has no backup just made and can delete the really newest one.

**Decision (2026-11-18):** documented, not changed; the issue decides that the time of a backup comes from its name (issue #27).

## Implementation Notes

### General

- Implementation language: Python; the minimum version is set by `requires-python` in `pyproject.toml`
- Use `typer` library for CLI framework with built-in help generation
- Use Python's `pathlib` for cross-platform path handling
- Copy a file as AC-2.8 says: `shutil.copyfile()` to the temporary file, `shutil.copystat()` for the metadata, `os.replace()` to the backup name
- Use `datetime.now()` for timestamp generation
- Use `Path.iterdir()` to iterate only files in the top-level directory (not recursive)
- Skip all entries where `Path.is_dir()` returns True
- All backup files are stored flat in the destination directory (no subdirectories)
- State file (`.backup_state.json`): AC-3.2 and AC-3.11 define its directory, AC-3.3 its two paths, and AC-3.11 and AC-3.12 how each path is used when it is read
- Timestamp format: `strftime("%Y_%m_%d__%H_%M_%S")` with 24-hour format
- Backup filename pattern: see AC-2.2; `BackupManager.generate_backup_filename()` makes the name
- Backup name reading for retention (AC-8.6): a name is a backup only when `generate_backup_filename()` gives exactly this name back
  for the original name and the time read from it.
  `retention.parse_backup_name()` reads a name,
  and `retention.select_backups_to_keep()` applies the rules (FR-8) to the backups of one original file, without any file access;
  `retention.plan_retention()` splits them into kept and deleted backups, newest first
- File access for retention: `backup.list_backup_groups()` lists the backups (AC-8.6, AC-8.7)
  and `backup.delete_backup()` deletes one and returns the outcome without reporting it (AC-8.13);
  `run` and `watch` apply the rules through `main.RetentionApplier` (AC-8.9 to AC-8.11)
- Implement atomic state file updates (write to temp file, then rename)
- Use `pathlib.Path.match()` for pattern matching with wildcard support
- Exclusion patterns: AC-4.6 (file name only) and AC-4.9 (which patterns are accepted)

### Watch Mode (FR-5)

- Top-level directory only: AC-1.3 and AC-4.7; the observer is scheduled with `recursive=False`
- Implement debouncing to wait for files to finish writing
- Debounce delay and its default: AC-5.5
- The debounce delay is saved in the state file; AC-3.6 to AC-3.9 define which delay `run` and `watch` use
- Use a timer-based approach: reset the timer on each event that AC-5.5 and AC-5.10 name, trigger backup when timer expires
- Catch the errors of the copy with try-except and report them by cause, as AC-6.18 defines it
- Log skipped files (locked/excluded) separately from successful backups
- Ensure clean shutdown on SIGINT (Ctrl+C)

### Help System

- Use `typer` with `rich` for formatted help output
- All commands must have detailed `help` parameter texts
- Provide usage examples in command docstrings
- Help text should be clear, concise, and actionable
- Include tips and notes for common use cases

### Logging (FR-6)

- Log file (`backup.log`) is stored in the destination directory
- Use Python's `logging` module for structured logging
- Log format: `[%(asctime)s] [%(levelname)s] %(message)s`
- Time format for logs: `%Y-%m-%d %H:%M:%S`
- Log to file only (not to console), console shows user-friendly messages
- Create log file during init or first run if it doesn't exist
- Always append to existing log file using mode 'a', never overwrite
- Use `logging.FileHandler` with UTF-8 encoding and append mode
- Each script execution creates a session with:
  - Session start marker and configuration (command, paths, excludes, debounce delay, retention rules)
  - Operation logs (backups, exclusions, errors)
  - Session end marker and summary
- Log excluded files with the reason defined in AC-6.17
- Settings are logged once per session at start, not repeated during operations

### Dependencies

- Python: the minimum version is set by `requires-python` in `pyproject.toml`
- `typer`: CLI framework with automatic help generation
- `rich`: Enhanced terminal output (used by typer for help formatting) and the prompts of the `config` menu
- `watchdog`: File system event monitoring (required for watch command)
- `pathlib`: Built-in, for path operations
- `shutil`: Built-in, for file copying
- `json`: Built-in, for state file management
- `logging`: Built-in, for activity logging
