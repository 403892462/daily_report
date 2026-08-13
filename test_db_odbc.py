#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试数据库连接 - 使用 pyodbc"""

import pyodbc
from config import get_db_config

db_config = get_db_config()

print(f"服务器: {db_config['server']}:{db_config['port']}")
print(f"用户: {db_config['user']}")
print(f"数据库: {db_config['database']}")
print("正在连接...")

try:
    # 使用旧版 SQL Server 驱动
    conn_str = f"DRIVER={{SQL Server}};SERVER={db_config['server']},{db_config['port']};DATABASE={db_config['database']};UID={db_config['user']};PWD={db_config['password']}"
    conn = pyodbc.connect(conn_str, timeout=30)
    print("连接成功！")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM RT_POSVoucher WHERE DocumentDate >= '2026-07-01' AND DocumentDate < '2026-08-01'")
    result = cursor.fetchone()
    print(f"7月份数据量: {result[0]} 条")
    
    conn.close()
except Exception as e:
    print(f"连接失败: {e}")
