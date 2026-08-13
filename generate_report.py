#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日报生成脚本：读取 report_data JSON，生成 Markdown 格式销售日报 + 图表
"""

import os
import json
import glob
from datetime import datetime

import matplotlib
matplotlib.use('Agg')  # 非交互式后端
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 深色主题配色
DARK_BG = '#1a1a2e'
DARK_FG = '#eaeaea'
ACCENT_COLORS = ['#00d9ff', '#ff6b6b', '#ffd93d', '#6bcf7f', '#a855f7']


def setup_dark_theme():
    """设置 matplotlib 深色主题"""
    plt.rcParams.update({
        'figure.facecolor': DARK_BG,
        'axes.facecolor': '#16213e',
        'axes.edgecolor': DARK_FG,
        'axes.labelcolor': DARK_FG,
        'text.color': DARK_FG,
        'xtick.color': DARK_FG,
        'ytick.color': DARK_FG,
        'grid.color': '#2a2a4a',
        'grid.alpha': 0.5,
        'font.size': 12,
        'axes.titlesize': 16,
        'axes.labelsize': 13,
    })

    # 尝试使用中文字体
    for font_name in ['Microsoft YaHei', 'SimHei', 'PingFang SC', 'sans-serif']:
        if any(font_name in f.name for f in fm.fontManager.ttflist):
            plt.rcParams['font.sans-serif'] = [font_name] + plt.rcParams['font.sans-serif']
            break
    plt.rcParams['axes.unicode_minus'] = False


def load_report(json_path):
    """读取 JSON 报告"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_anomalies(report_date, output_dir):
    """读取异常报告 Markdown"""
    date_str = report_date.replace('-', '_')
    anomalies_file = os.path.join(output_dir, f'anomalies_{date_str}.md')

    if not os.path.exists(anomalies_file):
        return None

    with open(anomalies_file, 'r', encoding='utf-8') as f:
        return f.read()


def format_number(num):
    """格式化数字，添加千分位"""
    if isinstance(num, int):
        return f'{num:,}'
    return f'{num:,.2f}'


def generate_channel_chart(report, output_dir):
    """生成各渠道销售额柱状图"""
    setup_dark_theme()

    channel_data = report.get('渠道明细', {})
    channels = []
    sales = []
    colors = []

    color_map = {'天猫': ACCENT_COLORS[0], '抖音': ACCENT_COLORS[1], 'POS': ACCENT_COLORS[2]}

    for ch in ['天猫', '抖音', 'POS']:
        if ch in channel_data and channel_data[ch]['销售额'] > 0:
            channels.append(ch)
            sales.append(channel_data[ch]['销售额'])
            colors.append(color_map.get(ch, ACCENT_COLORS[3]))

    if not channels:
        print('警告: 无渠道销售数据，跳过柱状图')
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    bars = ax.bar(channels, sales, color=colors, width=0.5, edgecolor=DARK_FG, linewidth=0.5)

    # 在柱子上方显示数值
    for bar, val in zip(bars, sales):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(sales) * 0.02,
                f'{val:,.0f}', ha='center', va='bottom', color=DARK_FG, fontsize=11, fontweight='bold')

    ax.set_title('各渠道销售额', pad=15, fontweight='bold')
    ax.set_ylabel('销售额 (元)')
    ax.grid(axis='y', linestyle='--')
    ax.set_axisbelow(True)

    # 去掉上右边框
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()

    report_date = report['报告日期'].replace('-', '_')
    output_file = os.path.join(output_dir, f'chart_channel_{report_date}.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    return output_file


def generate_trend_chart(output_dir):
    """生成最近7天销售额趋势折线图（至少需要2天数据）"""
    setup_dark_theme()

    # 读取所有 report_data JSON
    json_files = sorted(glob.glob(os.path.join(output_dir, 'report_data_*.json')))

    num_files = len(json_files)
    print(f'  发现 {num_files} 天历史数据')

    if num_files < 2:
        print('  提示: 至少需要 2 天数据才能生成趋势图')
        return None

    # 取最近7个文件
    recent_files = json_files[-7:]

    dates = []
    total_sales = []

    for f in recent_files:
        with open(f, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
        date_str = data.get('报告日期', '')
        sales = data.get('全渠道汇总', {}).get('总销售额', 0)
        dates.append(date_str[5:])  # 只显示 MM-DD
        total_sales.append(sales)

    if len(dates) < 2:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))

    # 绘制折线
    ax.plot(dates, total_sales, color=ACCENT_COLORS[0], linewidth=2.5,
            marker='o', markersize=8, markerfacecolor=ACCENT_COLORS[0],
            markeredgecolor=DARK_FG, markeredgewidth=1.5, zorder=5)

    # 填充区域
    ax.fill_between(dates, total_sales, alpha=0.2, color=ACCENT_COLORS[0])

    # 在每个点显示数值
    for i, (d, v) in enumerate(zip(dates, total_sales)):
        ax.annotate(f'{v:,.0f}', (d, v), textcoords='offset points',
                    xytext=(0, 12), ha='center', color=DARK_FG, fontsize=10, fontweight='bold')

    ax.set_title('近7天销售额趋势', pad=15, fontweight='bold')
    ax.set_xlabel('日期')
    ax.set_ylabel('销售额 (元)')
    ax.grid(axis='y', linestyle='--')
    ax.set_axisbelow(True)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()

    report_date = dates[-1].replace('-', '_')
    # 从最新 JSON 获取完整日期
    with open(recent_files[-1], 'r', encoding='utf-8') as fp:
        data = json.load(fp)
    full_date = data.get('报告日期', '').replace('-', '_')

    output_file = os.path.join(output_dir, f'chart_trend_{full_date}.png')
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    plt.close()

    return output_file


