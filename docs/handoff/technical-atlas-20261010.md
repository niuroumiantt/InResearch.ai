# 技术图册持续制作交接（2026-10-10，m4）

## 目标
完成原TA01–35逐图制作、审图、网页与真实发布闭环；TA36–39补充四项单独计量。这个文件是交接快照，实际状态始终读当前机器队列与逐项publication。

## 已定规则（不要重复问）
- 用户已明确授权自主制作、修正、开PR、合并/关闭本任务PR、部署和实读上线；不查询或等待CI，不冒称CI通过。每小时中文汇报，即使尚无新增完成；新图用真实绝对路径直接贴当前聊天。
- 本聊天只推进图册；研究PR、接收和研究服务由另一个对话处理。不干预Spark、研究队列、M5发布服务或研究事实。
- 用户要求同主题合成较实质PR。后续提交单元：21 → 22–23 → 24–27 → 28 → 29 → 30–34 → 35。批内仍按图号逐张制作、独立技术/视觉/页面验收与状态；正式规范、execution、计划和验证合同须同步。前项完成后的发布记录可随下一单元源码同交，分别绑定实际源码/应用版本与登记版本。
- 本地50166产品页面曾被浏览器权限明确拒绝。不得换端口、浏览器、headless、file或间接途径访问该页面；只做明确无HTTP静态/parse检查、离线单资产检查，以及正常授权发布后的独立许可公网HTTPS验收。TA17旧单测隐含localHTTP的偏差已记录并停用，不复用为通过依据。
- 保留原件、旧稿/拒稿、原生尺寸、来源角色、独立SVG与实际检查回执。新位图省略引用参数；编辑传已实看的实际目标，区分风格参考实看与实际工具输入。技术数量/连接、权利或OEM参数不由图片推定。

## 当前精确进度
- 实际完成20/35、补充4/4。TA20最终修复PR571于2026-10-09T23:04:48Z合并ef918aaa567ddd3ad013a10756112bd75b739fdd/.59；23:08:12Z source=applied与精确0e962a54镜像running/healthy。
- TA20 public-v3实际PASS、四页面/完整SVG/双下载SHA、5声明资源直接200、13源码资源SHA/health200及原TA18/19渲染完整；7图owner/独立原尺寸复审。真实firstpublication是ef918/.59，本次TA21只是登记提交，不能倒写历史。
- TA21工作树 /Users/m4/.codex/worktrees/atlas-ta21-facility/inresearch.ai，基线ef918/.59，分支codex/atlas-ta21-facility。已制作独立原生1536×1024设施领域母图/4可编辑标签；source review，真实新页面/领域面板/下载/精确部署待验，不计21。
- 本提交将main机器队列从19登记到20，下一TA21；批次22–23以后仍未制作。source_ready不冒充公网accepted。
- TA20完整原字节回执 /Users/m4/.local/share/inresearch.ai/technical-atlas-audit/2026-10-10/TA-20/final-publication-receipt.json；最终public-v3与fix-deployment-healthy.json同目录。

## 下一步
1. TA21源码/规范/合同/交接与TA20发布登记同PR，本地只明确无HTTP静态/parse/离线单资产；真实新产品网页在正常授权公网部署后核验。
2. TA21实际完成后按22–23、24–27、28、29、30–34、35提交单元顺序继续。批内逐图制作审图，逐项公网回执与sourceSHA，前项pub随下一实质source。
3. 四旧专页(server-plan/chip-atlas/rack-atlas/rack-exploded)最小清除重复无路由site-shell module，有效site-skin保留；实际公网直200另验，明确微改不声称零diff。
4. TA35全部真实闭包后最终登记，并停止小时自动任务。

## 待用户决定
无相同业务批准待决。工具权限拒绝须准确报原因，不写文件/换途径绕过。现有ACTIVE小时heartbeat id=automation绑定当前聊天；更新提示词工具曾返回“requires approval, but approval policy is never”，未替写TOML、未创建重复任务。聊天最新指令及现行规范优先于旧自动提示。

## 入口与现场
- 常驻源码 /Users/m4/code/inresearch.ai 保持clean但落后；不要切换、reset、stash或带入其它工作。图册使用Codex自管独立工作树。
- 当前TA20树 /Users/m4/.codex/worktrees/atlas-ta20-campus-plan/inresearch.ai；实际后续树以owner及app attachments为准。
- 唯一规则 framework/10_visual_atlas.md；机器状态 framework/visual_atlas_migration.json；计划 docs/design/technical-atlas/MIGRATION_PLAN.md；逐图 docs/design/technical-atlas/TA-XX/{acceptance-v1.json,publication-YYYYMMDD.json}。
- 本机原图、失败稿、实际公网截图与健康原字节 /Users/m4/.local/share/inresearch.ai/technical-atlas-audit/2026-10-09/TA-16/ 及 /Users/m4/.local/share/inresearch.ai/technical-atlas-audit/2026-10-10/TA-17…21/。不删唯一资料。
- 每次人工审阅验证合同后治理refresh/check、严格validate、registry及适用检查；生产由既有inresearch-only-deploy.timer自然应用，图册只观察与核验，不改调度。
