# 场景资源生命周期与脚本拆分：实施前交付

此文是本批审计快照，不是现行规范入口。基线为 52eaad0；先登记职责、消费者、全文件处置和退出项，再修改运行代码。

## 现状证据

`bom3d.html` 为 1027 行，`rack3d.html` 为 749 行。两页各自重复创建 EXRLoader、临时摄影棚 Scene、PMREMGenerator 与 CanvasTexture。PMREM 返回的 WebGLRenderTarget 只留下 `.texture`，没有保存或释放 render target；HDR 迟到成功可在页面退出或回退后重新写 `scene.environment`。两页 pagehide 只释放视口、可选模型和查看器，没有释放环境 target、页面 CanvasTexture、composer 或 renderer。

机柜页 `panel(name, fallback)` 从不使用 fallback，调用处也没有传 fallback；加载失败只打印“程序化面板兜底”，材料仍引用失败的空 Texture。README 的“自动回退”因此与实现不一致。HDR 的失败回退确实存在，本批不把它误报为同一问题。引用与所有调用点见 consumers-before.csv；可执行反例将在代码前写入 baseline.json。

## 目标职责与权威

新增 `web/components/scene-resources.js`，只拥有浏览器 GPU/纹理资源：

- 环境所有者负责 EXR 加载、超时、fallback、PMREM target 提交、A→B→A 替换、迟到结果丢弃及释放；页面只提供 HDR URL 与程序化摄影棚配方。
- 纹理池负责 CanvasTexture 创建、图片画入同一稳定 CanvasTexture、失败保留程序化像素，以及一次性释放；页面只提供领域绘制函数。
- 页面仍拥有场景几何、灯光、动画、选取、研究映射和材质组合。`scene-view.js` 继续只拥有视口/镜头，不吸收资源加载。
- `web/assets/hdri` 与 `web/assets/panels` 及其来源登记仍是视觉输入权威；组件不决定采用、许可或业务语义。

## 全文件迁移与消费者

file-plan.csv 覆盖基线全部 765 个文件和本批新增文件。计划修改新共享组件、两个消费者页面、静态路由、两个资产 README、浏览器测试入口、现行 UI/软件规范、状态、验收映射、决策摘要与在册清单。其他文件逐项保留，原件、事实、账号和运行数据库不迁移。

公共实现的全部在库消费者先登记为：bom3d、rack3d；专门资源测试直接消费 API；scene_framing 与 model_assets 作为页面回归消费者；静态 HTTP 路由发布模块。`bake.html` 仍是离线烘焙工具，生命周期与交互页面不同，本批明确保留为未迁移消费者候选，不偷偷扩大公共契约。compare 使用自己的简单 RoomEnvironment 且已有局部 dispose，保留并记录理由。

## 旧实现删除清单

删除两页重复的环境加载/提交实现、局部 ctex、机柜空 TextureLoader 兜底和 pagehide 缺失的资源释放。页面的程序化环境配方与纹理绘制内容迁为传入共享所有者的配置，不删除视觉设计。旧 URL、DOM、业务几何、相机、选取、可选模型及研究映射全部保留。

## 验证计划与边界

用真实 Three 对象验证首次成功、网络失败、超时后迟到成功、重试 A→fallback→A、并发重试只提交最新代、替换 target 只释放一次、页面退出后不复活；图片成功与失败均保持同一 Texture 身份，失败像素非空，dispose 后迟到图片不改写。两实际页面在桌面/360px、HDR 503、面板 503、重试和 pagehide 下验证，无生产写入。

运行完整浏览器、1023+ 单元、governance、strict、registry、asset-check、生产 HTTPS/登录/版本核对。通过仍只证明这个资源边界；大型几何构建、渲染循环、bake 工具、研究接口体积、全文跨机器权威和全站 UI 逐页验收继续列为未完成。
