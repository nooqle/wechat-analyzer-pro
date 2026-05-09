#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_contact.py — 从解密后的微信 SQLite 数据库导出联系人消息
支持 macOS 和 Windows 微信数据库

用法：
  python export_contact.py --list-contacts
  python export_contact.py --contact "姓名或备注"
  python export_contact.py --contact "姓名" --output ./my_chat.csv
  python export_contact.py --group "群名"  # 导出群聊
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import platform
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict

# 配置文件路径
_SCRIPT_DIR = Path(__file__).parent.parent
_CONFIG_PATH = _SCRIPT_DIR / 'config.json'


def load_config() -> dict:
    """加载配置文件"""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _looks_like_db_storage(path: Path) -> bool:
    """检查是否是有效的数据库目录"""
    return (
        (path / 'contact' / 'contact.db').exists() and
        (path / 'message' / 'message_0.db').exists()
    )


def _resolve_db_dir(base: Path) -> Optional[Path]:
    """解析数据库目录，兼容多种路径格式"""
    if _looks_like_db_storage(base):
        return base

    candidates = []
    # macOS 路径模式
    for pattern in ('wxid_*/db_storage', '*/db_storage'):
        for candidate in base.glob(pattern):
            if not candidate.is_dir() or not _looks_like_db_storage(candidate):
                continue
            msg_db = candidate / 'message' / 'message_0.db'
            mtime = msg_db.stat().st_mtime if msg_db.exists() else 0
            candidates.append((mtime, candidate))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)
    chosen = candidates[0][1]
    print(f"[*] 自动选择解密数据库目录：{chosen}")
    return chosen


def get_db_dir() -> Path:
    """获取解密数据库目录"""
    cfg = load_config()
    db_dir = cfg.get('decrypted_db_dir', '')
    if db_dir:
        p = Path(os.path.expanduser(db_dir))
        resolved = _resolve_db_dir(p) if p.exists() else None
        if resolved is not None:
            return resolved

    # 默认路径
    system = platform.system()
    if system == 'Darwin':  # macOS
        default = Path.home() / 'Documents/wechat-db-decrypt-macos/decrypted'
    else:  # Windows
        default = Path.home() / 'Documents/wechat-db-decrypt-windows/decrypted'

    resolved = _resolve_db_dir(default) if default.exists() else None
    if resolved is not None:
        return resolved

    print("❌ 找不到解密数据库目录。请检查 config.json 中的 decrypted_db_dir 路径。")
    sys.exit(1)


def md5(text: str) -> str:
    """计算 MD5 哈希"""
    return hashlib.md5(text.encode()).hexdigest()


def get_message_dbs(db_dir: Path) -> List[Path]:
    """获取所有消息数据库文件"""
    msg_dir = db_dir / 'message'
    if not msg_dir.exists():
        return []

    paths = []
    for path in msg_dir.glob('message_*.db'):
        m = re.fullmatch(r'message_(\d+)\.db', path.name)
        if m:
            paths.append((int(m.group(1)), path))

    paths.sort(key=lambda item: item[0])
    return [path for _, path in paths]


def list_contacts(db_dir: Path, is_group: bool = False):
    """列出所有联系人或群聊"""
    contact_db = db_dir / 'contact' / 'contact.db'
    conn = sqlite3.connect(contact_db)

    if is_group:
        # 只列出群聊
        rows = conn.execute(
            "SELECT username, remark, nick_name FROM contact "
            "WHERE username LIKE '%@chatroom' "
            "ORDER BY remark, nick_name"
        ).fetchall()
    else:
        # 列出个人联系人（排除群聊）
        rows = conn.execute(
            "SELECT username, remark, nick_name FROM contact "
            "WHERE local_type != 4 AND username NOT LIKE '%@chatroom' "
            "ORDER BY remark, nick_name"
        ).fetchall()

    conn.close()

    print(f"{'备注名':<20} {'昵称':<20} {'微信ID'}")
    print("-" * 60)
    for username, remark, nick in rows:
        display_name = remark or nick or username
        print(f"{(remark or ''):<20} {(nick or ''):<20} {username}")

    return rows


def find_contact(db_dir: Path, name: str, is_group: bool = False) -> List[Tuple]:
    """查找联系人"""
    contact_db = db_dir / 'contact' / 'contact.db'
    conn = sqlite3.connect(contact_db)

    if is_group:
        rows = conn.execute(
            "SELECT username, remark, nick_name FROM contact "
            "WHERE username LIKE '%@chatroom' AND (remark LIKE ? OR nick_name LIKE ? OR username LIKE ?)",
            (f'%{name}%', f'%{name}%', f'%{name}%')
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT username, remark, nick_name FROM contact "
            "WHERE (remark LIKE ? OR nick_name LIKE ? OR username LIKE ?) AND username NOT LIKE '%@chatroom'",
            (f'%{name}%', f'%{name}%', f'%{name}%')
        ).fetchall()

    conn.close()
    return rows


