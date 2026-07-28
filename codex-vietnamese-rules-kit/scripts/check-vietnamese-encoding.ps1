$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
php "$ScriptDir/check-vietnamese-encoding.php" @args
exit $LASTEXITCODE
