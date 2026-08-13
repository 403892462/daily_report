#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据处理脚本：读取 raw Excel，完成清洗、统计、环比计算，输出 JSON 报告
"""

import os
import json
import glob
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class ReportEncoder(json.JSONEncoder):
    """处理 numpy 类型的 JSON 序列化"""
    def default(self, obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def load_raw_data(file_path):
    """读取 raw Excel 文件"""
    df = pd.read_excel(file_path)
    return df


def clean_data(df):
    """数据清洗：去空值、去重复行、统一日期格式"""
    # 去除全空行
    df = df.dropna(how='all')

    # 去除关键列的空值行（门店编码、商品编码、销售日期）
    key_cols = ['门店编码', '商品编码', '销售日期']
    existing_key_cols = [c for c in key_cols if c in df.columns]
    if existing_key_cols:
        df = df.dropna(subset=existing_key_cols)

    # 去除重复行
    df = df.drop_duplicates()

    # 统一日期格式为 YYYY-MM-DD 字符串
    if '销售日期' in df.columns:
        df['销售日期'] = pd.to_datetime(df['销售日期']).dt.strftime('%Y-%m-%d')

    # 数值列确保为 numeric
    for col in ['销售数量', '应收金额', '扣减金额']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    return df.reset_index(drop=True)


def extract_category(code):
    """从商品编码前2位提取品类代码"""
    if pd.isna(code) or len(str(code)) < 2:
        return '未知'
    return str(code)[:2]


def calc_total_summary(df):
    """全渠道汇总：总销售额、总销量、整体毛利率"""
    total_sales = df['应收金额'].sum()
    total_qty = int(df['销售数量'].sum())
    total_cost = df['扣减金额'].sum()
    gross_profit = total_sales - total_cost
    gross_margin = round(gross_profit / total_sales * 100, 2) if total_sales > 0 else 0

    return {
        '总销售额': round(total_sales, 2),
        '总销量': total_qty,
        '总成本': round(total_cost, 2),
        '毛利额': round(gross_profit, 2),
        '整体毛利率': f'{gross_margin}%'
    }


def calc_channel_summary(df):
    """按渠道维度拆分：销售额、销量、占比"""
    channels = ['天猫', '抖音', 'POS']
    total_sales = df['应收金额'].sum()

    result = {}
    for ch in channels:
        ch_df = df[df['渠道'] == ch] if '渠道' in df.columns else pd.DataFrame()
        ch_sales = round(ch_df['应收金额'].sum(), 2) if not ch_df.empty else 0
        ch_qty = int(ch_df['销售数量'].sum()) if not ch_df.empty else 0
        ch_pct = round(ch_sales / total_sales * 100, 2) if total_sales > 0 else 0

        result[ch] = {
            '销售额': ch_sales,
            '销量': ch_qty,
            '占比': f'{ch_pct}%'
        }

    return result


def calc_category_top(df, top_n=3):
    """按品类维度统计销售额 top N"""
    df = df.copy()
    df['品类'] = df['商品编码'].apply(extract_category)

    cat_sales = df.groupby('品类')['应收金额'].sum().reset_index()
    cat_sales = cat_sales.sort_values('应收金额', ascending=False).head(top_n)

    result = []
    for _, row in cat_sales.iterrows():
        result.append({
            '品类代码': row['品类'],
            '销售额': round(row['应收金额'], 2)
        })
    return result


def calc_sku_top(df, top_n=3):
    """SKU 维度：畅销 top N 和滞销 top N（按销量排序）"""
    sku_sales = df.groupby('商品编码')['销售数量'].sum().reset_index()
    sku_sales = sku_sales.sort_values('销售数量', ascending=False)

    best = sku_sales.head(top_n)
    worst = sku_sales.tail(top_n).sort_values('销售数量', ascending=True)

    best_list = [{'商品编码': r['商品编码'], '销量': int(r['销售数量'])} for _, r in best.iterrows()]
    worst_list = [{'商品编码': r['商品编码'], '销量': int(r['销售数量'])} for _, r in worst.iterrows()]

    return {'畅销top3': best_list, '滞销top3': worst_list}


def find_previous_file(current_file):
    """根据当前文件名找到前一天的 raw 文件"""
    # 从文件名提取日期: raw_2026_08_05.xlsx
    basename = os.path.basename(current_file)
    match = basename.replace('raw_', '').replace('.xlsx', '')
    try:
        current_date = datetime.strptime(match, '%Y_%m_%d')
    except ValueError:
        return None, None

    prev_date = current_date - timedelta(days=1)
    prev_filename = f"raw_{prev_date.strftime('%Y_%m_%d')}.xlsx"
    prev_path = os.path.join(os.path.dirname(current_file), prev_filename)

    return prev_path, current_date


def calc_dod_change(current_df, prev_file_path):
    """对比前一天数据，计算环比变化率"""
    if not prev_file_path or not os.path.exists(prev_file_path):
        return None

    prev_df = load_raw_data(prev_file_path)
    prev_df = clean_data(prev_df)

    cur_sales = current_df['应收金额'].sum()
    cur_qty = int(current_df['销售数量'].sum())
    prev_sales = prev_df['应收金额'].sum()
    prev_qty = int(prev_df['销售数量'].sum())

    def pct_change(cur, prev):
        """返回 (百分比字符串, 数值)"""
        if prev == 0:
            return ('N/A' if cur > 0 else '0.00%', None)
        val = round((cur - prev) / prev * 100, 2)
        return f'{val}%', val

    # 按渠道环比
    channels = ['天猫', '抖音', 'POS']
    channel_change = {}
    channel_change_raw = {}
    for ch in channels:
        cur_ch = current_df[current_df['渠道'] == ch]['应收金额'].sum() if '渠道' in current_df.columns else 0
        prev_ch = prev_df[prev_df['渠道'] == ch]['应收金额'].sum() if '渠道' in prev_df.columns else 0
        pct_str, pct_val = pct_change(cur_ch, prev_ch)
        channel_change[ch] = pct_str
        channel_change_raw[ch] = pct_val

    _, total_sales_pct = pct_change(cur_sales, prev_sales)
    _, total_qty_pct = pct_change(cur_qty, prev_qty)

    return {
        '对比日期': prev_df['销售日期'].iloc[0] if not prev_df.empty else 'N/A',
        '总销售额环比': pct_change(cur_sales, prev_sales)[0],
        '总销量环比': pct_change(cur_qty, prev_qty)[0],
        '渠道销售额环比': channel_change,
        '_raw': {
            '总销售额环比': total_sales_pct,
            '总销量环比': total_qty_pct,
            '渠道销售额环比': channel_change_raw
        }
    }


def calc_category_margin(df):
    """计算各品类毛利率"""
    df = df.copy()
    df['品类'] = df['商品编码'].apply(extract_category)

    cat_stats = df.groupby('品类').agg(
        销售额=('应收金额', 'sum'),
        成本=('扣减金额', 'sum')
    ).reset_index()

    result = []
    for _, row in cat_stats.iterrows():
        sales = row['销售额']
        cost = row['成本']
        margin = round((sales - cost) / sales * 100, 2) if sales > 0 else 0
        result.append({
            '品类代码': row['品类'],
            '销售额': round(sales, 2),
            '成本': round(cost, 2),
            '毛利率': margin
        })
    return result


def detect_anomalies(dod_change, category_margins):
    """
    异常检测：
    1. 渠道销售额环比下降超过20% → 异常
    2. 品类毛利率低于30% → 预警
    """
    anomalies = []
    warnings = []

    # 1. 渠道环比异常检测
    if dod_change and '_raw' in dod_change:
        raw = dod_change['_raw']
        for ch, pct in raw.get('渠道销售额环比', {}).items():
            if pct is not None and pct < -20:
                anomalies.append({
                    '类型': '渠道销售额异常',
                    '对象': ch,
                    '详情': f'环比下降 {abs(pct)}%',
                    '阈值': '下降超过20%'
                })

    # 2. 品类毛利率预警
    for cat in category_margins:
        if cat['毛利率'] < 30:
            warnings.append({
                '类型': '品类毛利率预警',
                '对象': cat['品类代码'],
                '详情': f'毛利率 {cat["毛利率"]}%',
                '阈值': '低于30%'
            })

    return anomalies, warnings


def save_anomalies_md(anomalies, warnings, report_date, output_dir):
    """将异常和预警输出为 Markdown 文件"""
    date_str = report_date.replace('-', '_')
    output_file = os.path.join(output_dir, f'anomalies_{date_str}.md')

    lines = [
        f'# 异常检测报告',
        f'',
        f'**报告日期:** {report_date}  ',
        f'**生成时间:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        f'',
    ]

    if not anomalies and not warnings:
        lines.append('✅ **未检测到异常或预警项**')
    else:
        if anomalies:
            lines.append('## 🔴 异常项')
            lines.append('')
            lines.append('| 类型 | 对象 | 详情 | 阈值 |')
            lines.append('|------|------|------|------|')
            for item in anomalies:
                lines.append(f'| {item["类型"]} | {item["对象"]} | {item["详情"]} | {item["阈值"]} |')
            lines.append('')

        if warnings:
            lines.append('## 🟡 预警项')
            lines.append('')
            lines.append('| 类型 | 对象 | 详情 | 阈值 |')
            lines.append('|------|------|------|------|')
            for item in warnings:
                lines.append(f'| {item["类型"]} | {item["对象"]} | {item["详情"]} | {item["阈值"]} |')
            lines.append('')

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return output_file


def main():
    # 定位最新的 raw 文件
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    raw_files = sorted(glob.glob(os.path.join(data_dir, 'raw_*.xlsx')))

    if not raw_files:
        print('错误: data 目录下未找到 raw_*.xlsx 文件')
        return

    current_file = raw_files[-1]
    print(f'读取文件: {current_file}')

    # 1. 加载 & 清洗
    df = load_raw_data(current_file)
    print(f'原始数据: {len(df)} 行')

    df = clean_data(df)
    print(f'清洗后: {len(df)} 行')

    # 从文件名提取报告日期
    basename = os.path.basename(current_file).replace('raw_', '').replace('.xlsx', '')
    report_date = datetime.strptime(basename, '%Y_%m_%d').strftime('%Y-%m-%d')

    # 2. 全渠道汇总
    total_summary = calc_total_summary(df)

    # 3. 渠道拆分
    channel_summary = calc_channel_summary(df)

    # 4. 品类 top3
    category_top3 = calc_category_top(df, top_n=3)

    # 4.1 品类毛利率
    category_margins = calc_category_margin(df)

    # 5. SKU 畅销/滞销 top3
    sku_top = calc_sku_top(df, top_n=3)

    # 6. 环比
    prev_file, _ = find_previous_file(current_file)
    dod_change = calc_dod_change(df, prev_file)

    # 6.1 异常检测
    anomalies, warnings = detect_anomalies(dod_change, category_margins)

    # 组装报告
    report = {
        '报告日期': report_date,
        '生成时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '数据概览': {
            '总记录数': len(df),
            '渠道列表': sorted(df['渠道'].unique().tolist()) if '渠道' in df.columns else []
        },
        '全渠道汇总': total_summary,
        '渠道明细': channel_summary,
        '品类销售额top3': category_top3,
        '品类毛利率': category_margins,
        'SKU排名': sku_top,
        '环比变化': {k: v for k, v in dod_change.items() if k != '_raw'} if dod_change else '无前一天数据文件，无法计算环比',
        '异常检测': {
            '异常项数量': len(anomalies),
            '预警项数量': len(warnings)
        }
    }

    # 7. 保存 JSON
    output_dir = os.path.join(os.path.dirname(__file__), 'output')
    os.makedirs(output_dir, exist_ok=True)

    output_file = os.path.join(output_dir, f'report_data_{basename}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, cls=ReportEncoder)

    # 8. 保存异常报告 Markdown
    anomalies_file = save_anomalies_md(anomalies, warnings, report_date, output_dir)

    print(f'\n报告已保存: {output_file}')
    print(f'异常报告: {anomalies_file}')
    print(json.dumps(report, ensure_ascii=False, indent=2, cls=ReportEncoder))

    if anomalies:
        print(f'\n🔴 发现 {len(anomalies)} 个异常项')
    if warnings:
        print(f'🟡 发现 {len(warnings)} 个预警项')


if __name__ == '__main__':
    main()
