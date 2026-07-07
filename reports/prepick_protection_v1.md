# Prepick Protection V1

## 问题

LOL 客户端中，玩家当前点中/预选的英雄会显示在己方选择栏里。

旧逻辑会把它当作已锁定英雄：

```python
excluded = ally_picks + enemy_picks + bans
```

结果是：

- 用户点击推荐英雄
- 截图识别把它识别成己方已选
- 推荐引擎排除该英雄
- 英雄从推荐列表消失

## 修复方案

新增 `split_preselected_ally()`：

- 根据当前目标分路判断己方识别英雄中最像“玩家当前预选”的英雄
- 将它从 `ally_picks` 中暂时剥离
- 写入 `prepick.detected`
- 推荐计算时不把它加入排除列表

## 示例

当前角色：TOP

识别到：

```json
["Malphite"]
```

输出：

```python
locked_ally = []
detected_preselect = "Malphite"
```

这样墨菲特不会因为“正在预选”而从推荐列表消失。

## 影响范围

修改文件：

- `lol_bp_screenshot.py`

新增报告：

- `reports/prepick_protection_v1.md`

## 是否影响推荐排序

不改变推荐公式。

只是修正输入状态，把“预选英雄”和“已锁定队友”区分开。

## 后续优化

后续可以继续增强：

- 通过截图识别“锁定按钮/确认状态”
- 让 UI 显示“当前预选保护中”
- 与“定格”功能联动：定格后将预选视为最终选择
