#!/usr/bin/env python3
"""Hub 用户管理 CLI——与网页管理后台（ops.html「用户与权限」区）共用 auth.py 的同一套入口。

日常加人**建议直接用网页后台**（admin 登录 → 工作台 → 用户与权限）。
本 CLI 是兜底：admin 自己忘了密码、或网页不可用时，SSH 上来救场：

    sudo docker exec inresearch-host-inresearch-1 python3 manage.py users add admin
    sudo docker exec inresearch-host-inresearch-1 python3 manage.py users passwd admin
    sudo docker exec inresearch-host-inresearch-1 python3 manage.py users rename old-name new-name
    sudo docker exec inresearch-host-inresearch-1 python3 manage.py users role <用户名> <角色>
    sudo docker exec inresearch-host-inresearch-1 python3 manage.py users list / remove <用户名>

规则（实现全在 auth.py，此处只是壳）：首个用户强制 admin；其余默认 intern；
最后一个 admin 不可降级/删除；密码只显示一次；data/users.json 不进 git。

**必须在容器内执行**：容器带 `INRESEARCH_RUNTIME_ROOT=/runtime`，账号表解析到
`/srv/inresearch.ai/data/users.json`（网站读的就是它）。在宿主机 `/srv/sources/inresearch.ai`
直接跑 `python3 manage.py users ...` 写的是源码 checkout 自己的 `data/users.json`，
网站永远读不到——改了等于没改。`users list` 会打印实际文件位置，先看再改。
`passwd` 不带 `--password` 会生成随机密码，只打印一次；记不住就再跑一次。

长期有效的管理员密码不靠这里：由容器环境 `HUB_ADMIN_USERNAME` / `HUB_ADMIN_PASSWORD`
声明（infra `$KIT/.env.inresearch`），`serve` 启动即对齐账号表，见 auth.py 模块说明。
零依赖。
"""
import argparse
import sys

from inresearch.interfaces import auth as auth


def _out(ok, msg, pw=None):
    if not ok:
        sys.exit(f"✗ {msg}")
    print(f"✓ {msg}")
    if pw:
        print(f"  密码（只显示这一次，抄给使用者）：{pw}")


def main():
    ap = argparse.ArgumentParser(description="Hub 用户管理（无注册；与网页后台同一套规则）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for c in ("add", "passwd", "remove", "list", "role", "rename"):
        sp = sub.add_parser(c)
        if c != "list":
            sp.add_argument("username")
        if c == "add":
            sp.add_argument("--role", choices=list(auth.ROLES), help="缺省 intern（首个用户强制 admin）")
        if c == "role":
            sp.add_argument("role", help="/".join(auth.ROLES))
        if c == "rename":
            sp.add_argument("new_name")
        if c in ("add", "passwd"):
            sp.add_argument("--password", help="不给则自动生成随机密码并打印一次")
    a = ap.parse_args()

    if a.cmd == "add":
        _out(*auth.add_user(a.username, a.password, a.role))
    elif a.cmd == "passwd":
        _out(*auth.reset_password(a.username, a.password))
    elif a.cmd == "remove":
        _out(*auth.remove_user(a.username))
    elif a.cmd == "role":
        _out(*auth.set_role(a.username, a.role))
    elif a.cmd == "rename":
        _out(*auth.rename_user(a.username, a.new_name))
    else:
        users = auth.load_users()
        if not users:
            print(f"（无用户。文件位置：{auth.USERS_FILE}）")
            return
        for name, u in sorted(users.items()):
            print(f"  {name:24} {u.get('role', 'member'):8} 创建于 {u.get('created', '?')}")
        print(f"共 {len(users)} 人（文件位置：{auth.USERS_FILE}）")


if __name__ == "__main__":
    main()
