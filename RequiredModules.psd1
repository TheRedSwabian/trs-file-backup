@{
    # PowerShell modules required for this project
    # Install with: Install-Module -Name <ModuleName> -MinimumVersion <Version>
    # Or use Scoop: scoop install pester
    
    Pester = @{
        Version = "5.0.0"
        Repository = "PSGallery"
        InstallCommand = "scoop install pester"
        Required = $true
        Purpose = "PowerShell test framework for *.Tests.ps1 files"
    }
}
