# CHANGELOG


## v1.0.3 (2026-01-20)

### Bug Fixes

- Windows atomic write and test compatibility
  ([`f7b441c`](https://github.com/TheRedSwabian/trs-file-backup/commit/f7b441cb91a3a89f405b271a1d0686e9849a1625))


## v1.0.2 (2026-01-20)

### Bug Fixes

- Improve version handling and remove redundant output
  ([`ca9348e`](https://github.com/TheRedSwabian/trs-file-backup/commit/ca9348e46ad5925f352c51029dace65ba69388da))

- Show --version flag in help output and make it functional - Remove duplicate session summary
  message on watch stop - Clean dist directory before build to prevent stale wheel packages


## v1.0.1 (2026-01-20)

### Bug Fixes

- Prevent duplicate backups from rapid filesystem events on Windows
  ([`d2db3f5`](https://github.com/TheRedSwabian/trs-file-backup/commit/d2db3f5c1b983ae3cd6d1405ce784fff7c711df4))

Implement debounce mechanism to consolidate multiple events per file into single backup.


## v1.0.0 (2026-01-19)

### Features

- Change backupfile name extend help information
  ([`4d97800`](https://github.com/TheRedSwabian/trs-file-backup/commit/4d97800328a9d5b659043725d8259513381fd6ab))


## v0.1.0 (2026-01-16)

### Bug Fixes

- Add pester test and fix some stuff
  ([`ca3c60d`](https://github.com/TheRedSwabian/trs-file-backup/commit/ca3c60d75c21c1daa363bbb15a2e547dfc031672))

- Add portable creation
  ([`446887e`](https://github.com/TheRedSwabian/trs-file-backup/commit/446887e2ec4d0a294cbb81881c714eb6c760951a))

- Corrected tests and setup
  ([`8ab8ca2`](https://github.com/TheRedSwabian/trs-file-backup/commit/8ab8ca23fe11649bf7062e5a37dbb21a067eff5a))

### Documentation

- Add features
  ([`ba8946f`](https://github.com/TheRedSwabian/trs-file-backup/commit/ba8946f79a1c65aafd1d3941b9382b017ca1f506))

### Features

- Add correct version in wheel file
  ([`3ffdf3c`](https://github.com/TheRedSwabian/trs-file-backup/commit/3ffdf3c57c7aa487f74548d1e14e900fd8967662))

- Implementation with claude sonnet 4.5
  ([`8854d10`](https://github.com/TheRedSwabian/trs-file-backup/commit/8854d1036fca03947196c36767e27245cba98ad6))
