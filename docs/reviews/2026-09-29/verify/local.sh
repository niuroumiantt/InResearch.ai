#!/usr/bin/env bash
# 在你自己的电脑上跑（有 AWS CLI 凭证与外网的那台，例如 M5）。只读。结果写到 ~/inresearch-verify-local-<日期>.txt。
# 需要：dig、curl；AWS 部分需要已配置的 aws CLI（没有就跳过，会打印提示）。
set -u
OUT="$HOME/inresearch-verify-local-$(date +%F).txt"
{
echo "==== 0 本机"; hostname; date -Is
echo; echo "==== 1 从外面看 DNS 与 TLS（判断 Cloudflare 回源遗留）"
for n in inresearch.ai www.inresearch.ai inews.today www.inews.today; do
  printf '%-18s A=' "$n"; dig +short A "$n" | tr '\n' ' '; printf ' CNAME='; dig +short CNAME "$n" | tr '\n' ' '; echo
done
printf 'NS inresearch.ai = '; dig +short NS inresearch.ai | tr '\n' ' '; echo
printf 'NS inews.today   = '; dig +short NS inews.today | tr '\n' ' '; echo
for n in inresearch.ai www.inews.today; do echo "-- $n 响应头:"; curl -sI "https://$n/" | grep -iE '^(HTTP|server|strict-transport|x-content-type|cf-ray|via)'; done
echo "-- 证书签发者:"; echo | openssl s_client -connect inresearch.ai:443 -servername inresearch.ai 2>/dev/null | openssl x509 -noout -issuer -enddate 2>/dev/null
echo; echo "==== 2 Lightsail 自动快照与套餐（需要 aws CLI）"
if command -v aws >/dev/null 2>&1; then
  aws lightsail get-instances --query 'instances[].[name,bundleId,publicIpAddress,hardware.ramSizeInGb,hardware.disks[0].sizeInGb]' --output table
  for inst in $(aws lightsail get-instances --query 'instances[].name' --output text); do
    echo "-- $inst 自动快照（最近 3 个）:"; aws lightsail get-auto-snapshots --resource-name "$inst" --query 'autoSnapshots[0:3].[date,status]' --output table 2>&1 | head -12
    echo "-- $inst 快照开关:"; aws lightsail get-instances --query "instances[?name=='$inst'].addOns[].[name,status,snapshotTimeOfDay]" --output table
  done
  echo "-- 套餐价格:"; aws lightsail get-bundles --query 'bundles[].[bundleId,price,ramSizeInGb,diskSizeInGb]' --output table | head -30
else
  echo "(本机没有 aws CLI；在 Lightsail 控制台 → 实例 → 快照 页手动看'自动快照'是否启用，并在 → 账单 看套餐月费)"
fi
echo; echo "==== 完成，结果已写到 $OUT"
} 2>&1 | tee "$OUT"