def get_self_wxid(db_dir: Path) -> str:
    """推断自己的 wxid：通过消息表中发送消息最多的账号来判断"""
    msg_dbs = get_message_dbs(db_dir)
    if not msg_dbs:
        return None

    sender_counts = {}
    for msg_db in msg_dbs[:3]:
        try:
            conn = sqlite3.connect(msg_db)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
            ).fetchall()]

            for table in tables[:10]:
                try:
                    rows = conn.execute(
                        f"SELECT real_sender_id, COUNT(*) FROM {table} GROUP BY real_sender_id"
                    ).fetchall()
                    for sender_id, count in rows:
                        sender_counts[sender_id] = sender_counts.get(sender_id, 0) + count
                except:
                    pass
            conn.close()
        except:
            pass

    if sender_counts:
        max_sender = max(sender_counts.items(), key=lambda x: x[1])
        sender_id = max_sender[0]

        for msg_db in msg_dbs[:1]:
            try:
                conn = sqlite3.connect(msg_db)
                row = conn.execute(
                    "SELECT user_name FROM Name2Id WHERE rowid = ?", (sender_id,)
                ).fetchone()
                conn.close()
                if row and row[0]:
                    return row[0]
            except:
                pass

    return None


def get_sender_rowids(msg_db: Path, self_wxid: str, contact_wxid: str) -> Tuple[Optional[int], Optional[int]]:
    """获取发送者在 Name2Id 表中的 rowid"""
    conn = sqlite3.connect(msg_db)
    rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
    conn.close()

    self_id, contact_id = None, None
    for rowid, user_name in rows:
        if user_name == self_wxid:
            self_id = rowid
        if user_name == contact_wxid:
            contact_id = rowid

    return self_id, contact_id


def decode_content(raw) -> str:
    """解码消息内容"""
    if raw is None:
        return ''
    if isinstance(raw, bytes):
        try:
            import zstd
            ZSTD_MAGIC = b'\x28\xb5\x2f\xfd'
            if raw[:4] == ZSTD_MAGIC:
                try:
                    return zstd.decompress(raw).decode('utf-8', errors='replace')
                except:
                    pass
        except ImportError:
            pass
        return raw.decode('utf-8', errors='replace')
    return str(raw)


def export_messages(db_dir: Path, contact_wxid: str, contact_name: str,
                    self_wxid: str, output_path: Path) -> int:
    """导出聊天消息"""
    table = f"Msg_{md5(contact_wxid)}"
    msg_dbs = get_message_dbs(db_dir)

    if not msg_dbs:
        print("❌ 找不到已解密的 message_N.db 文件。")
        sys.exit(1)

    merged_rows = []
    matched_dbs = []

    for msg_db in msg_dbs:
        conn = sqlite3.connect(msg_db)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in tables:
            conn.close()
            continue

        self_id, _ = get_sender_rowids(msg_db, self_wxid, contact_wxid)
        rows = conn.execute(
            f"SELECT create_time, real_sender_id, local_type, message_content "
            f"FROM {table} ORDER BY create_time ASC"
        ).fetchall()
        conn.close()

        matched_dbs.append(msg_db.name)
        merged_rows.extend((create_time, sender_id, local_type, content, self_id)
                           for create_time, sender_id, local_type, content in rows)

    if not merged_rows:
        print(f"❌ 找不到消息表 {table}，可能没有与此联系人的消息记录。")
        sys.exit(1)

    merged_rows.sort(key=lambda row: row[0])
    msg_count = len(merged_rows)
    print(f"[*] 找到 {msg_count} 条消息（来自 {', '.join(matched_dbs)}）")

    json_records = []

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'datetime', 'sender', 'is_sender', 'type', 'content'])
        for create_time, sender_id, local_type, content, self_id in merged_rows:
            dt = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            is_self = 1 if sender_id == self_id else 0
            sender_name = '我' if is_self else contact_name
            text = decode_content(content)
            writer.writerow([create_time, dt, sender_name, is_self, local_type, text])
            json_records.append({
                'timestamp': int(create_time),
                'datetime': dt,
                'sender': sender_name,
                'is_sender': int(is_self),
                'type': int(local_type),
                'content': text,
            })

    # 保存 JSON
    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'format': 'wechat_chat_export_v1',
            'contact_wxid': contact_wxid,
            'contact_name': contact_name,
            'self_wxid': self_wxid,
            'message_count': msg_count,
            'source_databases': matched_dbs,
            'messages': json_records,
        }, f, ensure_ascii=False, indent=2)

    print(f"EXPORT_PATH:{output_path}")
    print(f"JSON_PATH:{json_path}")
    return msg_count


