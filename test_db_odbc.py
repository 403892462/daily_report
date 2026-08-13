#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试数据库连接 - 使用 pyodbc"""

import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

server = os.getenv('DB_SERVER')
port = os.getenv('DB_PORT', '1433')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
database = os.getenv('DB_NAME', 'NewPOS_Dev')

print(f"服务器: {server}:{port}")
print(f"用户: {user}")
print(f"数据库: {database}")
print("正在连接...")

try:
    # 使用旧版 SQL Server 驱动
    conn_str = f"DRIVER={{SQL Server}};SERVER={server},{port};DATABASE={database};UID={user};PWD={password}"
    conn = pyodbc.connect(conn_str, timeout=30)
    print("连接成功！")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM RT_POSVoucher WHERE DocumentDate >= '2026-07-01' AND DocumentDate < '2026-08-01'")
    result = cursor.fetchone()
    print(f"7月份数据量: {result[0]} 条")
    
    conn.close()
except Exception as e:
    print(f"连接失败: {e}")
