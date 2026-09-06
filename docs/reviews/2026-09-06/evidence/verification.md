# 隔离验证摘录

基线 af50de9；以下运行均未改实际业务数据。

### validate.log

```text
记录数: projects=120 companies=248 prices=207 policies=2 contracts=2 sources=74 products=175 bom_parts=46 product_docs_plan=801 product_library=0
校验通过（0 warnings）

```

### intake_selftest.log

```text
✓ 冲突升 A 档：「数据中心单方造价」= 900.0元/㎡，而库内「数据中心单方造价」已有 4406.0元/㎡（招标控制价/施工总包/CN，2022-01）——**差 4.9 倍**
✓ 干净的 6 分件落 B 档
✓ 默认扫描排除模板与夹具（本次扫到 0 个真投递）
自检通过

```

### models.log

```text
  · server_v2_console.glb → rack3d，自动适配尺寸（1.2MB，CC Attribution（作者：FlevasGR））

通过：1 条登记，0 个提醒。
下一步：python3 -m http.server 8000 然后开 http://localhost:8000/rack3d.html 看效果

```

### export_full.log

```text
导出 0 章 ｜ 0 条 Finding（0 条带警示）｜ 0 个来源
→ reports/output/2026-09-06_全球数据中心研究报告.md

```

### export_M10.log

```text
导出 0 章 ｜ 0 条 Finding（0 条带警示）｜ 0 个来源
→ reports/output/2026-09-06_专题报告：建设运营与人才.md

```
