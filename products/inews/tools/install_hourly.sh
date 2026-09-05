#!/usr/bin/env bash
# 把固定错峰的小时轮装进 launchd(**用户级 LaunchAgent,不是系统级 daemon**)。
#
# 为什么要有这个脚本:plist 里必须写**绝对路径** —— launchd 不认 `~`,也不认环境
# 变量。手抄那条路径是这一步最容易出错的地方,而抄错的后果不是报错,是任务指向
# 一个不存在的目录、然后**静默地什么都不做**:页面不变、退出码正常,人和监控都
# 看不出区别。这里从这份 checkout 自己的位置算出路径,填进去。
#
# 用户级而不是系统级:FT 是 manual 档,要开一个可见的、带登录态的 Chrome ——
# 那需要一个已登录的图形会话,系统 daemon 在登录之前就跑,没有会话可用。
#
# 卸掉:launchctl bootout gui/$(id -u)/today.inews.collector.hourly
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# 这两个只为用例存在:真机上就是 launchd 的标准位置和真的 launchctl。
AGENTS=${INEWS_LAUNCH_AGENTS:-$HOME/Library/LaunchAgents}
LAUNCHCTL=${INEWS_LAUNCHCTL:-/bin/launchctl}
SCHEDULE_PY=${INEWS_SCHEDULE_PYTHON:-$ROOT/.venv/bin/python}
SERVE_LABEL=today.inews.collector.serve
BOOTSTRAP_ATTEMPTS=${INEWS_BOOTSTRAP_ATTEMPTS:-3}
BOOTSTRAP_RETRY_SECONDS=${INEWS_BOOTSTRAP_RETRY_SECONDS:-1}

[ -x "$SCHEDULE_PY" ] || {
  echo "找不到可执行的定时表生成器 Python:$SCHEDULE_PY" >&2
  echo "先建立项目 .venv，或用 INEWS_SCHEDULE_PYTHON 指向项目 Python。" >&2
  exit 1
}
case "$BOOTSTRAP_ATTEMPTS" in
  ''|*[!0-9]*|0)
    echo "INEWS_BOOTSTRAP_ATTEMPTS 必须是正整数。" >&2
    exit 1
    ;;
esac

bootstrap_and_verify() {
  local label=$1 target=$2 attempt=1
  while [ "$attempt" -le "$BOOTSTRAP_ATTEMPTS" ]; do
    "$LAUNCHCTL" bootstrap "gui/$(id -u)" "$target"
    # launchctl 偶尔在 KeepAlive 任务刚 bootout 后报 EIO；以 registry 回读为准。
    if "$LAUNCHCTL" print "gui/$(id -u)/$label" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -lt "$BOOTSTRAP_ATTEMPTS" ]; then
      sleep "$BOOTSTRAP_RETRY_SECONDS"
    fi
    attempt=$((attempt + 1))
  done
  return 1
}

unload_and_verify() {
  local label=$1 attempt=1
  while [ "$attempt" -le "$BOOTSTRAP_ATTEMPTS" ]; do
    "$LAUNCHCTL" bootout "gui/$(id -u)/$label" >/dev/null 2>&1
    if ! "$LAUNCHCTL" print "gui/$(id -u)/$label" >/dev/null 2>&1; then
      return 0
    fi
    if [ "$attempt" -lt "$BOOTSTRAP_ATTEMPTS" ]; then
      sleep "$BOOTSTRAP_RETRY_SECONDS"
    fi
    attempt=$((attempt + 1))
  done
  return 1
}

