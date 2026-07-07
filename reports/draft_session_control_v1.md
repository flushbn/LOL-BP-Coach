# Draft Session Control V1

## 目标

在 BP 阵容基本完成后，允许用户定格当前推荐结果和战术分析，避免后续界面切换、动画、客户端变化导致识别结果错乱并覆盖正确建议。

## 新增能力

客户端顶部新增三个会话按钮：

- 定格：冻结当前 `live_state.json`，后续识别线程不会覆盖当前推荐和战术。
- 继续：恢复实时识别刷新。
- 新局：清空当前 BP 状态，开始下一局等待识别。

## 新增文件

- `analysis/draft_session_control.py`
- `reports/draft_session_control_v1.md`

## 修改文件

- `lol_bp_screenshot.py`
- `ui_v2/main_window.py`
- `ui_v2/state_reader.py`

## 数据文件

新增运行时控制文件：

```text
data/draft_session_control.json
```

核心字段：

```json
{
  "paused": true,
  "session_id": "1234567890",
  "paused_at": 1234567890,
  "frozen_state": {}
}
```

## 写入保护

所有识别写入最终通过：

```python
write_live_state(state)
```

当 `paused = true` 时：

- 普通识别写入会返回 `False`
- `live_state.json` 不会被覆盖
- UI 保持当前推荐、对线、战术、节奏计划不变

## 新局预留

`start_new_game()` 当前会：

- 清空 BP 阵容
- 清空推荐与战术
- 生成新的 `session_id`
- 保留上一局 frozen state 到 `previous_frozen_state`

后续可以在“我的数据”中接入：

- 本局使用英雄
- 位置
- 胜负
- 推荐是否被采纳
- 局后记录

## 验证

已验证：

- 定格后模拟后台写入不会覆盖当前阵容
- 继续后后台写入恢复
- 新局会清空阵容并进入等待识别状态

## 是否影响推荐排序

不影响。

本功能只控制 UI 数据流和识别写入，不修改推荐分数。
