# 放大地图矢量资源

world-detail.geo.json 是放大时按需加载的 Natural Earth 1:10m（1:1000万）派生底图，包含国界/海岸轮廓和全球一级行政区边界线。原 web/assets/world.geo.json 保持原字节及研究国家示意锚点用途；派生底图只用于显示，不改变项目坐标、国家聚合坐标、容量或研究事实。

来源：Natural Earth 官方维护仓库 https://github.com/nvkelso/natural-earth-vector ，固定提交 ca96624a56bd078437bca8184e78163e5039ad19 的 geojson/ne_10m_admin_0_countries.geojson 和 geojson/ne_10m_admin_1_states_provinces_lines.geojson。官方介绍：https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-1-states-provinces/ 。许可：public domain，https://www.naturalearthdata.com/about/terms-of-use/ 。保留官方地理表达，不宣称行政界实时更新或测绘级精度。

复现：将两个固定版本原始 GeoJSON 下载到临时目录后运行 python3 scripts/build_world_detail.py <目录>。标准库 Ramer–Douglas–Peucker 容差0.01度，保留小岛闭环，坐标四位小数；跳过来源中无几何的记录，去除无关属性。产物 sources 保留原始文件 SHA256、名称和提交。并非卫星影像、道路或地块地图。

全世界首屏沿用轻量底图，不请求该资源；viewBox宽度 <=650（首次放大）时同源加载，<=500（第二次放大）时显示州/省界。失败保留底图和项目，按钮可重试；复位隐藏州/省界，已取回精细轮廓可继续复用。边界线用 non-scaling-stroke 保持屏幕线宽，原浅色/深色主题和项目点尺寸保持。