# schedule.py 是唯一时刻表，也会确认每个已注册正文站点都有且只有一个时段。
# 先完整验证，再碰真机 LaunchAgents；缺站、撞分钟或资源间距不安全都会停在这里。
SCHEDULE_TABLE=$(PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  "$SCHEDULE_PY" -m inews.schedule --table) || {
  echo "正文采集时刻表校验失败；没有修改 launchd。" >&2
  exit 1
}
COLLECTOR_LABELS=()
SCHEDULE_SITES=()
SCHEDULE_DESCRIPTIONS=()
while IFS=$'\t' read -r site label minute resource_group calendar_text; do
  [ -n "$label" ] || continue
  SCHEDULE_SITES+=("$site")
  COLLECTOR_LABELS+=("$label")
  SCHEDULE_DESCRIPTIONS+=("$calendar_text")
done <<< "$SCHEDULE_TABLE"
SCRIPT_SITES=$(bash "$ROOT/tools/hourly.sh" --list-sites) || {
  echo "无法读取 hourly.sh 支持的站点；没有修改 launchd。" >&2
  exit 1
}
if [ "$(printf '%s\n' "${SCHEDULE_SITES[@]}")" != "$SCRIPT_SITES" ]; then
  echo "时刻表与 hourly.sh 支持的站点不一致；没有修改 launchd。" >&2
  echo "时刻表:$(printf '%s ' "${SCHEDULE_SITES[@]}")" >&2
  echo "脚本:$(echo "$SCRIPT_SITES" | tr '\n' ' ')" >&2
  exit 1
fi
LABELS=("${COLLECTOR_LABELS[@]}" "$SERVE_LABEL")

# 新任务逐个替换；任何一份 bootstrap/回读失败就把已经碰过的任务恢复成安装前
# 的 plist 与加载状态。这些字符串只是历史 launchd 标识，不依赖旧仓库仍然存在。
LEGACY_LABELS=(
  today.inews.paywall-ai.hourly
  today.inews.paywall-ai.serve
  today.inews.paywall-ai.bloomberg
)

if ! mkdir -p "$AGENTS" "$ROOT/out"; then
  echo "无法建立 LaunchAgents 或日志目录；没有修改 launchd。" >&2
  exit 1
fi
STAGE=$(mktemp -d /tmp/inews-launchd.XXXXXX) || {
  echo "无法建立 launchd 暂存目录；本次安装停止。" >&2
  exit 1
}
NEW_AGENTS="$STAGE/new"
OLD_AGENTS="$STAGE/old"
mkdir -p "$NEW_AGENTS" "$OLD_AGENTS"
cleanup_stage() { rm -rf "$STAGE"; }
trap cleanup_stage EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

# 先在 /tmp 完整生成和校验，不提前覆盖 ~/Library/LaunchAgents 里的可回滚版本。
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" \
  "$SCHEDULE_PY" -m inews.schedule --write-plists "$NEW_AGENTS" --root "$ROOT" || {
  echo "无法生成正文采集 LaunchAgents；本次安装停止。" >&2
  exit 1
}

[ -f "$ROOT/tools/launchd/$SERVE_LABEL.plist" ] || {
  echo "找不到 $ROOT/tools/launchd/$SERVE_LABEL.plist" >&2
  exit 1
}
sed "s|/Users/hermes/code/inews|$ROOT|g" \
  "$ROOT/tools/launchd/$SERVE_LABEL.plist" > "$NEW_AGENTS/$SERVE_LABEL.plist"

for label in "${LABELS[@]}"; do
  [ -f "$NEW_AGENTS/$label.plist" ] || {
    echo "找不到已生成的 $NEW_AGENTS/$label.plist" >&2
    exit 1
  }
  if [ -x /usr/bin/plutil ] && ! /usr/bin/plutil -lint "$NEW_AGENTS/$label.plist" >/dev/null; then
    echo "$label.plist 不是有效 plist；本次安装停止。" >&2
    exit 1
  fi
  if [ -f "$AGENTS/$label.plist" ]; then
    cp -p "$AGENTS/$label.plist" "$OLD_AGENTS/$label.plist" || {
      echo "无法备份原有 $label.plist；本次安装停止。" >&2
      exit 1
    }
  fi
  if "$LAUNCHCTL" print "gui/$(id -u)/$label" >/dev/null 2>&1; then
    : > "$OLD_AGENTS/$label.loaded"
  fi
