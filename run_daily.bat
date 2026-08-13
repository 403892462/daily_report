@echo off
chcp 65001 >nul
cd /d %~dp0

set PYTHON=%~dp0.venv\Scripts\python.exe

echo ========================================
echo   日报自动化流程
echo ========================================
echo.

echo [1/4] 拉取数据...
%PYTHON% fetch_data.py
if %errorlevel% neq 0 (
    echo [1/4] 拉取数据失败！
    goto :end
)
echo.

echo [2/4] 处理数据...
%PYTHON% process_data.py
if %errorlevel% neq 0 (
    echo [2/4] 处理数据失败！
    goto :end
)
echo.

echo [3/4] 生成报表...
%PYTHON% generate_report.py
if %errorlevel% neq 0 (
    echo [3/4] 生成报表失败！
    goto :end
)
echo.

echo [4/4] 推送飞书...
%PYTHON% push_feishu.py
if %errorlevel% neq 0 (
    echo [4/4] 推送飞书失败！
    goto :end
)
echo.

echo ========================================
echo   全部完成！
echo ========================================

:end
