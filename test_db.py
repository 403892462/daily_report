#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试数据库连接"""

import os
import pymssql
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
    conn = pymssql.connect(
        server=server,
        port=port,
        user=user,
        password=password,
        database=database,
        charset='utf8',
        login_timeout=10,
        timeout=30,
        tds_version='7.3'
    )
    print("连接成功！")
    
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM RT_POSVoucher WHERE DocumentDate >= '2026-07-01' AND DocumentDate < '2026-08-01'")
    result = cursor.fetchone()
    print(f"7月份数据量: {result[0]} 条")
    
    conn.close()
except Exception as e:
    print(f"连接失败: {e}")