done

# 历史任务也要先留原状快照。迁移不是“新任务装好就算完”：若清理到第三个才失败，
# 前两个同样必须能恢复，否则一次失败会把旧采集链拆成半套。
for legacy in "${LEGACY_LABELS[@]}"; do
  legacy_target="$AGENTS/$legacy.plist"
  if [ -f "$legacy_target" ]; then
    cp -p "$legacy_target" "$OLD_AGENTS/$legacy.plist" || {
      echo "无法备份历史 $legacy.plist；本次安装停止。" >&2
      exit 1
    }
  fi
  if "$LAUNCHCTL" print "gui/$(id -u)/$legacy" >/dev/null 2>&1; then
    if [ ! -f "$legacy_target" ]; then
      echo "$legacy 已加载但找不到 $legacy_target，无法保证失败回滚；本次安装停止。" >&2
      exit 1
    fi
    : > "$OLD_AGENTS/$legacy.loaded"
  fi
done

# 正文任务没有 RunAtLoad：安装只登记未来时刻，不会在这一刻多站齐跑。需要可见
# 浏览器的来源会使用脚本自己的专用 Chrome 窗口；CNBC 留在公开/无头资源组。
cat <<TXT
装 ${LABELS[*]}
  仓库:$ROOT
  plist 目录:$AGENTS

全部正文站都自动运行，固定错峰如下：
TXT
printf '  %s\n' "${SCHEDULE_DESCRIPTIONS[@]}"
cat <<TXT

安装后不会立刻抓取；各站等自己的下一个日历点。可见浏览器来源使用专用窗口且
彼此串行；CNBC 公开直抓，必要时只做无头兜底。系统唤醒或异常长轮造成撞车时，
同资源组会有界等待，不会同时挤占浏览器。

本机监听(today.inews.collector.serve)也一起装上:清单页上的「抓一轮」按钮
按下去就是敲它。它只绑 127.0.0.1,只认代码里写死的动作表。

TXT

TOUCHED_LABELS=""
rollback() {
  local rollback_failed=0 label target unloaded
  [ -n "$TOUCHED_LABELS" ] || return 0
  echo "安装未完整成功，正在恢复原有 LaunchAgents。" >&2
  for label in $TOUCHED_LABELS; do
    target="$AGENTS/$label.plist"
    unloaded=1
    if ! unload_and_verify "$label"; then
      echo "$label:无法确认当前任务已卸载；仍恢复磁盘 plist，但须人工核对运行态" >&2
      rollback_failed=1
      unloaded=0
    fi
    if [ -f "$OLD_AGENTS/$label.plist" ]; then
      if ! cp -p "$OLD_AGENTS/$label.plist" "$target"; then
        echo "$label:原 plist 恢复失败，请人工检查 $target" >&2
        rollback_failed=1
      elif [ -f "$OLD_AGENTS/$label.loaded" ] && [ "$unloaded" -eq 1 ]; then
        if ! bootstrap_and_verify "$label" "$target" >/dev/null 2>&1; then
          echo "$label:原任务恢复加载失败，请人工检查 $target" >&2
          rollback_failed=1
        fi
      fi
    else
      if ! rm -f "$target"; then
        echo "$label:无法恢复为原先的无 plist 状态，请人工检查 $target" >&2
        rollback_failed=1
      elif "$LAUNCHCTL" print "gui/$(id -u)/$label" >/dev/null 2>&1; then
        echo "$label:原先未加载，但回滚后仍在 launchd 中，请人工检查" >&2
        rollback_failed=1
      fi
    fi
  done
  return "$rollback_failed"
}

