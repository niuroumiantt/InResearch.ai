#!/usr/bin/env python3
"""Hub 用户管理 CLI——加用户的唯一入口，网页端没有也不会有注册。

服务器上的用法（容器内跑，users.json 在挂载卷里、容器重建不丢）：

    docker compose exec dchub python3 pipeline/users.py add yidian
    docker compose exec dchub python3 pipeline/users.py add intern-zhang
    docker compose exec dchub python3 pipeline/users.py list
    docker compose exec dchub python3 pipeline/users.py passwd intern-zhang
    docker compose exec dchub python3 pipeline/users.py remove intern-zhang

- `add` 不带 --password 时自动生成 16 位随机密码并**只打印这一次**——抄下来发给使用者。
- 密码只存 PBKDF2 哈希；`remove` 立即生效（已发的会话 cookie 下一次请求即失效）。
- ⚠️ data/users.json 不进 git。**它只活在服务器上，重装机器前记得单独备份**
  ——丢了不致命（重新 add 即可），但所有人要重新拿密码。

零依赖。
"""
import argparse
import re
import secrets
import sys
from datetime import date

from auth import load_users, save_users, hash_password, set_password, USERS_FILE

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,30}$")


def cmd_add(args):
    users = load_users()
    if args.username in users:
        sys.exit(f"✗ 用户已存在：{args.username}（改密码用 passwd）")
    if not NAME_RE.fullmatch(args.username):
        sys.exit("✗ 用户名须为小写字母/数字开头，2-31 位，可含 _ . -")
    pw = args.password or secrets.token_urlsafe(12)
    salt = secrets.token_bytes(16).hex()
    users[args.username] = {"salt": salt, "hash": hash_password(pw, salt),
                            "created": date.today().isoformat()}
    save_users(users)
    print(f"✓ 已添加 {args.username}")
    if not args.password:
        print(f"  初始密码（只显示这一次，抄给使用者）：{pw}")


def cmd_passwd(args):
    users = load_users()
    if args.username not in users:
        sys.exit(f"✗ 用户不存在：{args.username}")
    pw = args.password or secrets.token_urlsafe(12)
    set_password(args.username, pw)
    print(f"✓ 已重置 {args.username} 的密码")
    if not args.password:
        print(f"  新密码（只显示这一次）：{pw}")


def cmd_remove(args):
    users = load_users()
    if args.username not in users:
        sys.exit(f"✗ 用户不存在：{args.username}")
    del users[args.username]
    save_users(users)
    print(f"✓ 已删除 {args.username}（其会话下一次请求即失效）")


def cmd_list(_):
    users = load_users()
    if not users:
        print(f"（无用户。文件位置：{USERS_FILE}）")
        return
    for name, u in sorted(users.items()):
        print(f"  {name:24} 创建于 {u.get('created', '?')}")
    print(f"共 {len(users)} 人")


def main():
    ap = argparse.ArgumentParser(description="Hub 用户管理（无注册，仅此入口）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c, fn, with_pw in (("add", cmd_add, True), ("passwd", cmd_passwd, True),
                           ("remove", cmd_remove, False), ("list", cmd_list, False)):
        p = sub.add_parser(c)
        if c != "list":
            p.add_argument("username")
        if with_pw:
            p.add_argument("--password", help="不给则自动生成随机密码并打印一次")
        p.set_defaults(fn=fn)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