def generate_markdown(report, anomalies_content):
    """生成 Markdown 日报"""
    lines = []

    # 标题
    lines.append(f'# 销售日报 {report["报告日期"]}')
    lines.append('')

    # 今日概览
    summary = report['全渠道汇总']
    dod = report.get('环比变化', {})

    lines.append('## 📊 今日概览')
    lines.append('')

    # 销售额环比
    sales_dod = dod.get('总销售额环比', 'N/A') if isinstance(dod, dict) else 'N/A'
    lines.append(f'- **全渠道销售额：** {format_number(summary["总销售额"])} 元（环比 {sales_dod}）')
    lines.append(f'- **总销量：** {format_number(summary["总销量"])} 件')
    lines.append(f'- **整体毛利率：** {summary["整体毛利率"]}')
    lines.append('')

    # 渠道拆分
    lines.append('## 🏪 渠道拆分')
    lines.append('')
    lines.append('| 渠道 | 销售额 | 占比 | 环比 |')
    lines.append('|------|--------|------|------|')

    channel_detail = report.get('渠道明细', {})
    channel_dod = dod.get('渠道销售额环比', {}) if isinstance(dod, dict) else {}

    for ch in ['天猫', '抖音', 'POS']:
        if ch in channel_detail:
            info = channel_detail[ch]
            ch_dod = channel_dod.get(ch, 'N/A')
            sales = format_number(info['销售额'])
            lines.append(f'| {ch} | {sales} 元 | {info["占比"]} | {ch_dod} |')

    lines.append('')

    # 品类 TOP3
    lines.append('## 📦 品类 TOP3')
    lines.append('')
    lines.append('| 排名 | 品类代码 | 销售额 |')
    lines.append('|------|----------|--------|')

    cat_top = report.get('品类销售额top3', [])
    for i, cat in enumerate(cat_top, 1):
        lines.append(f'| {i} | {cat["品类代码"]} | {format_number(cat["销售额"])} 元 |')

    lines.append('')

    # 畅销 TOP3 / 滞销 TOP3
    lines.append('## 🏆 畅销 TOP3 / 滞销 TOP3')
    lines.append('')

    sku_rank = report.get('SKU排名', {})
    best = sku_rank.get('畅销top3', [])
    worst = sku_rank.get('滞销top3', [])

    lines.append('### 畅销 TOP3')
    lines.append('')
    lines.append('| 排名 | 商品编码 | 销量 |')
    lines.append('|------|----------|------|')
    for i, item in enumerate(best, 1):
        lines.append(f'| {i} | {item["商品编码"]} | {item["销量"]} |')

    lines.append('')
    lines.append('### 滞销 TOP3')
    lines.append('')
    lines.append('| 排名 | 商品编码 | 销量 |')
    lines.append('|------|----------|------|')
    for i, item in enumerate(worst, 1):
        lines.append(f'| {i} | {item["商品编码"]} | {item["销量"]} |')

    lines.append('')

    # 异常预警
    lines.append('## ⚠️ 异常预警')
    lines.append('')

    anomaly_count = report.get('异常检测', {}).get('异常项数量', 0)
    warning_count = report.get('异常检测', {}).get('预警项数量', 0)

    if anomaly_count == 0 and warning_count == 0:
        lines.append('✅ 今日无异常')
    else:
        # 从 anomalies 文件中提取表格内容
        if anomalies_content:
            # 提取异常项和预警项表格
            in_anomaly_section = False
            in_warning_section = False
            for line in anomalies_content.split('\n'):
                if '## 🔴 异常项' in line:
                    in_anomaly_section = True
                    in_warning_section = False
                    continue
                elif '## 🟡 预警项' in line:
                    in_anomaly_section = False
                    in_warning_section = True
                    continue
                elif line.startswith('## ') or line.startswith('# '):
                    in_anomaly_section = False
                    in_warning_section = False
                    continue

                if (in_anomaly_section or in_warning_section) and line.strip():
                    lines.append(line)
        else:
            if anomaly_count > 0:
                lines.append(f'🔴 发现 {anomaly_count} 个异常项')
            if warning_count > 0:
                lines.append(f'🟡 发现 {warning_count} 个预警项')

    lines.append('')
    lines.append('---')
    lines.append(f'*报告生成时间: {report.get("生成时间", "N/A")}*')

    return '\n'.join(lines)


