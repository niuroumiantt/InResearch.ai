"""Mac mini 上的正文采集时刻表与 LaunchAgent 生成器。

这里是**唯一的定时来源表**。新增站点时，``inews.sites.REGISTRY`` 和这里必须
同时登记；否则模块加载和测试都会明确失败，不能再出现「站点已经能抓，但忘了装
定时任务」的静默断档。

时刻按 24 小时周期固定错开。``resource_group`` 决定跨站并发边界：使用站长
日常 Chrome 的站共享一个槽，公开/无头来源共享另一个槽。常规站可每小时运行，
展开成本较高的新站也可声明隔小时；日历时刻只是第一层隔离，资源锁还会处理异常
长轮、手动触发和系统唤醒后的集中补跑。
"""
from __future__ import annotations

import argparse
import os
import plistlib
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from inews import sites
from inews.browser import tiers

DAILY_CHROME = "daily_chrome"
HEADLESS = "headless"
RESOURCE_GROUPS = frozenset((DAILY_CHROME, HEADLESS))

# 任意两条日历任务至少隔 5 分钟；共用日常 Chrome 的重任务至少隔 15 分钟。
# 未来没有安全空位时，应明确降低某个低收益站的频率或增加机器，而不是挤在同一分钟。
MIN_ANY_GAP = 5
MIN_DAILY_CHROME_GAP = 15


@dataclass(frozen=True)
class CollectorSchedule:
    site: str
    label: str
    minute: int
    resource_group: str
    log_prefix: str
    # 空组表示每小时；否则只在列出的本地小时运行。launchd 的
    # StartCalendarInterval 原生支持一组 {Hour, Minute}，无需常驻调度进程。
    hours: tuple[int, ...] = ()


EVEN_HOURS = tuple(range(0, 24, 2))
ODD_HOURS = tuple(range(1, 24, 2))


SCHEDULES: tuple[CollectorSchedule, ...] = (
    CollectorSchedule("ft", "today.inews.collector.hourly", 5, DAILY_CHROME, "launchd"),
    CollectorSchedule(
        "bloomberg", "today.inews.collector.bloomberg", 20, DAILY_CHROME,
        "bloomberg-launchd",
    ),
    # :35 是可见 Chrome 在 :20 与 :50 之间唯一满足 15 分钟安全间距的槽。
    # CNBC 公共/无头轮前移到 :27，给新增的两条重型发现线隔小时轮换 :35。
    CollectorSchedule("cnbc", "today.inews.collector.cnbc", 27, HEADLESS, "cnbc-launchd"),
    CollectorSchedule("wsj", "today.inews.collector.wsj", 50, DAILY_CHROME, "wsj-launchd"),
    CollectorSchedule(
        "reuters", "today.inews.collector.reuters", 35, DAILY_CHROME,
        "reuters-launchd", ODD_HOURS,
    ),
    CollectorSchedule(
        "axios", "today.inews.collector.axios", 35, DAILY_CHROME,
        "axios-launchd", EVEN_HOURS,
    ),
)


def _circular_gaps(minutes: Iterable[int], *, period: int = 60) -> list[int]:
    ordered = sorted(minutes)
    if len(ordered) < 2:
        return []
    return [
        (ordered[(index + 1) % len(ordered)] - minute) % period
        for index, minute in enumerate(ordered)
    ]


def _events(spec: CollectorSchedule) -> tuple[int, ...]:
    """把一条 launchd 日历声明展开成一天内的绝对分钟。"""
    hours = spec.hours or tuple(range(24))
    return tuple(hour * 60 + spec.minute for hour in hours)


