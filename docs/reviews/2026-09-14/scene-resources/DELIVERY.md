# 场景资源生命周期交付

## 已实现

实施前提交 7443588 已登记基线 765 个文件、75 处资源引用、16 个计划路径及旧实现退出清单。新增 `scene-resources.js`：环境所有者以代次管理 HDR 成功、失败/超时 fallback、重试、PMREM target 原子替换、迟到输入回收和幂等退出；纹理池统一 CanvasTexture 和稳定图片纹理，图片失败保留程序化像素，成功在同一 texture 身份上更新，退出一次释放。

bom3d 与 rack3d 是环境和 CanvasTexture 的全部交互页面消费者；rack3d 的五张面板改为共享图片 handle。两页删除重复 EXR/PMREM 提交及 ctex 实现，pagehide 停止 animation frame 后释放环境、纹理池、composer 和 renderer。页面仍拥有光照/纹理绘制配方、几何、材质、选取、相机与研究映射。静态路由发布新模块；HDR/面板 README 修正运行事实。专门测试直接消费两个公共工厂；scene_framing、model_assets 和 run_browser 是页面回归消费者。逐引用迁移见 consumers-after.csv。

退出项：无 target 句柄的 PMREM、迟到回调改写场景、两份 ctex、忽略 fallback 的 panel、只打印兜底文案的失败 Texture、遗漏本批 GPU 所有者的 pagehide。程序化配方是迁移后的领域输入，没有删除。`bake.html` 的离线输出生命周期和 compare 的局部 RoomEnvironment 保留，理由见 legacy-removal；它们没有被描述为公共实现消费者已迁移。

## 已验证

专门浏览器测试验证首次 HDR、失败、超时后迟到、并发 retry、A→fallback→A、旧 target 与输入各释放一次、dispose 后清空；图片失败/重试保留同一非空程序化纹理，真实 PNG 成功仍保留身份，handle/pool 重复 dispose 只释放一次。对 bom3d/rack3d 实际页面注入 EXR 503 和五张面板 503，两页均保留程序化环境，机柜五张纹理均 fallback；两次 dispose 只释放一次 renderer/composer，60ms 后渲染计数不再变化。

共享资源测试 8 秒通过；场景构图/用户镜头 25 秒通过；三个真实 GLB 模型失败、重试、整批替换与回收场景分别 20/14/2 秒通过。测试只修改浏览器请求，不写生产或仓库业务数据。

全量浏览器、Python 单元、governance、strict、registry、asset-check、CI、合并、生产 HTTPS/登录/精确版本仍待执行；完成后在同一批证据中更新，不用本地相关测试冒充上线。

## 未完成

两页仍分别是大型几何/材质/交互脚本；本批没有迁移 bake、compare、下钻 levels 加载，也没有全面释放场景几何/material、OrbitControls、选取监听或处理 WebGL context lost。真实多型号 GPU 内存、帧率、长时间切页和全部触摸设备未验。研究接口体积、跨机器全文结果、原件质量及全站逐页 Attio/folk 人工验收继续未完成；Spark/M4 未连接或迁移。
