# inews → inresearch 内容接口契约

inews.today 与 inresearch.ai 是**平行产品**，不是前后台。inresearch 采用 inews 的内容，
但两者的账号、会员、权限各自管理。本文件定义两者之间唯一允许的连接方式。

## 铁律

1. **不传递身份。** 内容包里不得出现用户、会话、会员、订阅、邮箱或任何主体标识。
   inresearch 不因为采用了 inews 的内容而知道 inews 的任何用户是谁。
2. **不跨库直读。** inresearch 不连接 inews 的数据库、不读它的用户表或业务表。
   唯一的通路是本文件定义的内容包。
3. **引用固定版本，不引用「最新」。** 每次采用记录 `package_version`。
   同一份研究成果在任何时候重放，引用到的都是同一份内容。
4. **单向。** inresearch 不向 inews 写任何东西。

## 内容包格式

```json
{
  "schema_version": 1,
  "package_version": "<32 位十六进制，内容摘要>",
  "produced_at": "<RFC3339>",
  "source": "inews.today",
  "items": [
    {
      "item_id": "<稳定标识>",
      "title": "...",
      "summary": "...",
      "published_at": "<RFC3339>",
      "origin_url": "https://…",
      "origin_domain": "example.com",
      "topics": ["..."],
      "language": "en"
    }
  ]
}
```

`package_version` 由内容本身算出（见 `content_package.py` 的 `compute_version`），
所以同样的内容一定得到同样的版本号，内容变了版本号一定变。

## 禁止出现的字段

以下字段名在内容包的**任何嵌套层级**出现都判为违约，采用方直接拒绝整个包：

`user`、`user_id`、`users`、`account`、`account_id`、`email`、`member`、`member_id`、
`membership`、`subscriber`、`subscription`、`session`、`session_id`、`token`、
`password`、`auth`、`credential`、`api_key`

这不是「谨慎起见」——手册第 3 节明确禁止「与研究会员互认登录、借用另一产品管理密码」。
身份一旦顺着内容包流过去，两个产品的授权边界就不再独立。

## 采用记录

inresearch 每次采用都写一条记录：包版本、采用时间、采用了哪些条目。
研究成果引用新闻时引用的是**采用记录**，不是「当前的 inews」。
