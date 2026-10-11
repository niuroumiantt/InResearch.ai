# 可运行的包模板

在 inresearch 仓库根目录运行：

```sh
python3 docs/guides/fetchdata/examples/make_sample.py /tmp/fetchdata-example-1
python3 scripts/validate_collector_handoff.py /tmp/fetchdata-example-1/fetchstat
python3 scripts/validate_collector_handoff.py /tmp/fetchdata-example-1/fetchfilings
python3 scripts/validate_collector_handoff.py /tmp/fetchdata-example-1/fetchreports
python3 scripts/validate_collector_handoff.py /tmp/fetchdata-example-1/fetchquotes
```

只需 Python 3.11+ 标准库，无网络。重复运行请换新目录，生成器拒绝覆盖旧包。四包所有数字、对象和 URL 都是**合成示例，不能采用或上传为真实资料**；全零提交 SHA 只作模板，真实交付换成实际提交。

以生成的 manifest / observations / run-report 为模板：员工更换原件及全部来源字段，按共同规范填写时间/单位/范围，并重新生成 SHA256SUMS。`object.match_status=unresolved`、未知时间及 `target_ids=[]` 均能通过本地检查，不要求先解决全部信息或关联研究需求。

离线验包结果明确 `formal_adoption=false`。失败结果会区分包级错误与逐条候选错误；工具不会修改文件，也不会把合成样例变为真实证据。
