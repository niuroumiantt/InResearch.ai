"""`tools/hourly.sh` 的用例。

这里只测**它到底跑没跑**这一件事:2026-08-21 站长在 macOS 上跑它,秒回、
什么都没做 —— 因为脚本用了 `flock`,而那是 Linux util-linux 的命令,macOS 没有。
取锁那句失败,于是每一轮都走「跳过:上一轮还在跑」然后 exit 0。

一个定时任务**静默地什么都不做**,是这个项目最坏的失败形态:页面不变、日志
只有一行「跳过」、退出码 0,监控和人都看不出区别。
"""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from inews import schedule as collector_schedule

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "hourly.sh"
REPAIR = ROOT / "tools" / "repair.sh"


def _stub(tmp_path: Path, marker: Path, exit_code: int = 0) -> Path:
    """假装是 inews:留个记号,按要求的退出码退出。"""
    stub = tmp_path / "fake-inews"
    stub.write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\nexit {exit_code}\n',
        encoding="utf-8",
    )
    stub.chmod(0o755)
    return stub


def _no_flock_path(tmp_path: Path) -> str:
    """把 macOS 那台机器的条件复刻到这里:`flock` 根本不存在。

    这个 bug 只在 macOS 上发作(flock 是 Linux util-linux 的命令),而用例大多
    在 Linux 上跑 —— 不复刻这个条件,用例就永远是绿的,而站长那边永远不跑。
    """
    shadow = tmp_path / "bin"
    shadow.mkdir(exist_ok=True)
    fake = shadow / "flock"
    fake.write_text("#!/usr/bin/env bash\nexit 127\n", encoding="utf-8")
    fake.chmod(0o755)
    return f"{shadow}:{os.environ.get('PATH', '')}"


def _run(tmp_path: Path, stub: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PY": str(stub),
        "INEWS_LOG": str(tmp_path / "hourly.log"),
        "INEWS_LOCK": str(tmp_path / "lock"),
        "INEWS_RESOURCE_LOCK": str(tmp_path / "resource.lock"),
        "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
        "PATH": _no_flock_path(tmp_path),
        **extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=60
    )


def test_hourly_actually_runs_the_crawl(tmp_path: Path):
    """脚本必须真的调用抓取。取锁失败就静默 exit 0 是这个 bug 的原形。"""
    marker = tmp_path / "ran"
    stub = _stub(tmp_path, marker)
    result = _run(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "hourly.log").read_text(encoding="utf-8")
    assert marker.exists(), f"抓取根本没被调用。日志:\n{log}"
    assert "--group" in marker.read_text(encoding="utf-8")
    assert result.returncode == 0, log


def test_hourly_does_not_publish_when_the_crawl_fails(tmp_path: Path):
    """抓取失败就不发布 —— 宁可服务器停在上一轮,也不要拿可疑产出盖掉它。"""
    marker = tmp_path / "ran"
    stub = _stub(tmp_path, marker, exit_code=3)
    result = _run(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "hourly.log").read_text(encoding="utf-8")
    assert result.returncode == 3
    assert "本轮不发布" in log


