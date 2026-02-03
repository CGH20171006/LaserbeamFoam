@echo off
REM 启动Claude Code和Antigravity Tools
REM 打开两个独立的WSL终端窗口

echo 正在启动Claude工具...

REM 启动第一个终端运行cc-switch
start "CC-Switch" wsl -e bash -c "cc-switch; exec bash"

REM 稍等一下，确保第一个窗口启动
timeout /t 1 /nobreak >nul

REM 启动第二个终端运行antigravity_tools
start "Antigravity Tools" wsl -e bash -c "antigravity_tools; exec bash"

echo 完成！
