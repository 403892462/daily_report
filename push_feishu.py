#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
飞书推送脚本：将日报内容和图表推送到飞书群
图片上传至阿里云 OSS，通过 URL 嵌入飞书卡片
"""

import os
import json
import glob
import base64
import hashlib
import hmac
import time
from datetime import datetime

import urllib.request
import urllib.error
import urllib.parse

from PIL import Image
import oss2


FEISHU_TOKEN_URL = 'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/'
FEISHU_IMAGE_URL = 'https://open.feishu.cn/open-apis/im/v1/images'


def resize_image(file_path, scale=0.5):
    """等比缩小图片，返回临时文件路径"""
    img = Image.open(file_path)
    new_size = (int(img.width * scale), int(img.height * scale))
    resized = img.resize(new_size, Image.LANCZOS)

    tmp_path = file_path.rsplit('.', 1)[0] + '_resized.png'
    resized.save(tmp_path, 'PNG', optimize=True)
    return tmp_path


def load_env():
    """从 .env 文件读取配置"""
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    config = {}
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    return config


def gen_sign(secret):
    """生成飞书 webhook 签名"""
    timestamp = str(int(time.time()))
    string_to_sign = f'{timestamp}\n{secret}'
    hmac_code = hmac.new(string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
    sign = base64.b64encode(hmac_code).decode('utf-8')
    return timestamp, sign


def get_tenant_access_token(config):
    """获取飞书 tenant_access_token"""
    payload = json.dumps({
        'app_id': config['FEISHU_APP_ID'],
        'app_secret': config['FEISHU_APP_SECRET']
    }).encode('utf-8')
    req = urllib.request.Request(
        FEISHU_TOKEN_URL,
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read().decode('utf-8'))
    if result.get('code') != 0:
        raise Exception(f"获取 token 失败: {result}")
    return result['tenant_access_token']


def upload_to_feishu(file_path, token):
    """上传图片到飞书，返回 image_key"""
    if not os.path.exists(file_path):
        return None, f'文件不存在: {file_path}'

    filename = os.path.basename(file_path)
    boundary = '----FormBoundary7MA4YWxkTrZu0gW'

    with open(file_path, 'rb') as f:
        file_data = f.read()

    parts = []
    parts.append(f'--{boundary}\r\n')
    parts.append('Content-Disposition: form-data; name="image_type"\r\n\r\n')
    parts.append('message\r\n')
    parts.append(f'--{boundary}\r\n')
    parts.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n')
    parts.append('Content-Type: image/png\r\n\r\n')

    header = ''.join(parts).encode('utf-8')
    footer = f'\r\n--{boundary}--\r\n'.encode('utf-8')
    body = header + file_data + footer

    req = urllib.request.Request(
        FEISHU_IMAGE_URL,
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}'
        }
    )

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')
        return None, f'HTTP {e.code}: {error_body}'

    if result.get('code') != 0:
        return None, f"上传失败: {result}"
    return result['data']['image_key'], None


def create_oss_bucket(config):
    """根据 .env 配置创建 OSS Bucket 实例"""
    auth = oss2.Auth(config['OSS_ACCESS_KEY_ID'], config['OSS_ACCESS_KEY_SECRET'])
    return oss2.Bucket(auth, config['OSS_ENDPOINT'], config['OSS_BUCKET_NAME'])


def upload_to_oss(bucket, file_path, config):
    """上传图片到阿里云 OSS（公共读），返回直接访问 URL"""
    if not os.path.exists(file_path):
        return None, f'文件不存在: {file_path}'

    filename = os.path.basename(file_path)
    date_prefix = datetime.now().strftime('%Y/%m/%d')
    object_key = f'daily-reports/{date_prefix}/{filename}'

    try:
        bucket.put_object_from_file(object_key, file_path, headers={'Content-Type': 'image/png'})
        base_url = config['OSS_BASE_URL'].rstrip('/')
        url = f'{base_url}/{object_key}'
        return url, None
    except Exception as e:
        return None, str(e)


def parse_markdown_to_post(md_content):
    """将 Markdown 日报解析为飞书 post 富文本格式"""
    lines = md_content.split('\n')

    title = '销售日报'
    content = []

    for line in lines:
        line = line.rstrip()

        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            continue

        if line.strip().startswith('!['):
            continue

        if line.startswith('## '):
            content.append([{'tag': 'text', 'text': f'\n{line[3:].strip()}\n'}])
            continue

        if line.startswith('### '):
            content.append([{'tag': 'text', 'text': f'\n  {line[4:].strip()}\n'}])
            continue

        if line.startswith('|') and '---' not in line:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            text = '  '.join(cells)
            content.append([{'tag': 'text', 'text': text}])
            continue

        if '---' in line and '|' in line:
            continue

        if line.startswith('- '):
            content.append([{'tag': 'text', 'text': f'• {line[2:].strip()}'}])
            continue

        if line.strip() == '---':
            continue

        if line.strip():
            content.append([{'tag': 'text', 'text': line.strip()}])

    return title, content


def build_card_message(title, md_content, image_keys):
    """构建飞书卡片消息，图表以飞书原生 img 组件嵌入"""
    lines = md_content.split('\n')

    summary_lines = []
    anomaly_lines = []
    in_section = None

    for line in lines:
        if '今日概览' in line:
            in_section = 'summary'
            continue
        elif '渠道拆分' in line:
            in_section = 'channel'
            continue
        elif '异常预警' in line:
            in_section = 'anomaly'
            continue
        elif line.startswith('## ') and in_section:
            in_section = None
            continue

        if in_section == 'summary' and line.startswith('- '):
            summary_lines.append(line[2:].strip().replace('**', ''))
        elif in_section == 'anomaly' and '|' in line and '---' not in line and '类型' not in line:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if len(cells) >= 3:
                anomaly_lines.append(f'🔴 {cells[1]}: {cells[2]}')

    elements = []

    if summary_lines:
        summary_text = '\n'.join(summary_lines)
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': summary_text
            }
        })
        elements.append({'tag': 'hr'})

    if anomaly_lines:
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': '**⚠️ 异常预警**\n' + '\n'.join(anomaly_lines)
            }
        })
    else:
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': '✅ 今日无异常'
            }
        })

    elements.append({'tag': 'hr'})

    for label, img_key in image_keys:
        elements.append({
            'tag': 'div',
            'text': {
                'tag': 'lark_md',
                'content': f'**📈 {label}**'
            }
        })
        elements.append({
            'tag': 'img',
            'img_key': img_key,
            'alt': {
                'tag': 'plain_text',
                'content': label
            },
            'mode': 'fit_horizontal',
            'preview': True
        })

    elements.append({
        'tag': 'note',
        'elements': [
            {'tag': 'plain_text', 'content': f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'}
        ]
    })

    card = {
        'config': {'wide_screen_mode': True},
        'header': {
            'title': {'tag': 'plain_text', 'content': title},
            'template': 'blue'
        },
        'elements': elements
    }

    return card


def send_to_feishu(webhook_url, message, secret=None):
    """发送消息到飞书"""
    payload = message.copy()

    if secret:
        timestamp, sign = gen_sign(secret)
        payload['timestamp'] = timestamp
        payload['sign'] = sign

    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read().decode('utf-8'))
        return True, result
    except urllib.error.HTTPError as e:
        return False, f'HTTP Error {e.code}: {e.read().decode()}'
    except Exception as e:
        return False, str(e)


def main():
    output_dir = os.path.join(os.path.dirname(__file__), 'output')

    config = load_env()
    webhook_url = config.get('FEISHU_WEBHOOK_URL')
    secret = config.get('FEISHU_WEBHOOK_SECRET')

    if not webhook_url:
        print('错误: .env 中未配置 FEISHU_WEBHOOK_URL')
        return

    feishu_keys = ['FEISHU_APP_ID', 'FEISHU_APP_SECRET']
    missing = [k for k in feishu_keys if not config.get(k)]
    if missing:
        print(f'错误: .env 中缺少飞书应用配置: {", ".join(missing)}')
        return

    md_files = sorted(glob.glob(os.path.join(output_dir, 'daily_report_*.md')))
    if not md_files:
        print('错误: output 目录下未找到 daily_report_*.md 文件')
        print('请先运行 generate_report.py 生成日报')
        return

    md_file = md_files[-1]
    print(f'读取日报: {md_file}')

    with open(md_file, 'r', encoding='utf-8') as f:
        md_content = f.read()

    date_match = os.path.basename(md_file).replace('daily_report_', '').replace('.md', '')
    chart_files = glob.glob(os.path.join(output_dir, f'chart_*_{date_match.replace("-", "_")}.png'))
    print(f'找到 {len(chart_files)} 张图表')

    print('获取飞书 access_token ...', end=' ')
    try:
        token = get_tenant_access_token(config)
        print('✅')
    except Exception as e:
        print(f'❌ {e}')
        return

    image_keys = []

    chart_labels = {
        'channel': '渠道销售额',
        'trend': '近7天趋势',
    }

    for chart_path in chart_files:
        chart_type = os.path.basename(chart_path).split('_')[1]
        label = chart_labels.get(chart_type, os.path.basename(chart_path))

        print(f'  缩放 {os.path.basename(chart_path)} -> 50% ...', end=' ')
        resized_path = resize_image(chart_path, scale=0.5)
        print('✅')

        print(f'  上传 {os.path.basename(resized_path)} -> 飞书 ...', end=' ')
        img_key, err = upload_to_feishu(resized_path, token)
        if img_key:
            print(f'✅')
            image_keys.append((label, img_key))
        else:
            print(f'❌ {err}')

        if os.path.exists(resized_path):
            os.remove(resized_path)

    title = f'📊 销售日报 {date_match}'
    card = build_card_message(title, md_content, image_keys)

    message = {
        'msg_type': 'interactive',
        'card': card
    }

    print(f'\n正在推送到飞书...')
    success, result = send_to_feishu(webhook_url, message, secret)

    if success:
        print(f'✅ 推送成功!')
        print(f'   响应: {result}')
    else:
        print(f'❌ 推送失败: {result}')


if __name__ == '__main__':
    main()