def _run_repair_with_publish(
    tmp_path: Path, *, publish_exit: int = 0
) -> tuple[subprocess.CompletedProcess, Path]:
    crawler = _stub(tmp_path, tmp_path / "repair.crawl")
    calls = tmp_path / "publish.calls"
    publish = tmp_path / "fake-publish"
    publish.write_text(
        f'#!/usr/bin/env bash\necho "$RAW_OUT|$RAW_DEST" >> "{calls}"\n'
        f"exit {publish_exit}\n",
        encoding="utf-8",
    )
    publish.chmod(0o755)
    backup = tmp_path / "fake-backup"
    backup.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    backup.chmod(0o755)
    result = subprocess.run(
        ["bash", str(REPAIR), "wsj"],
        env={
            **os.environ,
            "PY": str(crawler),
            "INEWS_LOG": str(tmp_path / "repair.log"),
            "INEWS_LOCK": str(tmp_path / "repair.lock"),
            "INEWS_RESOURCE_LOCK": str(tmp_path / "resource.lock"),
            "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
            "INEWS_PUBLISH_SH": str(publish),
            "INEWS_BACKUP_SH": str(backup),
            "RAW_OUT": str(tmp_path / "WSJ.COM"),
            "RAW_DEST": "/srv/rawarticle/wsj-test",
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result, calls


def test_repair_preserves_a_source_publish_failure_exit_code(tmp_path: Path):
    result, calls = _run_repair_with_publish(tmp_path, publish_exit=7)

    assert result.returncode == 7
    assert len(calls.read_text(encoding="utf-8").splitlines()) == 1
    assert "来源页面发布失败,退出码 7" in (
        tmp_path / "repair.log"
    ).read_text(encoding="utf-8")


def test_repair_publishes_the_unified_dashboard_after_the_source(tmp_path: Path):
    result, calls = _run_repair_with_publish(tmp_path)

    assert result.returncode == 0
    published = calls.read_text(encoding="utf-8").splitlines()
    assert published[0].endswith("WSJ.COM|/srv/rawarticle/wsj-test")
    assert published[1].endswith("out/DASHBOARD|/srv/rawarticle/dashboard")


def test_hourly_skips_when_a_previous_round_still_holds_the_lock(tmp_path: Path):
    """锁要真的锁得住:两轮同时写台账会互相盖。"""
    marker = tmp_path / "ran"
    slow = tmp_path / "slow-inews"
    slow.write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\nsleep 5\n', encoding="utf-8"
    )
    slow.chmod(0o755)
    env = {
        **os.environ, "PY": str(slow),
        "INEWS_LOG": str(tmp_path / "hourly.log"),
        "INEWS_LOCK": str(tmp_path / "lock"),
        "INEWS_RESOURCE_LOCK": str(tmp_path / "resource.lock"),
        "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
        "INEWS_SKIP_PUBLISH": "1",
        "PATH": _no_flock_path(tmp_path),
    }
    first = subprocess.Popen(["bash", str(SCRIPT)], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        # 等第一轮真的把锁拿到手
        for _ in range(50):
            if marker.exists():
                break
            import time as _t
            _t.sleep(0.1)
        second = _run(tmp_path, _stub(tmp_path, tmp_path / "second-ran"))
        assert second.returncode == 0
        assert "跳过" in (tmp_path / "hourly.log").read_text(encoding="utf-8")
        assert not (tmp_path / "second-ran").exists(), "第二轮不该跑起来"
    finally:
        first.terminate()
        first.wait(timeout=10)


def test_daily_chrome_sites_queue_behind_the_shared_resource_lock(tmp_path: Path):
    """FT 未释放日常 Chrome 时，Bloomberg 要等待，不能再开第二组标签页。"""
    resource = tmp_path / "daily-chrome.lock"
    ft_started = tmp_path / "ft-started"
    bloomberg_ran = tmp_path / "bloomberg-ran"
    slow = tmp_path / "slow-ft"
    slow.write_text(
        f'#!/usr/bin/env bash\n: > "{ft_started}"\nsleep 1\n', encoding="utf-8"
    )
    slow.chmod(0o755)
    fast = _stub(tmp_path, bloomberg_ran)
    common = {
        **os.environ,
        "INEWS_RESOURCE_LOCK": str(resource),
        "INEWS_RESOURCE_WAIT_SECONDS": "5",
        "INEWS_RESOURCE_POLL_SECONDS": "1",
        "INEWS_SKIP_PUBLISH": "1",
        "PATH": _no_flock_path(tmp_path),
    }
    first = subprocess.Popen(
        ["bash", str(SCRIPT), "ft"],
        env={
            **common,
            "PY": str(slow),
            "INEWS_LOG": str(tmp_path / "ft.log"),
            "INEWS_LOCK": str(tmp_path / "ft.lock"),
        },
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            if ft_started.exists():
                break
            time.sleep(0.02)
        assert ft_started.exists(), "FT 测试轮没有进入抓取阶段"
        second = subprocess.Popen(
            ["bash", str(SCRIPT), "bloomberg"],
            env={
                **common,
                "PY": str(fast),
                "INEWS_LOG": str(tmp_path / "bloomberg.log"),
                "INEWS_LOCK": str(tmp_path / "bloomberg.lock"),
            },
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.2)
        assert not bloomberg_ran.exists(), "共用日常 Chrome 的两个站不应并发"
        first.wait(timeout=5)
        second.wait(timeout=5)
        assert first.returncode == 0 and second.returncode == 0
        assert bloomberg_ran.exists(), "资源释放后，等待中的站应该真的继续运行"
        assert "资源忙" in (tmp_path / "bloomberg.log").read_text(encoding="utf-8")
    finally:
        if first.poll() is None:
            first.terminate()
            first.wait(timeout=5)
        if "second" in locals() and second.poll() is None:
            second.terminate()
            second.wait(timeout=5)


def test_resource_wait_timeout_is_visible_and_nonzero(tmp_path: Path):
    """异常长轮占槽时不能静默 exit 0 冒充成功。"""
    lock = tmp_path / "resource.lock"
    ready = tmp_path / "holder-ready"
    holder = tmp_path / "hold-lock"
    helper = ROOT / "tools" / "lib" / "directory_lock.sh"
    holder.write_text(
        "#!/usr/bin/env bash\n"
        f'. "{helper}"\n'
        "log() { :; }\n"
        'inews_lock_try "$1" "另一条测试轮" 9 || exit $?\n'
        ': > "$2"\n'
        "sleep 5\n",
        encoding="utf-8",
    )
    holder.chmod(0o755)
    owner = subprocess.Popen(["bash", str(holder), str(lock), str(ready)])
    for _ in range(50):
        if ready.exists():
            break
        time.sleep(0.02)
    assert ready.exists(), "测试持有者没有取得资源锁"
    marker = tmp_path / "must-not-run"
    try:
        result = _run(
            tmp_path,
            _stub(tmp_path, marker),
            INEWS_RESOURCE_LOCK=str(lock),
            INEWS_RESOURCE_WAIT_SECONDS="0",
            INEWS_SKIP_PUBLISH="1",
        )
        assert result.returncode == 75
        assert not marker.exists()
        log = (tmp_path / "hourly.log").read_text(encoding="utf-8")
        assert "资源等待超时" in log and "未运行" in log
    finally:
        owner.terminate()
        owner.wait(timeout=5)


def test_dead_resource_lock_is_reclaimed(tmp_path: Path):
    lock = tmp_path / "resource.lock"
    lock.write_text("99999999\t已经退出的任务\t旧时间\n", encoding="utf-8")
    marker = tmp_path / "ran-after-reclaim"
    result = _run(
        tmp_path,
        _stub(tmp_path, marker),
        INEWS_RESOURCE_LOCK=str(lock),
        INEWS_RESOURCE_WAIT_SECONDS="0",
        INEWS_SKIP_PUBLISH="1",
    )
    assert result.returncode == 0
    assert marker.exists()
    assert "接管" in (tmp_path / "hourly.log").read_text(encoding="utf-8")


# ---------------- tools/tidy_layout.sh ----------------

TIDY = ROOT / "tools" / "tidy_layout.sh"


def test_tidy_removes_the_old_flat_pages_but_not_the_site_itself(tmp_path: Path):
    """整理老布局:根上那些 <uuid>.html 是孤儿,index/stats/dashboard 不是。

    删除的口径写死成 uuid 的形状 —— 「删掉根上所有 .html」哪天会把手写的
    页面一起带走。
    """
    out = tmp_path / "FT.COM"
    out.mkdir()
    old = out / "aaaaaaaa-1111-2222-3333-444444444444.html"
    old.write_text("老页面", encoding="utf-8")
    # 有正本才删得起 —— 没有正本的那种由下面那条用例守着
    (out / "data" / "articles").mkdir(parents=True)
    (out / "data" / "articles" / "aaaaaaaa-1111-2222-3333-444444444444.json").write_text(
        '{"article_id": "aaaaaaaa-1111-2222-3333-444444444444", "body": "有正本"}',
        encoding="utf-8",
    )
    keep = [out / name for name in ("index.html", "stats.html", "dashboard.html", "site.css")]
    for path in keep:
        path.write_text("留着", encoding="utf-8")
    marker = tmp_path / "called"
    stub = _stub(tmp_path, marker)

    result = subprocess.run(
        ["bash", str(TIDY)],
        env={**os.environ, "PY": str(stub), "RAW_OUT": str(out)},
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "--render-only" in marker.read_text(encoding="utf-8"), "要先重画再删"
    assert not old.exists()
    for path in keep:
        assert path.exists(), f"{path.name} 不该被删"


# ---------------- tools/抓一轮.command ----------------

BUTTON = ROOT / "tools" / "抓一轮.command"


def test_the_double_click_button_is_executable_and_runs_the_same_round(tmp_path: Path):
    """双击的那个入口跑的必须是**同一轮**:同一把锁、同一份日志。

    另起一条路径就会有两套行为,而定时任务和手点这两条路径下出的问题
    没人会同时去查。
    """
    assert os.access(BUTTON, os.X_OK), "不可执行的话,Finder 里双击会用文本编辑器打开它"
    assert "tools/hourly.sh" in BUTTON.read_text(encoding="utf-8")

    marker = tmp_path / "called"
    stub = _stub(tmp_path, marker)
    result = subprocess.run(
        ["bash", str(BUTTON)],
        env={
            **os.environ,
            "PY": str(stub),
            "INEWS_LOG": str(tmp_path / "hourly.log"),
            "INEWS_LOCK": str(tmp_path / "lock"),
            "INEWS_RESOURCE_LOCK": str(tmp_path / "resource.lock"),
            "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
            "INEWS_SKIP_PUBLISH": "1",
            "PATH": _no_flock_path(tmp_path),
        },
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "--group all" in marker.read_text(encoding="utf-8")


def test_the_button_keeps_a_failure_on_screen(tmp_path: Path):
    """失败要留在屏幕上并带上非零退出码 —— 双击窗口一闪而过的话,
    失败和成功长得一模一样。"""
    marker = tmp_path / "called"
    stub = _stub(tmp_path, marker, exit_code=1)
    result = subprocess.run(
        ["bash", str(BUTTON)],
        env={
            **os.environ,
            "PY": str(stub),
            "INEWS_LOG": str(tmp_path / "hourly.log"),
            "INEWS_LOCK": str(tmp_path / "lock"),
            "INEWS_RESOURCE_LOCK": str(tmp_path / "resource.lock"),
            "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
            "INEWS_SKIP_PUBLISH": "1",
            "PATH": _no_flock_path(tmp_path),
        },
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 1
    assert "失败" in result.stdout


def test_tidy_keeps_a_page_whose_body_is_not_in_the_archive(tmp_path: Path):
    """存档里没有正本的页面**不能删** —— 那一篇的正文就只在这个 HTML 里。

    2026-08-22 这一步删掉了 23 篇:那批是存档上线之前爬的,重画画不出来,
    删完只剩台账里一行标题。「产物随时能重画」只在有正本的时候成立。
    """
    out = tmp_path / "FT.COM"
    (out / "data" / "articles").mkdir(parents=True)
    (out / "data" / "articles" / "aaaaaaaa-1111-2222-3333-444444444444.json").write_text(
        '{"article_id": "aaaaaaaa-1111-2222-3333-444444444444", "body": "有正本"}',
        encoding="utf-8",
    )
    has_archive = out / "aaaaaaaa-1111-2222-3333-444444444444.html"
    no_archive = out / "bbbbbbbb-1111-2222-3333-444444444444.html"
    for path in (has_archive, no_archive):
        path.write_text("老页面", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(TIDY)],
        env={**os.environ, "PY": str(_stub(tmp_path, tmp_path / "called")), "RAW_OUT": str(out)},
        capture_output=True, text=True, timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert not has_archive.exists(), "有正本的那篇,页面重画得出来,可以删"
    assert no_archive.exists(), "没有正本的那篇必须留着"
    assert "--refill" in result.stdout, "要告诉人怎么把缺的正本补回来"


# ---------------- 装定时任务 ----------------

INSTALL = ROOT / "tools" / "install_hourly.sh"


def _install(tmp_path: Path, **extra: str) -> subprocess.CompletedProcess:
    """在假的 LaunchAgents 目录里装,用假的 launchctl —— 不碰这台机器的 launchd。"""
    agents = tmp_path / "LaunchAgents"
    agents.mkdir(exist_ok=True)
    calls = tmp_path / "launchctl.calls"
    state = tmp_path / "launchctl-state"
    state.mkdir(exist_ok=True)
    failure_count = tmp_path / "bootstrap-failure-count"
    fake = tmp_path / "launchctl"
    # 假 launchctl:记下每次调用,并像真的那样只在 bootstrap 过之后才 print 得出来
    # ——「装上了」这句话必须由回读决定,用例就得把回读能失败这件事复刻出来。
    fake.write_text(
        f'#!/usr/bin/env bash\necho "$@" >> "{calls}"\n'
        f'state="{state}"\n'
        f'case "$1" in\n'
        f'  bootstrap)\n'
        '    target="${!#}"\n'
        '    label="${target##*/}"\n'
        '    label="${label%.plist}"\n'
        f'    if [ -n "${{INEWS_TEST_FAIL_BOOTSTRAP_MATCH:-}}" ] '
        f'&& [[ "$target" == *"$INEWS_TEST_FAIL_BOOTSTRAP_MATCH"* ]] '
        f'&& [ "$(cat "{failure_count}" 2>/dev/null || echo 0)" '
        f'-lt "${{INEWS_TEST_FAIL_BOOTSTRAP_COUNT:-1}}" ]; then\n'
        f'      count=$(cat "{failure_count}" 2>/dev/null || echo 0)\n'
        f'      echo $((count + 1)) > "{failure_count}"\n'
        f'      exit 44\n'
        f'    fi\n'
        '    : > "$state/$label"\n'
        f'    ;;\n'
        f'  bootout)\n'
        '    label="${2##*/}"\n'
        f'    if [ -n "${{INEWS_TEST_STICKY_LABEL:-}}" ] '
        f'&& [ "$label" = "$INEWS_TEST_STICKY_LABEL" ]; then\n'
        f'      :\n'
        f'    else\n'
        '      rm -f "$state/$label"\n'
        f'    fi\n'
        f'    ;;\n'
        '  print)\n'
        '    label="${2##*/}"\n'
        '    [ -f "$state/$label" ] || exit 113\n'
        '    ;;\n'
        f'esac\nexit 0\n',
        encoding="utf-8",
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "INEWS_LAUNCH_AGENTS": str(agents),
        "INEWS_LAUNCHCTL": str(fake),
        "INEWS_SCHEDULE_PYTHON": sys.executable,
        "INEWS_BOOTSTRAP_RETRY_SECONDS": "0",
        **extra,
    }
    return subprocess.run(
        ["bash", str(INSTALL)], env=env, capture_output=True, text=True, timeout=60
    )


def test_install_writes_the_plist_with_this_checkout_s_real_path(tmp_path: Path):
    """plist 里写死着 `/Users/hermes/code/inews`,而 launchd 不认 `~` 和环境变量。

    手抄那条路径正是这一步最容易出错的地方 —— 装到别人的机器上、或者仓库挪了个
    位置,任务就会指向一个不存在的目录,然后**静默地什么都不做**。
    """
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    plist = (tmp_path / "LaunchAgents" / "today.inews.collector.hourly.plist").read_text(
        encoding="utf-8"
    )
    assert str(ROOT) in plist, "要把这份 checkout 的真实路径写进去"
    # Match the complete old checkout path, not its text prefix: the unified repo is
    # named ``inews.today`` and therefore legitimately contains ``.../inews``.
    assert "<string>/Users/hermes/code/inews</string>" not in plist
    assert str(ROOT / "tools" / "hourly.sh") in plist


def test_install_loads_it_into_launchd(tmp_path: Path):
    """写个文件不算装上 —— 没 bootstrap 过的 plist,launchd 根本不知道它存在。"""
    result = _install(tmp_path)
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert "bootstrap" in calls
    assert "today.inews.collector.hourly" in calls
    assert "print" in calls, "装完要回读一次,不能只凭 bootstrap 的退出码说装上了"


def test_install_explains_fixed_slots_without_immediate_multi_site_run(tmp_path: Path):
    """安装只登记固定日历，不能因 RunAtLoad 把多站在同一秒启动。"""
    out = _install(tmp_path).stdout
    for line in (
        "FT.COM 每小时 :05",
        "BLOOMBERG.COM 每小时 :20",
        "CNBC.COM 每小时 :27",
        "WSJ.COM 每小时 :50",
        "REUTERS.COM 奇数小时（每 2 小时） :35",
        "AXIOS.COM 偶数小时（每 2 小时） :35",
    ):
        assert line in out
    assert "不会立刻抓取" in out
    assert "专用窗口" in out


def test_install_is_idempotent(tmp_path: Path):
    """重装一次不能报错:改完 plist 之后要能直接再跑一遍。"""
    assert _install(tmp_path).returncode == 0
    second = _install(tmp_path)
    assert second.returncode == 0, second.stderr
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert "bootout" in calls, "重装前要先把旧的卸掉,否则 bootstrap 会撞上「已存在」"


def test_install_rolls_back_every_touched_plist_after_a_midway_bootstrap_failure(
    tmp_path: Path,
):
    """第五份之前失败也不能留下半套新时刻表。"""
    assert _install(tmp_path).returncode == 0
    agents = tmp_path / "LaunchAgents"
    before = {path.name: path.read_bytes() for path in agents.glob("*.plist")}

    result = _install(
        tmp_path,
        INEWS_TEST_FAIL_BOOTSTRAP_MATCH="today.inews.collector.cnbc.plist",
        INEWS_TEST_FAIL_BOOTSTRAP_COUNT="3",
    )

    assert result.returncode != 0
    assert "正在恢复原有 LaunchAgents" in result.stderr
    after = {path.name: path.read_bytes() for path in agents.glob("*.plist")}
    assert after == before


def test_install_retries_a_transient_launchctl_bootstrap_error(tmp_path: Path):
    result = _install(
        tmp_path,
        INEWS_TEST_FAIL_BOOTSTRAP_MATCH="today.inews.collector.serve.plist",
        INEWS_TEST_FAIL_BOOTSTRAP_COUNT="1",
    )

    assert result.returncode == 0, result.stderr
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert calls.count("today.inews.collector.serve.plist") >= 2


def test_install_never_mistakes_a_still_loaded_old_job_for_the_new_schedule(
    tmp_path: Path,
):
    label = "today.inews.collector.hourly"
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    old = agents / f"{label}.plist"
    old.write_text("旧的 StartInterval 配置", encoding="utf-8")
    state = tmp_path / "launchctl-state"
    state.mkdir()
    (state / label).touch()

    result = _install(tmp_path, INEWS_TEST_STICKY_LABEL=label)

    assert result.returncode != 0
    assert "无法确认旧任务已卸载" in result.stderr
    assert old.read_text(encoding="utf-8") == "旧的 StartInterval 配置"
    assert (state / label).exists()


def test_install_fails_before_touching_launchd_when_log_directory_cannot_be_made(
    tmp_path: Path,
):
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("挡住 mkdir", encoding="utf-8")

    result = _install(
        tmp_path,
        INEWS_LAUNCH_AGENTS=str(blocked / "LaunchAgents"),
    )

    assert result.returncode != 0
    assert "无法建立 LaunchAgents 或日志目录" in result.stderr
    assert not (tmp_path / "launchctl.calls").exists()


def test_install_restores_earlier_legacy_jobs_when_the_third_one_stays_loaded(
    tmp_path: Path,
):
    legacy = (
        "today.inews.paywall-ai.hourly",
        "today.inews.paywall-ai.serve",
        "today.inews.paywall-ai.bloomberg",
    )
    agents = tmp_path / "LaunchAgents"
    agents.mkdir()
    state = tmp_path / "launchctl-state"
    state.mkdir()
    for index, label in enumerate(legacy):
        (agents / f"{label}.plist").write_text(
            f"旧配置 {index}", encoding="utf-8"
        )
        (state / label).touch()
    before = {path.name: path.read_bytes() for path in agents.glob("*.plist")}

    result = _install(
        tmp_path,
        INEWS_TEST_STICKY_LABEL=legacy[2],
    )

    assert result.returncode != 0
    assert "拒绝让新旧任务同时运行" in result.stderr
    after = {path.name: path.read_bytes() for path in agents.glob("*.plist")}
    assert after == before
    assert all((state / label).exists() for label in legacy)


def test_install_also_installs_the_button_listener(tmp_path: Path):
    """按钮要能按,本机得有那个监听常驻着 —— 它和每小时那轮一起装,别让人装两次。"""
    _install(tmp_path)
    agents = tmp_path / "LaunchAgents"
    listener = agents / "today.inews.collector.serve.plist"
    assert listener.exists(), "本机监听的 LaunchAgent 也要装上"
    text = listener.read_text(encoding="utf-8")
    assert str(ROOT) in text and "--serve" in text
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert "today.inews.collector.serve" in calls, "写了文件不算装上,要 bootstrap"


def test_install_defaults_to_all_registered_collectors(tmp_path: Path):
    """所有已核验站都获授权自动运行；新增站不能只注册而漏装。"""
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    agents = tmp_path / "LaunchAgents"
    assert (agents / "today.inews.collector.bloomberg.plist").exists()
    assert (agents / "today.inews.collector.cnbc.plist").exists()
    assert (agents / "today.inews.collector.serve.plist").exists()
    assert (agents / "today.inews.collector.wsj.plist").exists()
    assert (agents / "today.inews.collector.reuters.plist").exists()
    assert (agents / "today.inews.collector.axios.plist").exists()
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert "today.inews.collector.bloomberg" in calls
    assert "today.inews.collector.cnbc" in calls
    assert "today.inews.collector.reuters" in calls
    assert "today.inews.collector.axios" in calls
    calls = (tmp_path / "launchctl.calls").read_text(encoding="utf-8")
    assert any(
        line.startswith("bootstrap ") and "today.inews.collector.wsj.plist" in line
        for line in calls.splitlines()
    )


def test_schedule_covers_every_registered_site_once():
    values = collector_schedule.validate_schedules()
    assert {item.site for item in values} == set(collector_schedule.sites.REGISTRY)
    assert len(values) == len({item.site for item in values})
    assert collector_schedule.cadence_for_site("ft") == "每小时一轮"
    assert collector_schedule.cadence_for_site("reuters") == "每 2 小时一轮"
    assert collector_schedule.cadence_for_site("axios") == "每 2 小时一轮"


def test_schedule_has_real_24_hour_gaps_not_just_distinct_minute_labels():
    """奇偶小时可共用 :35，但一天内任何真实触发都不能相撞。"""
    values = collector_schedule.validate_schedules()
    events = [
        event
        for item in values
        for event in collector_schedule._events(item)
    ]
    assert len(events) == len(set(events))
    assert min(
        collector_schedule._circular_gaps(events, period=24 * 60)
    ) >= collector_schedule.MIN_ANY_GAP
    visible = [
        event
        for item in values if item.resource_group == collector_schedule.DAILY_CHROME
        for event in collector_schedule._events(item)
    ]
    assert min(
        collector_schedule._circular_gaps(visible, period=24 * 60)
    ) >= collector_schedule.MIN_DAILY_CHROME_GAP


def test_schedule_rejects_two_sites_at_the_same_actual_hour_and_minute():
    broken = tuple(
        replace(item, minute=35, hours=collector_schedule.EVEN_HOURS)
        if item.site == "cnbc" else item
        for item in collector_schedule.SCHEDULES
    )
    with pytest.raises(ValueError, match="同一个日历时刻"):
        collector_schedule.validate_schedules(broken)


def test_schedule_rejects_a_registered_site_without_an_explicit_browser_tier():
    """新 adapter 漏登档位时不能默认成 headless，失败后又在错误锁下弹 Chrome。"""
    extra = collector_schedule.CollectorSchedule(
        "new-site", "today.inews.collector.new-site", 40,
        collector_schedule.HEADLESS, "new-site-launchd",
    )
    with pytest.raises(ValueError, match="浏览器档位"):
        collector_schedule.validate_schedules(
            (*collector_schedule.SCHEDULES, extra),
            registered_sites=(*collector_schedule.sites.REGISTRY, "new-site"),
        )


def test_every_scheduled_site_is_supported_by_the_shared_hourly_script():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--list-sites"], capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [item.site for item in collector_schedule.SCHEDULES]


@pytest.mark.parametrize(
    ("site", "minute"),
    (("ft", 5), ("bloomberg", 20), ("cnbc", 27), ("wsj", 50)),
)
def test_generated_collectors_use_fixed_calendar_minutes_without_run_at_load(
    tmp_path: Path, site: str, minute: int,
):
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    spec = next(item for item in collector_schedule.SCHEDULES if item.site == site)
    path = tmp_path / "LaunchAgents" / f"{spec.label}.plist"
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["StartCalendarInterval"] == {"Minute": minute}
    assert "StartInterval" not in payload
    assert "RunAtLoad" not in payload
    assert payload["ProgramArguments"][-1] == site
    assert payload["EnvironmentVariables"]["INEWS_RESOURCE_GROUP"] == spec.resource_group
    if spec.resource_group == collector_schedule.DAILY_CHROME:
        assert payload["EnvironmentVariables"][
            "YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW"
        ] == "1"


@pytest.mark.parametrize(
    ("site", "hours"),
    (("reuters", tuple(range(1, 24, 2))), ("axios", tuple(range(0, 24, 2)))),
)
def test_heavy_new_collectors_alternate_the_only_safe_visible_slot(
    tmp_path: Path, site: str, hours: tuple[int, ...],
):
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    spec = next(item for item in collector_schedule.SCHEDULES if item.site == site)
    path = tmp_path / "LaunchAgents" / f"{spec.label}.plist"
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["StartCalendarInterval"] == [
        {"Hour": hour, "Minute": 35} for hour in hours
    ]
    assert payload["EnvironmentVariables"][
        "YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW"
    ] == "1"


def test_listener_still_runs_at_load_and_stays_alive(tmp_path: Path):
    result = _install(tmp_path)
    assert result.returncode == 0, result.stderr
    path = tmp_path / "LaunchAgents" / "today.inews.collector.serve.plist"
    with path.open("rb") as handle:
        payload = plistlib.load(handle)
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True


def test_hourly_only_asks_for_the_first_page(tmp_path: Path):
    """每小时那一轮只翻第 1 页。

    搜索页按时间倒序,这一小时里新出的永远在第 1 页;翻到第 5 页是在挖历史,
    而历史只需要挖一次。8-23 那轮 45 个词 × 5 页 + 分类页,光发现就开了两百多次
    窗口(每次之间还要限速 4 秒),换回来的是同一批早就在台账里的稿子。
    """
    marker = tmp_path / "args"
    stub = _stub(tmp_path, marker)
    _run(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    assert "--pages 1" in marker.read_text(encoding="utf-8")


def test_hourly_has_no_per_round_cap(tmp_path: Path):
    """每轮不设上限(9-01 站长指定;此前 20 → 50 → 0)。

    base 已经建立、词表也砍掉了九个只带来垃圾的词,每小时真正新出的就是
    个位数 —— 上限保护的场景不存在了,留着只会在断档恢复后把补课拖成好几轮。
    发现阶段仍然只翻第 1 页,天然有界。
    """
    marker = tmp_path / "args"
    stub = _stub(tmp_path, marker)
    _run(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    assert "--limit 0" in marker.read_text(encoding="utf-8")


BLOOMBERG_SCRIPT = ROOT / "tools" / "hourly.sh"


def _run_bloomberg(tmp_path: Path, stub: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PY": str(stub),
        "INEWS_LOG": str(tmp_path / "bloomberg.log"),
        "INEWS_LOCK": str(tmp_path / "bloomberg.lock"),
        "INEWS_RESOURCE_LOCK": str(tmp_path / "bloomberg-resource.lock"),
        "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
        "PATH": _no_flock_path(tmp_path),
        **extra,
    }
    return subprocess.run(
        ["bash", str(BLOOMBERG_SCRIPT), "bloomberg"],
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_bloomberg_hourly_crawls_the_hub_line_only(tmp_path: Path):
    """Bloomberg 每小时轮:走 --site bloomberg、不设上限;没有关键词可传。"""
    marker = tmp_path / "ran"
    stub = _stub(tmp_path, marker)
    result = _run_bloomberg(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "bloomberg.log").read_text(encoding="utf-8")
    args = marker.read_text(encoding="utf-8")
    assert "--site bloomberg" in args, f"抓取参数不对:{args}\n日志:\n{log}"
    assert "--limit 0" in args
    assert "--group" not in args
    assert result.returncode == 0, log


def test_bloomberg_hourly_does_not_publish_on_failure(tmp_path: Path):
    marker = tmp_path / "ran"
    stub = _stub(tmp_path, marker, exit_code=3)
    result = _run_bloomberg(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "bloomberg.log").read_text(encoding="utf-8")
    assert result.returncode == 3
    assert "本轮不发布" in log


def _run_cnbc(tmp_path: Path, stub: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PY": str(stub),
        "INEWS_LOG": str(tmp_path / "cnbc.log"),
        "INEWS_LOCK": str(tmp_path / "cnbc.lock"),
        "INEWS_RESOURCE_LOCK": str(tmp_path / "cnbc-resource.lock"),
        "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
        "PATH": _no_flock_path(tmp_path),
        **extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "cnbc"],
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_cnbc_hourly_uses_the_official_hub_adapter_without_keywords(tmp_path: Path):
    marker = tmp_path / "cnbc-ran"
    stub = _stub(tmp_path, marker)
    result = _run_cnbc(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    args = marker.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "--site cnbc" in args and "--pages 1" in args and "--limit 0" in args
    assert "--group" not in args and "--keyword" not in args


def test_cnbc_hourly_does_not_publish_on_failure(tmp_path: Path):
    marker = tmp_path / "cnbc-ran"
    stub = _stub(tmp_path, marker, exit_code=3)
    result = _run_cnbc(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "cnbc.log").read_text(encoding="utf-8")
    assert result.returncode == 3
    assert "本轮不发布" in log


def _run_wsj(tmp_path: Path, stub: Path, **extra: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PY": str(stub),
        "INEWS_LOG": str(tmp_path / "wsj.log"),
        "INEWS_LOCK": str(tmp_path / "wsj.lock"),
        "INEWS_RESOURCE_LOCK": str(tmp_path / "wsj-resource.lock"),
        "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
        "PATH": _no_flock_path(tmp_path),
        **extra,
    }
    return subprocess.run(
        ["bash", str(SCRIPT), "wsj"],
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_wsj_hourly_uses_the_ai_pagination_adapter_without_keywords(tmp_path: Path):
    marker = tmp_path / "wsj-ran"
    stub = _stub(tmp_path, marker)
    result = _run_wsj(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    args = marker.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "--site wsj" in args and "--pages 1" in args and "--limit 0" in args
    assert "--group" not in args and "--keyword" not in args


def test_wsj_hourly_does_not_publish_on_failure(tmp_path: Path):
    marker = tmp_path / "wsj-ran"
    stub = _stub(tmp_path, marker, exit_code=3)
    result = _run_wsj(tmp_path, stub, INEWS_SKIP_PUBLISH="1")
    log = (tmp_path / "wsj.log").read_text(encoding="utf-8")
    assert result.returncode == 3
    assert "本轮不发布" in log


@pytest.mark.parametrize("site", ("reuters", "axios"))
def test_new_fixed_ai_lanes_use_their_adapter_without_arbitrary_keywords(
    tmp_path: Path, site: str,
):
    marker = tmp_path / f"{site}-ran"
    stub = _stub(tmp_path, marker)
    log = tmp_path / f"{site}.log"
    result = subprocess.run(
        ["bash", str(SCRIPT), site],
        env={
            **os.environ,
            "PY": str(stub),
            "INEWS_LOG": str(log),
            "INEWS_LOCK": str(tmp_path / f"{site}.lock"),
            "INEWS_RESOURCE_LOCK": str(tmp_path / f"{site}-resource.lock"),
            "INEWS_DASHBOARD_LOCK": str(tmp_path / "dashboard.lock"),
            "INEWS_SKIP_PUBLISH": "1",
            "PATH": _no_flock_path(tmp_path),
        },
        capture_output=True,
        text=True,
        timeout=60,
    )
    args = marker.read_text(encoding="utf-8")
    assert result.returncode == 0, log.read_text(encoding="utf-8")
    assert f"--site {site}" in args and "--pages 1" in args and "--limit 0" in args
    assert "--group" not in args and "--keyword" not in args


# ---------------- tools/publish.sh ----------------

PUBLISH = ROOT / "tools" / "publish.sh"


def test_publish_reports_the_destination_it_actually_pushed_to(tmp_path: Path):
    """9-02 首轮 Bloomberg 发布:rsync 推的是 /srv/rawarticle/bloomberg,
    最后那句却写死「已发布 → …/rawarticle/ft/」—— 提示语在撒谎。
    完成语必须由真实的 RAW_DEST 推导,rsync 收到的目的地也要对得上。"""
    out = tmp_path / "BLOOMBERG.COM"
    out.mkdir()
    (out / "index.html").write_text("页面", encoding="utf-8")
    marker = tmp_path / "rsync-args"
    shadow = tmp_path / "bin"
    shadow.mkdir()
    fake = shadow / "rsync"
    fake.write_text(f'#!/usr/bin/env bash\necho "$@" >> "{marker}"\nexit 0\n',
                    encoding="utf-8")
    fake.chmod(0o755)
    result = subprocess.run(
        ["bash", str(PUBLISH)],
        env={**os.environ,
             "PATH": f"{shadow}:{os.environ.get('PATH', '')}",
             "RAW_OUT": str(out),
             "RAW_DEST": "/srv/rawarticle/bloomberg"},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "/srv/rawarticle/bloomberg" in marker.read_text(encoding="utf-8")
    assert "rawarticle/bloomberg" in result.stdout
    assert "rawarticle/ft" not in result.stdout
