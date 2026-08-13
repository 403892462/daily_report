#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试数据库连接"""

import pymssql
from config import get_db_config

db_config = get_db_config()

print(f"服务器: {db_config['server']}:{db_config['port']}")
print(f"用户: {db_config['user']}")
print(f"数据库: {db_config['database']}")
print("正在连接...")

try:
    conn = pymssql.connect(
        server=db_config['server'],
        port=db_config['port'],
        user=db_config['user'],
        password=db_config['password'],
        database=db_config['database'],
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