def export_group_messages(db_dir: Path, group_wxid: str, group_name: str,
                          output_path: Path) -> Tuple[int, Dict[str, int]]:
    """导出群聊消息，返回消息总数和成员发言统计"""
    table = f"Msg_{md5(group_wxid)}"
    msg_dbs = get_message_dbs(db_dir)

    if not msg_dbs:
        print("❌ 找不到已解密的 message_N.db 文件。")
        sys.exit(1)

    merged_rows = []
    matched_dbs = []

    for msg_db in msg_dbs:
        conn = sqlite3.connect(msg_db)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in tables:
            conn.close()
            continue

        rows = conn.execute(
            f"SELECT create_time, real_sender_id, local_type, message_content "
            f"FROM {table} ORDER BY create_time ASC"
        ).fetchall()
        conn.close()

        matched_dbs.append(msg_db.name)
        merged_rows.extend(rows)

    if not merged_rows:
        print(f"❌ 找不到群聊消息表 {table}")
        sys.exit(1)

    merged_rows.sort(key=lambda row: row[0])
    msg_count = len(merged_rows)
    print(f"[*] 找到 {msg_count} 条群聊消息")

    # 解析群成员
    member_stats = {}
    json_records = []

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'datetime', 'sender', 'is_sender', 'type', 'content'])

        for create_time, sender_id, local_type, content in merged_rows:
            dt = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M:%S')
            text = decode_content(content)

            # 群聊消息格式: "username:\n消息内容"
            sender_name = group_name
            is_self = 0
            actual_sender = None

            if text:
                match = re.match(r'^([^:\n]+):\n(.*)$', text, re.DOTALL)
                if match:
                    actual_sender = match.group(1)
                    sender_name = actual_sender
                    text_content = match.group(2)
                else:
                    text_content = text
            else:
                text_content = ''

            writer.writerow([create_time, dt, sender_name, is_self, local_type, text])

            if actual_sender:
                member_stats[actual_sender] = member_stats.get(actual_sender, 0) + 1

            json_records.append({
                'timestamp': int(create_time),
                'datetime': dt,
                'sender': sender_name,
                'is_sender': 0,
                'type': int(local_type),
                'content': text,
                'actual_sender': actual_sender,
            })

    # 保存 JSON
    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'format': 'wechat_group_export_v1',
            'group_wxid': group_wxid,
            'group_name': group_name,
            'message_count': msg_count,
            'member_count': len(member_stats),
            'member_stats': member_stats,
            'source_databases': matched_dbs,
            'messages': json_records,
        }, f, ensure_ascii=False, indent=2)

    print(f"EXPORT_PATH:{output_path}")
    print(f"JSON_PATH:{json_path}")

    # 打印成员统计
    print(f"\n[*] 群成员发言统计：")
    for member, count in sorted(member_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"    {member}: {count} 条")

    return msg_count, member_stats


def extract_pair_from_group(group_json_path: Path, member1: str, member2: str,
                            output_path: Path) -> int:
    """从群聊数据中提取两个人的对话"""
    with open(group_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    messages = []
    for msg in data['messages']:
        if msg.get('type') != 1:
            continue

        actual_sender = msg.get('actual_sender')
        if actual_sender not in [member1, member2]:
            continue

        messages.append({
            'timestamp': msg['timestamp'],
            'datetime': msg['datetime'],
            'sender': actual_sender,
            'is_sender': 1 if actual_sender == member1 else 0,
            'type': msg['type'],
            'content': msg['content'],
        })

    messages.sort(key=lambda x: x['timestamp'])

    # 保存
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'datetime', 'sender', 'is_sender', 'type', 'content'])
        for msg in messages:
            writer.writerow([
                msg['timestamp'], msg['datetime'], msg['sender'],
                msg['is_sender'], msg['type'], msg['content']
            ])

    json_path = output_path.with_suffix('.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'format': 'wechat_chat_export_v1',
            'contact_wxid': member2,
            'contact_name': member2,
            'self_wxid': member1,
            'message_count': len(messages),
            'source_databases': [group_json_path.name],
            'messages': messages,
        }, f, ensure_ascii=False, indent=2)

    print(f"[*] 提取 {member1} vs {member2}: {len(messages)} 条消息")
    print(f"EXPORT_PATH:{output_path}")
    return len(messages)


