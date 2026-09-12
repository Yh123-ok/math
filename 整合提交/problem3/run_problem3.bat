@echo off
cd /d "%~dp0"
python problem3.py
if errorlevel 1 (
    echo.
    echo 运行失败，请检查上面的错误信息。
) else (
    echo.
    echo 已生成当前目录的 result3.xlsx。
)
pause
