#!/usr/bin/env python3
"""守卫:这个项目必须真的独立,而且不能把登录态带进仓库。

**为什么需要机器来守。** 这份代码是从一个大项目里抽出来的。抽出来容易,
保持抽出来难 —— 下一次「顺手 import 一下原项目那个函数」不会有任何报错,
直到有人把它 clone 到别处才发现拖着半个仓库。读代码看不出这种污染,
所以要有一条会红的检查。

三条:
1. 不许 import 母项目(``yidian``)的任何模块;
2. 不许把 cookie/登录态文件提交进仓库;
3. ``inews`` 只许依赖 pyproject 里声明过的第三方包。
"""
from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "inews"

STDLIB = set(sys.stdlib_module_names)
FORBIDDEN_ROOTS = {"yidian"}
SECRET_SUFFIXES = {".cookies"}
# 名字里看不出是密钥的那些要**逐个点名**:`.gitignore` 挡的是「不小心 add」,
# 守卫挡的是「有人 add -f 之后忘了」。cloudflare.json 里是一把有权限的 token。
SECRET_NAMES = {"cookies.txt", "ft.cookies", "bloomberg.cookies", "cloudflare.json"}


def declared_dependencies() -> set[str]:
    payload = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    names = set()
    for spec in payload["project"]["dependencies"]:
        names.add(spec.split(">")[0].split("<")[0].split("=")[0].strip().lower())
    # 分发名与 import 名不一致的,在这里显式登记 —— 别让守卫去猜。
    aliases = {"beautifulsoup4": "bs4"}
    return {aliases.get(name, name) for name in names}


def imported_roots() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(PKG.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                roots.add(node.module.split(".")[0])
        if roots:
            found[str(path.relative_to(ROOT))] = roots
    return found


def tracked_files() -> tuple[pathlib.Path, ...]:
    """Return files Git would include in a commit, including staged additions.

    Runtime credentials deliberately live below the ignored ``secrets/`` directory.
    Scanning the working tree therefore rejects the exact local-only files that the
    crawler needs.  ``git ls-files`` is the right boundary for this guard: an
    accidental ``git add -f`` appears here immediately, while ignored credentials do
    not.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        pathlib.Path(raw.decode("utf-8", errors="surrogateescape"))
        for raw in result.stdout.split(b"\0")
        if raw
    )


def main() -> int:
    problems: list[str] = []
    allowed = declared_dependencies() | STDLIB | {"inews"}

    for path, roots in imported_roots().items():
        for root in sorted(roots):
            if root in FORBIDDEN_ROOTS:
                problems.append(
                    f"{path} import 了母项目模块 `{root}` —— 这个项目就不再独立了"
                )
            elif root not in allowed:
                problems.append(
                    f"{path} import 了未声明的依赖 `{root}`;"
                    "先加进 pyproject 的 dependencies,再用"
                )

    for path in tracked_files():
        if path.suffix in SECRET_SUFFIXES or path.name in SECRET_NAMES:
            problems.append(f"{path} 看起来是登录态文件,不该进仓库")

    if problems:
        print("独立性守卫失败:", file=sys.stderr)
        for line in problems:
            print(f"  - {line}", file=sys.stderr)
        return 1
    print(f"独立性守卫通过({len(imported_roots())} 个模块,无母项目依赖)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
