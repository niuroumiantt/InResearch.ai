# NVIDIA 产品规格库交接

## 当前目标

2026-09-27 用户采用：先清点 NVIDIA 官方目录中的产品，逐产品寻找官方规格，以各自参数目录形成数据库，本站轻量呈现并导出 CSV。本轮 M5→AWS，Spark 不参与。正式规范见 framework/06_acquisition.md。

## 代码与数据

- Fetchspec：`python3 -m fetchspec.product_catalog --out /Users/m5/Downloads/tempfetch --max-pages 220 --reparse`（PYTHONPATH=src）。以官方 products 总目录为起点，目录/型号相关链接扩展，持久 frontier，可重复启动续跑；`--reparse` 重用旧页面快照补充解析。
- M5 原件：`/Users/m5/Downloads/tempfetch/blobs/<SHA前2位>/<SHA>.html`；发现台账和交付：`product-catalog/nvidia/{discovery.sqlite3,catalog.json}`，保留原有 PDF。
- inresearch 接收：`INRESEARCH_RUNTIME_ROOT=/Users/m5/.local/share/inresearch.ai python3 manage.py product-catalog import --input <catalog.json> --archive-root /Users/m5/Downloads/tempfetch`。
- 私有运行数据库：`data/raw/product-catalog/nvidia.sqlite3`；产品、历史、来源、参数表独立持久化。GET `/api/product-catalog/nvidia` 遵守网站登录；POST 使用现有 NVIDIA 专用交付凭证，不使用 Spark 凭证。
- 页面 `/product-catalog.html`：筛选、每产品官方表格、并排核查、CSV。资料验证页提供入口。源码不包含抓取数据。

## 验收与未完成

验收包括来源/跨度/外链校验，重复与陈旧交付，历史保留，CSV 公式转义、配置列和脚注保存；浏览器检验真实表格呈现、筛选、错误恢复和移动端。

数量以运行台账为准，官方目录条目不等于全部 SKU。型号识别仍是待复核规则，系列、平台、软件独立计数；具体配置拆分、在售确认、动态规格/PDF 定向解析、网络文档站产品型号补齐和跨产品公共参数映射仍需继续。不可将 frontier 耗尽称为全公司产品穷尽。

旧 OCR 试验的未提交修改保留在 nvidia-progress-live-20260927 工作树，未混入本批。主工作区还有其他任务的未提交修改，未改动。