def main():
    output_dir = os.path.join(os.path.dirname(__file__), 'output')

    # 定位最新的 report_data JSON
    json_files = sorted(glob.glob(os.path.join(output_dir, 'report_data_*.json')))

    if not json_files:
        print('错误: output 目录下未找到 report_data_*.json 文件')
        print('请先运行 process_data.py 生成报告数据')
        return

    json_path = json_files[-1]
    print(f'读取报告: {json_path}')

    # 加载数据
    report = load_report(json_path)
    report_date = report['报告日期']

    # 加载异常报告
    anomalies_content = load_anomalies(report_date, output_dir)

    # 生成图表
    print('生成图表...')
    channel_chart = generate_channel_chart(report, output_dir)
    trend_chart = generate_trend_chart(output_dir)

    if channel_chart:
        print(f'  渠道柱状图: {channel_chart}')
    if trend_chart:
        print(f'  趋势折线图: {trend_chart}')

    # 生成 Markdown
    markdown = generate_markdown(report, anomalies_content)

    # 在 Markdown 中插入图表引用
    chart_section = []
    if channel_chart or trend_chart:
        chart_section.append('')
        chart_section.append('## 📈 数据图表')
        chart_section.append('')
        if channel_chart:
            chart_name = os.path.basename(channel_chart)
            chart_section.append(f'### 渠道销售额')
            chart_section.append(f'![渠道销售额]({chart_name})')
            chart_section.append('')
        if trend_chart:
            chart_name = os.path.basename(trend_chart)
            chart_section.append(f'### 近7天趋势')
            chart_section.append(f'![销售趋势]({chart_name})')
            chart_section.append('')

    # 在异常预警之前插入图表
    lines = markdown.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('## ⚠️ 异常预警'):
            new_lines.extend(chart_section)
        new_lines.append(line)

    markdown = '\n'.join(new_lines)

    # 保存
    output_file = os.path.join(output_dir, f'daily_report_{report_date}.md')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown)

    print(f'\n日报已保存: {output_file}')
    print()
    print(markdown)


if __name__ == '__main__':
    main()
