@echo off
setlocal
php "%~dp0check-vietnamese-encoding.php" %*
exit /b %ERRORLEVEL%
