# 待人工解压的加密压缩包清单

`needs_password_YYYYMMDD.csv` 由本地会话每轮扫描后刷新（`pipeline/needs_password.py`）。

- 列：path / size_bytes / project / guess_content / module / why
- `guess_content` 与 `module` 是**据包名推测**的，未解压核实，仅供批量处理时排优先级；
- 用户按清单解压后**文件原地留下即可**，本地会话下一轮扫描自动发现并入队，无需通知；
- 已解压的包会从下一版清单中自动消失。
