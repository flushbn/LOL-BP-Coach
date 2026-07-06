# LOL BP Coach

LOL BP Coach 是一个面向《英雄联盟》BP 阶段的桌面辅助工具。它把版本数据、对线克制、阵容分析、玩家历史表现和版本更新解释整合到一个 PySide6 单窗口 UI 中，帮助玩家在选人阶段更快做出决策。

## 功能模块

- **综合推荐**：基于版本强度、角色适配、阵容需求、对位加成和玩家熟练度生成推荐。
- **对线推荐**：使用 Lolalytics 当前版本 matchup 数据展示对位优势英雄。
- **战术分析**：分析己方与敌方阵容的前排、开团、保护、爆发、持续输出和后期能力。
- **英雄详情**：搜索或点击英雄后查看版本数据、克制关系、协同关系、符文/出装思路和强势期。
- **玩家数据**：读取本地对局历史，统计胜率、英雄池、位置表现和个人风格。
- **数据更新中心**：在 UI 内更新当前 patch 的 Meta、Counter、Synergy 和 Lolalytics 缓存。
- **版本公告**：展示 patch notes，并解释英雄、装备、符文和系统改动对推荐的影响。

## 系统架构

```text
LOL-BP-Coach
├─ run_app.py                 # 统一启动入口
├─ core/                      # 推荐引擎核心
│  ├─ recommendation_engine_v3.py
│  ├─ recommendation_engine.py
│  ├─ counter_analyzer.py
│  ├─ meta_analyzer.py
│  └─ role_filter.py
├─ analysis/                  # 数据层与分析模块
│  ├─ lolalytics_client.py
│  ├─ lane_recommendation.py
│  ├─ role_inference_engine.py
│  ├─ player_analytics.py
│  └─ online_meta_sync.py
├─ ui_v2/                     # PySide6 单窗口 UI
│  ├─ main_window.py
│  ├─ pages/
│  ├─ widgets/
│  └─ components/
├─ data/
│  ├─ 16.13/                  # 当前版本 BP 数据
│  ├─ zh_CN/                  # Riot Data Dragon 中文英雄数据
│  └─ patch_notes/
├─ img/champion/              # 英雄头像
└─ utils/                     # 资源路径、英雄名、头像等工具
```

## 安装方法

建议使用 Python 3.10+。

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 运行方式

```bash
python run_app.py
```

首次启动会自动创建：

- `data/live_state.json`
- `data/live_draft.json`
- `data/match_sessions.json`
- `data/player_profile.json`
- `data/cache/`
- `logs/`
- `config/`

## 数据来源说明

- **Lolalytics**：用于当前 patch 的英雄胜率、登场率、禁用率、对位克制和对线推荐。
- **Riot Data Dragon**：用于英雄中文名称、英雄基础信息和头像索引。
- **本地推断数据**：协同数据当前基于英雄标签、阵容角色和 matchup pattern 推断，UI 会将其作为推断数据展示。

## 当前内置版本

- Patch：`16.13`
- 数据目录：`data/16.13/`
- 已内置：
  - `meta_data.json`
  - `counter_data.json`
  - `synergy_data.json`

## 安全与隐私

仓库不包含：

- API Key
- 本地绝对路径
- 个人日志
- 缓存目录
- 测试截图
- 打包产物

玩家对局历史只保存在本地 `data/match_sessions.json`，默认发布版本为空数组。

## 开发说明

本仓库是公开发布清理版，已移除旧 Overlay、临时脚本、debug 图片、缓存和打包产物。推荐系统核心位于 `core/`，UI 只读取 `data/live_state.json` 并渲染，不直接依赖截图识别流程。
