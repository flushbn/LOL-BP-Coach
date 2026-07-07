# Coach Lane State V1

## 目标

教练系统第一步：分析 BP 阶段双方路线强弱，输出每条路线的线权、击杀潜力、防守价值和打野行动建议。

## 新增文件

- `analysis/lane_state_analyzer.py`
- `reports/coach_lane_state_v1.md`

## 修改文件

- `lol_bp_screenshot.py`
- `ui_v2/pages/coach_page.py`

## 输出结构

`live_state.json` 的 `coach` 字段新增：

```json
{
  "lane_state": {
    "lanes": [],
    "summary": [],
    "ally_roles": {},
    "enemy_roles": {}
  }
}
```

每条路线包含：

- 路线：上路 / 打野 / 中路 / 下路
- 对位：我方英雄 vs 敌方英雄
- 线权：大优 / 小优 / 均势 / 小劣 / 劣势
- 击杀潜力：高 / 中 / 低
- 防守价值：高 / 中 / 低
- 资源优先级：主攻路 / 防守路 / 保护路 / 放养路 / 机会路 / 发育路 / 控资源路
- 打野建议：主动抓 / 反蹲 / 控视野 / 换资源等

## 关键规则

不再把“对线优势”直接等同于“应该多抓”。

例如：

- 墨菲特对亚索：可能是小优，但单人坦克击杀潜力不高。
- 输出建议：不建议硬抓，优先反蹲、控视野，防止对方发育。

## 验证样例

输入：

- 己方：Malphite / LeeSin / Ahri / Jhin / Leona
- 敌方：Yasuo / JarvanIV / Zed / Kaisa / Nautilus

输出摘要：

- 中路、下路：适合作为主攻路
- 上路：有线权但不建议硬抓，更适合反蹲与视野保护

## 是否影响推荐排序

不影响。

本阶段只写入 `coach.lane_state` 并在战术页展示，不修改 `recommendation_engine_v3.py` 的排序公式。
