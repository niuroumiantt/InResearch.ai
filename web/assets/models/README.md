# 已登记的 3D 视觉输入

`manifest.json` 是本目录唯一发布登记，具体规则见
[03 对象与协作](../../../framework/03_bom_and_collaboration.md)，
操作见 [模型接收与采用](../../../docs/local_setup/ADD_3D_MODEL.md)。

文件保留来源、许可和真实 SHA-256；candidate 供比较，adopted 进入指定场景，
rejected 保留但不自动加载。下载和网格统计都不授予采用资格。
现有 server_v2_console.glb 延续既有明确不采用决定，文件字节不变。

运行 `python3 manage.py asset-check` 检查同一契约。
新模型不需要复制 routes 条目；未登记文件仍不可访问。
