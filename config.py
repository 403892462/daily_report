#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
统一配置管理：从 .env 加载并按模块分组提供配置项
"""

import os
import sys
from dotenv import load_dotenv


def _require(keys, section_name):
    """校验必填配置项，缺失时打印明确提示并退出"""
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        print(f"[配置错误] {section_name} 缺少必要配置: {', '.join(missing)}")
        print("请复制 .env.example 为 .env 并填写对应配置项")
        sys.exit(1)


def _optional(keys, defaults=None):
    """读取可选配置项，返回字典"""
    defaults = defaults or {}
    return {k: os.getenv(k, defaults.get(k, '')) for k in keys}


load_dotenv(override=True)


# ── 数据库配置 ──────────────────────────────────────────────
def get_db_config():
    _require(['DB_SERVER', 'DB_USER', 'DB_PASSWORD'], '数据库')
    return {
        'server': os.getenv('DB_SERVER'),
        'port': os.getenv('DB_PORT', '1433'),
        'user': os.getenv('DB_USER'),
        'password': os.getenv('DB_PASSWORD'),
        'database': os.getenv('DB_NAME', 'NewPOS_Dev'),
    }


# ── 飞书配置 ────────────────────────────────────────────────
def get_feishu_config():
    _require(
        ['FEISHU_WEBHOOK_URL', 'FEISHU_APP_ID', 'FEISHU_APP_SECRET'],
        '飞书',
    )
    return {
        'webhook_url': os.getenv('FEISHU_WEBHOOK_URL'),
        'webhook_secret': os.getenv('FEISHU_WEBHOOK_SECRET', ''),
        'app_id': os.getenv('FEISHU_APP_ID'),
        'app_secret': os.getenv('FEISHU_APP_SECRET'),
    }


# ── 阿里云 OSS 配置 ─────────────────────────────────────────
def get_oss_config():
    _require(
        ['OSS_ACCESS_KEY_ID', 'OSS_ACCESS_KEY_SECRET', 'OSS_ENDPOINT', 'OSS_BUCKET_NAME'],
        '阿里云 OSS',
    )
    return {
        'access_key_id': os.getenv('OSS_ACCESS_KEY_ID'),
        'access_key_secret': os.getenv('OSS_ACCESS_KEY_SECRET'),
        'endpoint': os.getenv('OSS_ENDPOINT'),
        'bucket_name': os.getenv('OSS_BUCKET_NAME'),
        'base_url': os.getenv('OSS_BASE_URL', ''),
    }
