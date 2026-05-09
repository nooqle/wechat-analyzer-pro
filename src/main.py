#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_analyzer.py — 微信聊天记录分析工具主程序
支持私聊分析、群聊分析、群成员两两对比

用法：
  # 私聊分析
  python main.py --contact "联系人名"

  # 群聊概览
  python main.py --group "群名"

  # 群成员两两对比
  python main.py --group "群名" --pair "成员1" "成员2"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

# 导入自定义模块
from export_contact import (
    get_db_dir, list_contacts, find_contact, get_self_wxid,
    export_messages, export_group_messages, extract_pair_from_group
)
from personality import analyze_communication_style, generate_remark_tags_batch


def setup_chinese_font():
    """设置中文字体"""
    plt.rcParams['font.sans-serif'] = ['SimHei', 'STSong', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


def analyze_private_chat(db_dir: Path, contact_name: str, output_dir: Path) -> Dict:
    """分析私聊"""
    print(f"\n📊 分析私聊：{contact_name}")

    # 查找联系人
    matches = find_contact(db_dir, contact_name, is_group=False)
    if not matches:
        print(f"❌ 找不到联系人：{contact_name}")
        return {}

    if len(matches) > 1:
        print(f"找到 {len(matches)} 个匹配联系人：")
        for i, (username, remark, nick) in enumerate(matches):
            print(f"  [{i+1}] {remark or nick} ({username})")
        return {}

    username, remark, nick = matches[0]
    actual_name = remark or nick or username

    # 获取自己的 wxid
    self_wxid = get_self_wxid(db_dir)
    if not self_wxid:
        print("❌ 无法确定自己的微信 ID")
        return {}

    # 导出消息
    output_csv = output_dir / f'export_{actual_name}.csv'
    msg_count = export_messages(db_dir, username, actual_name, self_wxid, output_csv)

    # 分析
    json_path = output_csv.with_suffix('.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 分离双方消息
    self_msgs = [m['content'] for m in data['messages'] if m['is_sender'] == 1]
    partner_msgs = [m['content'] for m in data['messages'] if m['is_sender'] == 0]

    # 人格分析
    self_result = analyze_communication_style(self_msgs, '我')
    partner_result = analyze_communication_style(partner_msgs, actual_name)

    # 保存结果
    results = {
        'self': self_result,
        'partner': partner_result,
        'stats': {
            'total_messages': msg_count,
            'self_messages': len(self_msgs),
            'partner_messages': len(partner_msgs),
            'time_range': [
                data['messages'][0]['datetime'] if data['messages'] else '',
                data['messages'][-1]['datetime'] if data['messages'] else ''
            ]
        }
    }

    result_path = output_dir / 'analysis_result.json'
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 生成报告
    generate_html_report(results, output_dir)

    # 打印好友备注推荐
    print("\n📋 好友备注推荐：")
    if partner_result and 'style' in partner_result:
        tag = partner_result['style'].get('remark_tag', '')
        print(f"  {actual_name}: {tag}")

    return results


def analyze_group(db_dir: Path, group_name: str, output_dir: Path) -> Dict:
    """分析群聊概览"""
    print(f"\n📊 分析群聊：{group_name}")

    # 查找群
    matches = find_contact(db_dir, group_name, is_group=True)
    if not matches:
        print(f"❌ 找不到群聊：{group_name}")
        return {}

    if len(matches) > 1:
        print(f"找到 {len(matches)} 个匹配群聊：")
        for i, (username, remark, nick) in enumerate(matches):
            print(f"  [{i+1}] {remark or nick} ({username})")
        return {}

    username, remark, nick = matches[0]
    actual_name = remark or nick or username

    # 导出群聊消息
    output_csv = output_dir / f'export_{actual_name}.csv'
    msg_count, member_stats = export_group_messages(db_dir, username, actual_name, output_csv)

    # 分析每个成员
    json_path = output_csv.with_suffix('.json')
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    member_results = {}
    for member_name in member_stats.keys():
        member_msgs = [
            m['content'] for m in data['messages']
            if m.get('actual_sender') == member_name and m['type'] == 1
        ]
        if member_msgs:
            member_results[member_name] = analyze_communication_style(member_msgs, member_name)

    # 保存结果
    results = {
        'group_name': actual_name,
        'stats': {
            'total_messages': msg_count,
            'member_count': len(member_stats),
            'member_stats': member_stats
        },
        'member_analysis': member_results
    }

    result_path = output_dir / 'group_analysis.json'
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 生成群聊报告
    generate_group_report(results, output_dir)

    # 打印好友备注推荐
    print("\n📋 群成员备注推荐：")
    tags = generate_remark_tags_batch(member_results)
    for member, tag in tags.items():
        print(f"  {member}: {tag}")

    return results


def analyze_pair(db_dir: Path, group_name: str, member1: str, member2: str, output_dir: Path) -> Dict:
    """分析群聊中两个人的对话"""
    print(f"\n📊 分析群成员对比：{member1} vs {member2}")

    # 先导出群聊数据
    matches = find_contact(db_dir, group_name, is_group=True)
    if not matches:
        print(f"❌ 找不到群聊：{group_name}")
        return {}

    username, remark, nick = matches[0]
    actual_group_name = remark or nick or username

    # 导出群聊消息
    group_csv = output_dir / f'export_{actual_group_name}.csv'
    export_group_messages(db_dir, username, actual_group_name, group_csv)

    # 提取两人对话
    group_json = group_csv.with_suffix('.json')
    pair_csv = output_dir / f'export_{member1}_vs_{member2}.csv'
    msg_count = extract_pair_from_group(group_json, member1, member2, pair_csv)

    # 分析
    pair_json = pair_csv.with_suffix('.json')
    with open(pair_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 分离两人消息
    msgs1 = [m['content'] for m in data['messages'] if m['sender'] == member1]
    msgs2 = [m['content'] for m in data['messages'] if m['sender'] == member2]

    # 人格分析
    result1 = analyze_communication_style(msgs1, member1)
    result2 = analyze_communication_style(msgs2, member2)

    # 保存结果
    results = {
        'member1': {'name': member1, 'analysis': result1, 'message_count': len(msgs1)},
        'member2': {'name': member2, 'analysis': result2, 'message_count': len(msgs2)},
        'stats': {
            'total_messages': msg_count,
            'time_range': [
                data['messages'][0]['datetime'] if data['messages'] else '',
                data['messages'][-1]['datetime'] if data['messages'] else ''
            ]
        }
    }

    result_path = output_dir / f'{member1}_vs_{member2}_analysis.json'
    with open(result_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 生成对比报告
    generate_pair_report(results, output_dir)

    # 打印好友备注推荐
    print("\n📋 好友备注推荐：")
    if result1 and 'style' in result1:
        print(f"  {member1}: {result1['style'].get('remark_tag', '')}")
    if result2 and 'style' in result2:
        print(f"  {member2}: {result2['style'].get('remark_tag', '')}")

    return results


def generate_html_report(results: Dict, output_dir: Path):
    """生成私聊 HTML 报告"""
    html_path = output_dir / 'report.html'

    self_result = results.get('self', {})
    partner_result = results.get('partner', {})
    stats = results.get('stats', {})

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>聊天分析报告</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .header h1 {{ margin: 0 0 10px 0; }}
        .profile {{ display: flex; gap: 20px; }}
        .profile-card {{ flex: 1; padding: 20px; border-radius: 8px; }}
        .profile-card.self {{ background: #e3f2fd; }}
        .profile-card.partner {{ background: #fce4ec; }}
        .mbti {{ font-size: 28px; font-weight: bold; margin: 10px 0; }}
        .remark-tag {{ background: #fff3e0; border: 1px solid #ffb74d; padding: 8px 16px; border-radius: 20px; display: inline-block; margin-top: 10px; }}
        .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-top: 20px; }}
        .stat-item {{ text-align: center; padding: 16px; background: #f5f5f5; border-radius: 8px; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💬 聊天分析报告</h1>
            <p>{stats.get('time_range', ['', ''])[0]} ~ {stats.get('time_range', ['', ''])[1]}</p>
        </div>

        <div class="card">
            <h2>👥 人格对比</h2>
            <div class="profile">
                <div class="profile-card self">
                    <h3>我</h3>
                    <div class="mbti" style="color: #1976D2;">{self_result.get('mbti', {}).get('type', '-')}</div>
                    <p>{self_result.get('mbti', {}).get('name', '')}</p>
                    <p style="font-size: 12px; color: #666;">{self_result.get('style', {}).get('one_line', '')}</p>
                </div>
                <div class="profile-card partner">
                    <h3>{partner_result.get('nickname', '对方')}</h3>
                    <div class="mbti" style="color: #C2185B;">{partner_result.get('mbti', {}).get('type', '-')}</div>
                    <p>{partner_result.get('mbti', {}).get('name', '')}</p>
                    <p style="font-size: 12px; color: #666;">{partner_result.get('style', {}).get('one_line', '')}</p>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📋 好友备注推荐</h2>
            <p>可直接复制到微信联系人备注中：</p>
            <div class="remark-tag">{partner_result.get('style', {}).get('remark_tag', '')}</div>
        </div>

        <div class="card">
            <h2>📊 统计数据</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value">{stats.get('total_messages', 0):,}</div>
                    <div class="stat-label">消息总数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats.get('self_messages', 0):,}</div>
                    <div class="stat-label">我的消息</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats.get('partner_messages', 0):,}</div>
                    <div class="stat-label">对方消息</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>'''

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n📄 报告已生成：{html_path}")


def generate_group_report(results: Dict, output_dir: Path):
    """生成群聊 HTML 报告"""
    html_path = output_dir / 'group_report.html'

    group_name = results.get('group_name', '')
    stats = results.get('stats', {})
    member_analysis = results.get('member_analysis', {})

    member_cards = ''
    for name, analysis in member_analysis.items():
        mbti = analysis.get('mbti', {}).get('type', '-')
        tag = analysis.get('style', {}).get('remark_tag', '')
        member_cards += f'''
        <div class="member-card">
            <h3>{name}</h3>
            <div class="mbti">{mbti}</div>
            <p style="font-size: 12px;">{tag}</p>
            <div class="remark-tag" onclick="copyToClipboard('{tag}')">📋 复制备注</div>
        </div>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{group_name} - 群聊分析</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; }}
        .member-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; }}
        .member-card {{ padding: 20px; background: #f8f9fa; border-radius: 8px; text-align: center; }}
        .mbti {{ font-size: 24px; font-weight: bold; color: #667eea; margin: 10px 0; }}
        .remark-tag {{ background: #fff3e0; border: 1px solid #ffb74d; padding: 6px 12px; border-radius: 16px; font-size: 12px; cursor: pointer; margin-top: 10px; }}
        .remark-tag:hover {{ background: #ffe0b2; }}
        .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
        .stat-item {{ text-align: center; padding: 16px; background: #f5f5f5; border-radius: 8px; }}
        .stat-value {{ font-size: 28px; font-weight: bold; color: #667eea; }}
        .stat-label {{ font-size: 12px; color: #666; }}
    </style>
    <script>
    function copyToClipboard(text) {{
        navigator.clipboard.writeText(text).then(() => {{
            alert('已复制: ' + text);
        }});
    }}
    </script>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👥 {group_name}</h1>
            <p>群聊分析报告</p>
        </div>

        <div class="card">
            <h2>📊 群聊概况</h2>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-value">{stats.get('total_messages', 0):,}</div>
                    <div class="stat-label">消息总数</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">{stats.get('member_count', 0)}</div>
                    <div class="stat-label">群成员数</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>👥 成员分析</h2>
            <div class="member-grid">
                {member_cards}
            </div>
        </div>

        <div class="card">
            <h2>📋 批量备注推荐</h2>
            <p>可复制到微信联系人备注：</p>
            <pre style="background: #f5f5f5; padding: 16px; border-radius: 8px; overflow-x: auto;">
{chr(10).join(f'{name}: {a.get("style", {}).get("remark_tag", "")}' for name, a in member_analysis.items())}
            </pre>
        </div>
    </div>
</body>
</html>'''

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n📄 群聊报告已生成：{html_path}")


def generate_pair_report(results: Dict, output_dir: Path):
    """生成群成员对比 HTML 报告"""
    m1 = results.get('member1', {})
    m2 = results.get('member2', {})
    stats = results.get('stats', {})

    html_path = output_dir / f'{m1.get("name", "member1")}_vs_{m2.get("name", "member2")}_report.html'

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>{m1.get('name', '')} vs {m2.get('name', '')} - 对比分析</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .card {{ background: white; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 12px; margin-bottom: 20px; text-align: center; }}
        .vs-badge {{ display: inline-block; background: rgba(255,255,255,0.2); padding: 4px 16px; border-radius: 20px; margin: 10px 0; font-size: 18px; }}
        .profile {{ display: flex; gap: 20px; }}
        .profile-card {{ flex: 1; padding: 20px; border-radius: 8px; text-align: center; }}
        .profile-card.left {{ background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); }}
        .profile-card.right {{ background: linear-gradient(135deg, #fce4ec 0%, #f8bbd9 100%); }}
        .mbti {{ font-size: 32px; font-weight: bold; margin: 10px 0; }}
        .remark-tag {{ background: #fff3e0; border: 1px solid #ffb74d; padding: 8px 16px; border-radius: 20px; display: inline-block; margin-top: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>👥 群成员对比分析</h1>
            <div class="vs-badge">{m1.get('name', '')} vs {m2.get('name', '')}</div>
            <p style="opacity: 0.8; margin-top: 10px;">{stats.get('time_range', ['', ''])[0]} ~ {stats.get('time_range', ['', ''])[1]}</p>
        </div>

        <div class="card">
            <h2>🧠 人格对比</h2>
            <div class="profile">
                <div class="profile-card left">
                    <h3>{m1.get('name', '')}</h3>
                    <div class="mbti" style="color: #1976D2;">{m1.get('analysis', {}).get('mbti', {}).get('type', '-')}</div>
                    <p>{m1.get('analysis', {}).get('mbti', {}).get('name', '')}</p>
                    <p style="font-size: 12px; color: #666; margin-top: 10px;">{m1.get('analysis', {}).get('style', {}).get('one_line', '')}</p>
                    <div class="remark-tag">📋 {m1.get('analysis', {}).get('style', {}).get('remark_tag', '')}</div>
                </div>
                <div class="profile-card right">
                    <h3>{m2.get('name', '')}</h3>
                    <div class="mbti" style="color: #C2185B;">{m2.get('analysis', {}).get('mbti', {}).get('type', '-')}</div>
                    <p>{m2.get('analysis', {}).get('mbti', {}).get('name', '')}</p>
                    <p style="font-size: 12px; color: #666; margin-top: 10px;">{m2.get('analysis', {}).get('style', {}).get('one_line', '')}</p>
                    <div class="remark-tag">📋 {m2.get('analysis', {}).get('style', {}).get('remark_tag', '')}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>📋 好友备注推荐</h2>
            <pre style="background: #f5f5f5; padding: 16px; border-radius: 8px;">
{m1.get('name', '')}: {m1.get('analysis', {}).get('style', {}).get('remark_tag', '')}
{m2.get('name', '')}: {m2.get('analysis', {}).get('style', {}).get('remark_tag', '')}
            </pre>
        </div>
    </div>
</body>
</html>'''

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n📄 对比报告已生成：{html_path}")


def main():
    parser = argparse.ArgumentParser(description='微信聊天记录分析工具')
    parser.add_argument('--contact', help='私聊联系人名称')
    parser.add_argument('--group', help='群聊名称')
    parser.add_argument('--pair', nargs=2, metavar=('MEMBER1', 'MEMBER2'), help='群成员两两对比')
    parser.add_argument('--list-contacts', action='store_true', help='列出所有联系人')
    parser.add_argument('--list-groups', action='store_true', help='列出所有群聊')
    parser.add_argument('--output', default='./output', help='输出目录')
    parser.add_argument('--db-dir', help='解密数据库目录')
    args = parser.parse_args()

    # 设置中文字体
    setup_chinese_font()

    # 获取数据库目录
    db_dir = Path(args.db_dir) if args.db_dir else get_db_dir()

    # 创建输出目录
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 列出联系人/群聊
    if args.list_contacts:
        list_contacts(db_dir, is_group=False)
        return
    if args.list_groups:
        list_contacts(db_dir, is_group=True)
        return

    # 私聊分析
    if args.contact and not args.group:
        analyze_private_chat(db_dir, args.contact, output_dir)
        return

    # 群聊分析
    if args.group:
        if args.pair:
            # 群成员两两对比
            analyze_pair(db_dir, args.group, args.pair[0], args.pair[1], output_dir)
        else:
            # 群聊概览
            analyze_group(db_dir, args.group, output_dir)
        return

    parser.print_help()


if __name__ == '__main__':
    main()
