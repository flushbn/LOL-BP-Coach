# Coach Macro Plan V1

## 目标

教练系统第二步：在“路线强弱分析”的基础上，生成前中期资源与节奏计划。

系统不只回答“哪路线优线劣”，还会进一步回答：

- 主节奏应该围绕哪半区？
- 前 5 分钟应该主动抓、反蹲还是控视野？
- 5-14 分钟应该优先小龙、先锋还是换资源？
- 哪条路线容易被针对？

## 新增文件

- `analysis/macro_plan_advisor.py`
- `reports/coach_macro_plan_v1.md`

## 修改文件

- `lol_bp_screenshot.py`
- `analysis/demo_state.py`
- `ui_v2/pages/coach_page.py`

## 新增数据结构

`live_state.json` 的 `coach` 字段新增：

```json
{
  "macro_plan": {
    "primary_side": "下半区",
    "primary_lane": "下路",
    "strong_lanes": ["中路", "下路"],
    "protect_lanes": ["上路"],
    "weak_lanes": [],
    "jungle_path": "建议刷野路线向下半区收束...",
    "first_5_min": [],
    "minute_5_14": [],
    "objectives": [],
    "risk_alerts": [],
    "summary": []
  }
}
```

## 关键规则

### 不把线优等同于强抓

如果某路对线优势但击杀潜力不足，例如坦克上路：

- 标记为防守路
- 建议反蹲、控视野、防止对方发育
- 不建议投入大量打野时间硬抓

### 主节奏选择

优先考虑：

1. 主攻路
2. 机会路
3. 击杀潜力
4. 路线权重：下路 / 中路 / 上路
5. 打野强弱

### 资源建议

- 下半区强：优先小龙视野和下河道
- 上半区强：优先先锋和塔皮
- 中路强：先控中路线权，再转双河道
- 后期劣势：15-25 分钟主动争夺资源，避免拖后期

## UI 展示

战术页新增：

- 节奏计划
- 路线强弱分析
- 战术建议

三个区域互相独立，可滚动，不再互相遮挡。

## 是否影响推荐排序

不影响。

本阶段只增强 Coach Panel，不修改 `recommendation_engine_v3.py` 的最终评分。