def validate_schedules(
    schedules: Iterable[CollectorSchedule] = SCHEDULES,
    *,
    registered_sites: Iterable[str] | None = None,
) -> tuple[CollectorSchedule, ...]:
    """验证覆盖、唯一性和本机资源间距，返回稳定的 tuple。"""
    values = tuple(schedules)
    expected = set(registered_sites if registered_sites is not None else sites.REGISTRY)
    scheduled = {item.site for item in values}
    if scheduled != expected:
        missing = sorted(expected - scheduled)
        extra = sorted(scheduled - expected)
        raise ValueError(f"正文站点与定时表不一致；缺少={missing}；多出={extra}")
    if len(scheduled) != len(values):
        raise ValueError("同一正文站点只能有一条定时任务")
    labels = [item.label for item in values]
    if len(set(labels)) != len(labels):
        raise ValueError("LaunchAgent label 必须唯一")
    minutes = [item.minute for item in values]
    if any(not 0 <= minute <= 59 for minute in minutes):
        raise ValueError("定时分钟必须在 0..59")
    for item in values:
        if len(set(item.hours)) != len(item.hours):
            raise ValueError(f"{item.site} 的定时小时不能重复")
        if any(not 0 <= hour <= 23 for hour in item.hours):
            raise ValueError(f"{item.site} 的定时小时必须在 0..23")
    unknown = sorted({item.resource_group for item in values} - RESOURCE_GROUPS)
    if unknown:
        raise ValueError(f"未知资源组:{', '.join(unknown)}")
    undeclared_tiers = sorted(
        site for site in expected if tiers.tier_of(site) not in tiers.TIERS
    )
    if undeclared_tiers:
        raise ValueError(
            "正文站点缺少有效浏览器档位声明:" + ", ".join(undeclared_tiers)
        )
    mismatched = sorted(
        item.site
        for item in values
        if item.resource_group
        != (DAILY_CHROME if tiers.requires_visible_browser(item.site) else HEADLESS)
    )
    if mismatched:
        raise ValueError(f"定时资源组与浏览器档位不一致:{', '.join(mismatched)}")
    events = [event for item in values for event in _events(item)]
    if len(set(events)) != len(events):
        raise ValueError("两个正文站点不能安排在同一个日历时刻")
    if any(gap < MIN_ANY_GAP for gap in _circular_gaps(events, period=24 * 60)):
        raise ValueError(f"任意两个定时任务至少间隔 {MIN_ANY_GAP} 分钟")
    visible = [
        event
        for item in values if item.resource_group == DAILY_CHROME
        for event in _events(item)
    ]
    if any(
        gap < MIN_DAILY_CHROME_GAP
        for gap in _circular_gaps(visible, period=24 * 60)
    ):
        raise ValueError(
            f"共用日常 Chrome 的任务至少间隔 {MIN_DAILY_CHROME_GAP} 分钟"
        )
    return values


def launch_agent(spec: CollectorSchedule, *, root: Path) -> dict[str, object]:
    """生成一份无 ``RunAtLoad`` 的用户级 LaunchAgent。"""
    environment = {
        "INEWS_SCHEDULED": "1",
        "INEWS_RESOURCE_GROUP": spec.resource_group,
    }
    if spec.resource_group == DAILY_CHROME:
        # 自动任务永远使用脚本自己的专用窗口，不切换站长正在看的 Chrome 标签页。
        environment["YIDIAN_LOCAL_SYNC_DEDICATED_WINDOW"] = "1"
    calendar: object = (
        [{"Hour": hour, "Minute": spec.minute} for hour in spec.hours]
        if spec.hours
        else {"Minute": spec.minute}
    )
    return {
        "Label": spec.label,
        "ProgramArguments": [
            "/bin/bash",
            str(root / "tools" / "hourly.sh"),
            spec.site,
        ],
        "StartCalendarInterval": calendar,
        "WorkingDirectory": str(root),
        "StandardOutPath": str(root / "out" / f"{spec.log_prefix}.out.log"),
        "StandardErrorPath": str(root / "out" / f"{spec.log_prefix}.err.log"),
        "ProcessType": "Background",
        "EnvironmentVariables": environment,
    }


def _write_plist_atomic(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            plistlib.dump(payload, handle, fmt=plistlib.FMT_XML, sort_keys=False)
        os.chmod(name, 0o644)
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def write_launch_agents(directory: Path, *, root: Path) -> tuple[Path, ...]:
    written: list[Path] = []
    for spec in validate_schedules():
        target = directory / f"{spec.label}.plist"
        _write_plist_atomic(target, launch_agent(spec, root=root))
        written.append(target)
    return tuple(written)


def schedule_lines() -> tuple[str, ...]:
    def calendar_text(item: CollectorSchedule) -> str:
        if not item.hours:
            cadence = "每小时"
        elif item.hours == EVEN_HOURS:
            cadence = "偶数小时（每 2 小时）"
        elif item.hours == ODD_HOURS:
            cadence = "奇数小时（每 2 小时）"
        else:
            cadence = ",".join(f"{hour:02d}" for hour in item.hours) + " 时"
        return f"{sites.get(item.site).LABEL} {cadence} :{item.minute:02d}"

    return tuple(
        f"{item.site}\t{item.label}\t{item.minute:02d}\t{item.resource_group}"
        f"\t{calendar_text(item)}"
        for item in validate_schedules()
    )


def cadence_for_site(site_key: str) -> str:
    """给页面显示的简短频率；事实仍只来自这张定时表。"""
    item = next((value for value in SCHEDULES if value.site == site_key), None)
    if item is None:
        return "定期一轮"
    if not item.hours:
        return "每小时一轮"
    if item.hours in {EVEN_HOURS, ODD_HOURS}:
        return "每 2 小时一轮"
    return "按固定时段运行"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成并核对本机正文采集 LaunchAgents")
    parser.add_argument("--write-plists", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--labels", action="store_true")
    parser.add_argument("--table", action="store_true")
    args = parser.parse_args(argv)
    values = validate_schedules()
    if args.write_plists:
        write_launch_agents(args.write_plists, root=args.root.resolve())
    if args.labels:
        print("\n".join(item.label for item in values))
    if args.table:
        print("\n".join(schedule_lines()))
    if not (args.write_plists or args.labels or args.table):
        parser.error("至少指定 --write-plists、--labels 或 --table")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
