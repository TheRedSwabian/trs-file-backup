BeforeAll {
    $script:projectRoot = Split-Path $PSScriptRoot -Parent
    $script:testOutputDir = Join-Path $script:projectRoot "build\portable-test"
}

Describe "create-portable.ps1 - Version Reading" {
    It "should read version from __init__.py" {
        $versionFile = Join-Path $script:projectRoot "src\trs_file_backup\__init__.py"
        Test-Path $versionFile | Should -Be $true

        $versionLine = Get-Content $versionFile | Select-String '__version__\s*=\s*"([^"]+)"'
        $versionLine | Should -Not -BeNullOrEmpty

        $version = $versionLine.Matches.Groups[1].Value
        $version | Should -Match '^\d+\.\d+\.\d+$'
    }
}

Describe "create-portable.ps1 - Wheel Package Creation" {
    BeforeAll {
        if (Test-Path $script:testOutputDir) {
            Remove-Item -Recurse -Force $script:testOutputDir
        }
        Push-Location $script:projectRoot
        & ".\create-portable.ps1" -Type wheel -OutputDir $script:testOutputDir 2>&1 | Out-Null
        Pop-Location
    }

    It "should create output directory" {
        Test-Path $script:testOutputDir | Should -Be $true
    }

    It "should create a wheel file" {
        $wheelFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.whl"
        $wheelFiles.Count | Should -BeGreaterThan 0
    }

    It "should create wheel with correct naming format" {
        $wheelFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.whl"
        $wheelFiles[0].Name | Should -Match '^trs-file-backup-\d+\.\d+\.\d+-py3-none-any\.whl$'
    }

    It "should include version in wheel filename" {
        $versionFile = Join-Path $script:projectRoot "src\trs_file_backup\__init__.py"
        $versionLine = Get-Content $versionFile | Select-String '__version__\s*=\s*"([^"]+)"'
        $version = $versionLine.Matches.Groups[1].Value

        $wheelFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.whl"
        $wheelFiles[0].Name | Should -Match "trs-file-backup-$version-"
    }

    It "should create installation instructions" {
        $instructionsFile = Join-Path $script:testOutputDir "INSTALL-WHEEL.txt"
        Test-Path $instructionsFile | Should -Be $true
    }

    It "should include pip install command in instructions" {
        $instructionsFile = Join-Path $script:testOutputDir "INSTALL-WHEEL.txt"
        $content = Get-Content $instructionsFile -Raw
        $content | Should -Match 'pip install'
    }
}

Describe "create-portable.ps1 - ZIP Package Creation" {
    BeforeAll {
        if (Test-Path $script:testOutputDir) {
            Remove-Item -Recurse -Force $script:testOutputDir
        }
        Push-Location $script:projectRoot
        & ".\create-portable.ps1" -Type zip -OutputDir $script:testOutputDir 2>&1 | Out-Null
        Pop-Location
    }

    It "should create a ZIP file" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipFiles.Count | Should -BeGreaterThan 0
    }

    It "should create ZIP with version in filename" {
        $versionFile = Join-Path $script:projectRoot "src\trs_file_backup\__init__.py"
        $versionLine = Get-Content $versionFile | Select-String '__version__\s*=\s*"([^"]+)"'
        $version = $versionLine.Matches.Groups[1].Value

        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipFiles[0].Name | Should -Match "trs-file-backup-Portable-v$version\.zip"
    }

    It "should create setup instructions" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipContent = [System.IO.Compression.ZipFile]::OpenRead($zipFiles[0].FullName)
        $setupInstructions = $zipContent.Entries | Where-Object { $_.Name -eq 'SETUP-INSTRUCTIONS.txt' }
        $setupInstructions | Should -Not -BeNullOrEmpty
        $zipContent.Dispose()
    }

    It "should include build.ps1 command in setup instructions" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipContent = [System.IO.Compression.ZipFile]::OpenRead($zipFiles[0].FullName)
        $setupEntry = $zipContent.Entries | Where-Object { $_.Name -eq 'SETUP-INSTRUCTIONS.txt' }
        $stream = $setupEntry.Open()
        $reader = [System.IO.StreamReader]::new($stream)
        $content = $reader.ReadToEnd()
        $reader.Close()
        $stream.Close()
        $zipContent.Dispose()
        $content | Should -Match 'build\.ps1 -install'
    }

    It "should create a valid ZIP archive" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        { [System.IO.Compression.ZipFile]::OpenRead($zipFiles[0].FullName).Dispose() } | Should -Not -Throw
    }

    It "should include source code in ZIP" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipContent = [System.IO.Compression.ZipFile]::OpenRead($zipFiles[0].FullName)
        $entries = $zipContent.Entries | Where-Object { $_.FullName -match 'src/' }
        $entries.Count | Should -BeGreaterThan 0
        $zipContent.Dispose()
    }

    It "should include pyproject.toml in ZIP" {
        $zipFiles = Get-ChildItem -Path $script:testOutputDir -Filter "*.zip"
        $zipContent = [System.IO.Compression.ZipFile]::OpenRead($zipFiles[0].FullName)
        $pyproject = $zipContent.Entries | Where-Object { $_.Name -eq 'pyproject.toml' }
        $pyproject | Should -Not -BeNullOrEmpty
        $zipContent.Dispose()
    }
}

Describe "create-portable.ps1 - Error Handling" {
    It "should accept custom output directory" {
        $customDir = Join-Path $script:projectRoot "build\custom-test-output"
        if (Test-Path $customDir) {
            Remove-Item -Recurse -Force $customDir -ErrorAction SilentlyContinue
        }
        Push-Location $script:projectRoot
        & ".\create-portable.ps1" -Type wheel -OutputDir $customDir 2>&1 | Out-Null
        Pop-Location
        Test-Path $customDir | Should -Be $true
        if (Test-Path $customDir) {
            Remove-Item -Recurse -Force $customDir -ErrorAction SilentlyContinue
        }
    }
}
