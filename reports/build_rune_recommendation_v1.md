# Champion Build & Rune Recommendation System V1

## 修改文件

- `analysis/lolalytics_client.py`
- `analysis/build_recommendation.py`
- `analysis/rune_recommendation.py`
- `analysis/hero_detail_context.py`
- `ui_v2/components/hero_detail_panel.py`

## 新增能力

- 从 Lolalytics build 页面解析符文和装备图片 `alt` 信息。
- 新增 patch-aware build cache：`data/cache/lolalytics/{patch}/builds/`。
- 英雄详情页展示：
  - 推荐符文
  - 三件核心装备
  - 出门装
  - 根据敌方 AD/AP/爆发结构的调整装备

## 评分逻辑

`BuildScore = winrate * 0.5 + pickrate * 0.2 + sample_score * 0.2 + situational_bonus * 0.1`

其中小样本装备会降权，避免只因为极高胜率但样本很少而被误选。

## 敌方阵容适配

- 敌方 AD 英雄较多：优先护甲、防暴击、生存装备。
- 敌方 AP 英雄较多：优先魔抗装备。
- 敌方爆发英雄较多：优先容错和保命装备。

## 验证方式

```powershell
cd "H:\lol-bp-mss\test"
python analysis/test_build_rune_recommendation.py
```

## 已验证样例

- `Malphite TOP`
  - 符文：`Resolve / Grasp of the Undying`
  - 核心装备：`Plated Steelcaps → Sunfire Aegis → Frozen Heart`
  - 敌方 AD 偏多时：推荐 `Thornmail / Frozen Heart / Randuin's Omen`
- `LeeSin JUNGLE`
  - 能输出当前版本常用符文
  - 能输出爆发/半肉相关核心装备和防爆发调整项

## 兼容性

- 不修改推荐排序。
- 不修改 Counter / Synergy / Meta / DraftBonus。
- Lolalytics 网络失败时使用本地英雄标签兜底，详情页不会空白或闪退。
