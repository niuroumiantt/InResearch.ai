# 精细底图与州省边界（2026-10-11，m5）

用户要求地图放大更清晰并显示州界。保留浅色设计/首页布局，首次放大同源按需加载固定Natural Earth 1:10m国界/海岸与全球一级行政区；进一步放大显示州省界，复位隐藏。异步只更新底图层，原项目DOM/锚点/点尺寸与固定详情保持，失败可重试。边界non-scaling-stroke；旧world.geo.json和研究国家示意点原字节保持。

来源/许可/原始SHA、派生容差与复现见 web/assets/maps/README.md 和 scripts/build_world_detail.py，派生10436条几何，未定位来源记录跳过。原始下载使用临时目录，不入Git；初次本机大文件传输失败后使用AWS独立/tmp目录获取固定公开原件与派生，仅用于资产制作，不改生产运行数据。

本地industry、datacenter_news、ui_skin、url_rendering浏览器通过，含真实新增资源、恒定线宽、复位与503后重试；治理、严格数据和registry通过。完整单元、最终head CI及真实部署/公网实测须继续完成，在本次PR保存回执，不以本交接冒充上线。无待用户决定事项。
