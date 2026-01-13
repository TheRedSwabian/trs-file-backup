echo 'Printing all parameters:'
params.each { param ->
    echo "${param.key} = ${param.value}"
}

properties([
    buildDiscarder(logRotator(numToKeepStr: '20')),
    disableConcurrentBuilds(),
    parameters ([
    booleanParam(
            name: 'do_prerelease',
            defaultValue: false,
            description: '''If set to true, will create a prerelease.
                This is required to avoid creating prereleases automatically when pushing a branch.''',
        ),
    string(
            name: 'prerelease_token',
            defaultValue: '',
            description: '''The prerelease token can be used when multiple users
                want to create release candidates. One can define an own unique token
                to avoid conflicts: rcN.dev, where N is a digit. For example: rc1.dev'''
        ),
    ])
])

node('SPLE') {
    ws('sple/trs-file-backup') {
        stage('checkout') {
            // git should use the Windows Store (certificates), but this fails sometimes
            bat 'git config --global http.sslVerify false'
            checkout scm
        }

        stage('bootstrap') {
            // Initial SPLE setup
            bat 'powershell.exe -NonInteractive -ExecutionPolicy Bypass -Command "Invoke-WebRequest https://git.example.com/projects/SPLE/repos/sple-setup/raw/bin/install.ps1 -OutFile $env:TMP\\install.ps1; . $env:TMP\\install.ps1"'
            bat 'call build.bat -install -clean || exit /b 1'
        }

        stage('build') {
            withCredentials([
                usernamePassword(
                    credentialsId: 'mq_s_jenkinsrepo',
                    usernameVariable: 'PYPI_USER',
                    passwordVariable: 'PYPI_PASSWD'
                ),
                usernamePassword(
                    credentialsId: 'mq_s_jenkinsrepo',
                    usernameVariable: 'BITBUCKET_USER',
                    passwordVariable: 'BITBUCKET_TOKEN'
                )
            ]) {
                def buildCommand = "call build.bat -deploy -clean"
                if (params.do_prerelease) {
                    buildCommand += " -doPrerelease"
                }
                if (params.prerelease_token?.trim()) {
                    buildCommand += " -prereleaseToken \"${params.prerelease_token}\""
                }

                bat "${buildCommand} || exit /b 1"

                dir('build') {
                    archiveArtifacts(
                        artifacts: 'docs.html',
                        // Documentation might not be published for all builds, thus allow missing redirects
                        allowEmptyArchive: true
                    )
                    junit allowEmptyResults: false, keepLongStdio: false, testResults: 'tests/test-report.xml'
                }
            }
        }
    }
}
