# products/ —— 两个独立的研究业务产品

按收敛方案，本仓库承载 **inews** 与 **inresearch** 两个**平行产品**。
它们共用一个仓库，但**不共用身份、会员、数据库或发布**。

| 目录 | 域名 | 技术栈 | 身份实现 |
|---|---|---|---|
| `inews/` | inews.today | Node.js + Python 采集 | `src/auth/`（crypto/gate/routes/schema/smtp/store） |
| `inresearch/` | inresearch.ai | Python 标准库 | `pipeline/auth.py`、`pipeline/users.py` |

## 独立到什么程度

手册第 1 节第 2 条：**不建设统一账号中心，不按邮箱自动关联身份，
不靠跨系统账号同步脚本维持权限正确性。**

- 两套用户库、两套会话、两套会员、两套停用与授权，各自管理。
- 同一个人在两边分别注册或分别接受邀请。
- 在一边停用某人，**不会**影响另一边——这是设计，不是缺陷。
- 两个产品各自独立发布：改 `products/inews/` 不会重建 inresearch，
  反之亦然（见 infra 仓库 `hosts/apps.json` 的 `paths` 映射）。

## 唯一允许的连接：内容接口

inresearch **采用** inews 的内容，但这是内容的流动，不是身份的流动。

- 契约：[`inews/CONTENT_INTERFACE.md`](inews/CONTENT_INTERFACE.md)
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
