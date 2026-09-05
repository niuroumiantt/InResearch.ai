#!/usr/bin/env bash
# **双击这个文件就跑一轮**(Finder 里双击,或者拖到 Dock/桌面做个快捷方式)。
#
# 为什么是一个 .command 而不是页面上的按钮:产出是静态 HTML,这个项目没有
# 服务端 —— 服务器上那份页面里的按钮点下去,也够不着你 Mac 上的 Chrome 和
# 你的登录态。要让网页按钮真的能触发,得在本机常驻一个监听端口的进程,
# 那是另一件事(而且是要先问过站长的那类改动)。
#
# 跑的就是每小时那一轮 `tools/hourly.sh`:同一把锁、同一份日志、同样不重试。
# 定时任务正在跑的时候你双击它,会看到「上一轮还在跑」然后退出 —— 那是对的。
#
# **这一轮会打开一个可见的 Chrome 窗口**(FT 是 manual 档),窗口关掉这一轮就废了。
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

printf '\033[1m抓一轮 inews\033[0m  %s\n' "$(date -Iseconds)"
printf '日志:%s\n\n' "$ROOT/out/hourly.log"

bash "$ROOT/tools/hourly.sh"
code=$?

echo
if [ "$code" -eq 0 ]; then
  printf '\033[32m这一轮跑完了\033[0m → https://inews.today/rawarticle/ft/\n'
else
  # 失败**留在屏幕上**:双击跑的窗口一闪而过的话,失败和成功长得一模一样。
  printf '\033[31m这一轮失败了(退出码 %s)。没有发布,服务器上还是上一轮那份。\033[0m\n' "$code"
  printf '最近几行日志:\n'
  tail -n 15 "$ROOT/out/hourly.log" 2>/dev/null || true
fi

echo
read -r -n 1 -p "按任意键关掉这个窗口 " _
exit "$code"
