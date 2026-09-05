# products/ —— inresearch 产品

本目录只有一个产品：`inresearch/`（inresearch.ai，Python 标准库，身份实现在
`pipeline/auth.py`、`pipeline/users.py`）。

inews.today 曾在 2026-09-05 被复制到本目录下的 `inews/` 作为「平行产品」，同日站长
决定两个产品完全分开：inews 回到它自己的仓库
[niuroumiantt/inews.today](https://github.com/niuroumiantt/inews.today)，本目录不再保留副本。
infra 的 `hosts/apps.json` 里 inews 也不再指向本仓库。

## 与 inews 唯一允许的连接：内容接口

inresearch **采用** inews 的内容，但这是内容的流动，不是身份的流动。

- 契约：inews.today 仓库根目录的 `CONTENT_INTERFACE.md`（由内容提供方维护）
- 采用方实现：[`inresearch/pipeline/inews_adoption.py`](inresearch/pipeline/inews_adoption.py)
- 验收：`inresearch/pipeline/test_inews_adoption.py`（19 项）

四条铁律：

1. **不传递身份**——内容包里出现 `user` / `email` / `member` / `session` / `token`
   等任何身份字段（任何嵌套层级），采用方直接拒绝整个包。
2. **不跨库直读**——inresearch 不连 inews 的数据库、不读它的用户表或业务表。
3. **引用固定版本**——`package_version` 由内容摘要算出；内容被改过则版本对不上，
   采用方拒绝。研究成果引用的是**采用记录**，不是「当前的 inews」。
4. **单向**——inresearch 不向 inews 写任何东西。

`inresearch` 是独立运营的研究产品，**不是 inews 的后台或展示页**：
它除了采用新闻，还直接接收其他研究资料。