def get_self_nick(db_dir: Path, self_wxid: str) -> Optional[str]:
    """获取自己的昵称"""
    try:
        contact_db = db_dir / 'contact' / 'contact.db'
        conn = sqlite3.connect(contact_db)
        row = conn.execute(
            "SELECT nick_name FROM contact WHERE username = ?", (self_wxid,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    except:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(description='导出微信聊天记录')
    parser.add_argument('--contact', help='联系人备注名或昵称')
    parser.add_argument('--group', help='群聊名称')
    parser.add_argument('--list-contacts', action='store_true', help='列出所有联系人')
    parser.add_argument('--list-groups', action='store_true', help='列出所有群聊')
    parser.add_argument('--output', help='输出 CSV 路径')
    parser.add_argument('--db-dir', help='解密数据库目录')
    parser.add_argument('--extract-pair', nargs=2, metavar=('MEMBER1', 'MEMBER2'),
                        help='从群聊中提取两个人的对话')
    parser.add_argument('--group-json', help='群聊 JSON 文件路径（用于 --extract-pair）')
    args = parser.parse_args()

    db_dir = Path(os.path.expanduser(args.db_dir)) if args.db_dir else get_db_dir()

    if args.list_contacts:
        list_contacts(db_dir, is_group=False)
        return

    if args.list_groups:
        list_contacts(db_dir, is_group=True)
        return

    if args.extract_pair:
        if not args.group_json:
            print("❌ --extract-pair 需要配合 --group-json 使用")
            sys.exit(1)
        member1, member2 = args.extract_pair
        output_path = Path(args.output) if args.output else _SCRIPT_DIR / f'export_{member1}_vs_{member2}.csv'
        extract_pair_from_group(Path(args.group_json), member1, member2, output_path)
        return

    if args.group:
        matches = find_contact(db_dir, args.group, is_group=True)
        if not matches:
            print(f"❌ 找不到群聊：{args.group}")
            print("提示：使用 --list-groups 查看所有群聊")
            sys.exit(1)

        if len(matches) > 1:
            print(f"找到 {len(matches)} 个匹配群聊：")
            for i, (username, remark, nick) in enumerate(matches):
                print(f"  [{i+1}] {remark or nick} ({username})")
            choice = input("请输入编号：").strip()
            try:
                idx = int(choice) - 1
                username, remark, nick = matches[idx]
            except (ValueError, IndexError):
                print("无效选择")
                sys.exit(1)
        else:
            username, remark, nick = matches[0]

        group_name = remark or nick or username
        print(f"[*] 分析群聊：{group_name} ({username})")

        if args.output:
            output_path = Path(args.output)
        else:
            safe_name = group_name.encode('ascii', 'ignore').decode() or 'group'
            safe_name = safe_name.replace('/', '_').replace(' ', '_')[:20] or 'group'
            output_path = _SCRIPT_DIR / f'export_{safe_name}.csv'

        export_group_messages(db_dir, username, group_name, output_path)
        return

    if not args.contact:
        parser.print_help()
        sys.exit(1)

    matches = find_contact(db_dir, args.contact, is_group=False)
    if not matches:
        print(f"❌ 找不到联系人：{args.contact}")
        print("提示：使用 --list-contacts 查看所有联系人")
        sys.exit(1)

    if len(matches) > 1:
        print(f"找到 {len(matches)} 个匹配联系人：")
        for i, (username, remark, nick) in enumerate(matches):
            print(f"  [{i+1}] {remark or nick} ({username})")
        choice = input("请输入编号：").strip()
        try:
            idx = int(choice) - 1
            username, remark, nick = matches[idx]
        except (ValueError, IndexError):
            print("无效选择")
            sys.exit(1)
    else:
        username, remark, nick = matches[0]

    contact_name = remark or nick or username
    print(f"[*] 分析联系人：{contact_name} ({username})")

    self_wxid = get_self_wxid(db_dir)
    if not self_wxid:
        print("❌ 无法确定自己的微信 ID")
        sys.exit(1)
    print(f"[*] 自己的 wxid：{self_wxid}")

    if args.output:
        output_path = Path(args.output)
    else:
        safe_name = contact_name.encode('ascii', 'ignore').decode() or 'contact'
        safe_name = safe_name.replace('/', '_').replace(' ', '_')[:20] or 'contact'
        output_path = _SCRIPT_DIR / f'export_{safe_name}.csv'

    msg_count = export_messages(db_dir, username, contact_name, self_wxid, output_path)

    # 保存 meta 信息
    self_nick = get_self_nick(db_dir, self_wxid) or '我'
    meta = {
        'self_wxid': self_wxid,
        'self_name': self_nick,
        'partner_wxid': username,
        'partner_name': contact_name,
    }
    meta_path = output_path.with_suffix('.meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"META_PATH:{meta_path}")


if __name__ == '__main__':
    main()