INSTALL_ACTIVE=1
abort_install() {
  local signal_code=$1
  # 回滚期间忽略重复信号；不能让第二次 Ctrl-C 把恢复动作拦腰截断。
  trap '' HUP INT TERM
  if [ -n "${CURRENT_TEMP_TARGET:-}" ]; then
    rm -f "$CURRENT_TEMP_TARGET"
  fi
  if [ "$INSTALL_ACTIVE" -eq 1 ] && [ -n "$TOUCHED_LABELS" ]; then
    rollback || true
  fi
  INSTALL_ACTIVE=0
  exit "$signal_code"
}
trap 'abort_install 129' HUP
trap 'abort_install 130' INT
trap 'abort_install 143' TERM

failed=0
CURRENT_TEMP_TARGET=""
for LABEL in "${LABELS[@]}"; do
  TARGET="$AGENTS/$LABEL.plist"
  TEMP_TARGET="$AGENTS/.$LABEL.plist.inews-new.$$"
  CURRENT_TEMP_TARGET="$TEMP_TARGET"
  # 先登记再碰目标；即使信号恰好落在 mv 与下一条命令之间，也能恢复这一份。
  TOUCHED_LABELS="${TOUCHED_LABELS}${TOUCHED_LABELS:+ }${LABEL}"
  if ! cp "$NEW_AGENTS/$LABEL.plist" "$TEMP_TARGET"; then
    rm -f "$TEMP_TARGET"
    echo "$LABEL:无法暂存新 plist 到 $TEMP_TARGET" >&2
    failed=1
    break
  fi
  # 必须先确认旧 label 真正消失，再换磁盘 plist。否则 bootstrap 报错后 print 到的
  # 可能仍是旧 StartInterval 任务，不能把“旧的还活着”误报成“新的装好了”。
  if ! unload_and_verify "$LABEL"; then
    rm -f "$TEMP_TARGET"
    echo "$LABEL:无法确认旧任务已卸载；没有替换它的 plist。" >&2
    failed=1
    break
  fi
  if ! mv "$TEMP_TARGET" "$TARGET"; then
    rm -f "$TEMP_TARGET"
    echo "$LABEL:无法原子写入 $TARGET" >&2
    failed=1
    break
  fi
  CURRENT_TEMP_TARGET=""
  if ! bootstrap_and_verify "$LABEL" "$TARGET"; then
    echo "$LABEL:多次 bootstrap/回读仍失败。plist 已写到 ${TARGET}，但 launchd 没接受它。" >&2
    failed=1
    break
  fi
  # **回读一次**:bootstrap 的退出码只说「收下了」。这个项目栽过的跟头都是同一种 ——
  # 命令成功了,事情没发生。装没装上,以 launchd 自己怎么说为准。
  echo "$LABEL 装上了"
done

echo
if [ "$failed" -ne 0 ]; then
  trap '' HUP INT TERM
  INSTALL_ACTIVE=0
  rollback || true
  exit 1
fi

legacy_failed=0
for legacy in "${LEGACY_LABELS[@]}"; do
  TOUCHED_LABELS="${TOUCHED_LABELS}${TOUCHED_LABELS:+ }${legacy}"
  if ! unload_and_verify "$legacy"; then
    echo "$legacy:旧任务仍在 launchd 中；拒绝让新旧任务同时运行。" >&2
    legacy_failed=1
    break
  fi
  if ! rm -f "$AGENTS/$legacy.plist"; then
    echo "$legacy:无法删除旧 plist；请检查 $AGENTS/$legacy.plist" >&2
    legacy_failed=1
    break
  fi
done

if [ "$legacy_failed" -ne 0 ]; then
  trap '' HUP INT TERM
  INSTALL_ACTIVE=0
  rollback || true
  exit 1
fi

INSTALL_ACTIVE=0

echo "${#LABELS[@]} 个任务都装上了：全部正文站固定错峰 + 本机监听。旧独立仓库任务已卸载。"
echo "各来源日志在 $ROOT/out/*hourly.log；监听日志:$ROOT/out/serve.log"
echo "看它跑:tail -f $ROOT/out/hourly.log"
