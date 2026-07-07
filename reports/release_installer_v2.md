# Release Installer V2

## 目标

让用户像正常软件一样使用：

```text
下载 → 解压或安装 → 双击启动 → 选择分路 → 启动识别
```

用户不需要安装：

- Python
- pip
- Visual Studio Build Tools
- 项目源码

## 发布产物

构建脚本：

- `build_release.py`

构建后输出：

- `release/LoL BP Coach/LoL BP Coach.exe`
- `release/LoL-BP-Coach-portable-0.2.0.zip`
- `release/installer/LoL-BP-Coach-Setup-0.2.0.exe`
- `release/installer/LoL-BP-Coach.iss`
- 如果本机安装 Inno Setup，则额外输出 `LoL-BP-Coach-Setup-0.2.0.exe`

## 已整合资源

发布包包含：

- `data/16.13/`
- `data/zh_CN/`
- `data/patch_notes/`
- `data/cache/`
- `data/cache_seed/`
- `img/champion/`
- `champion_data.json`
- `ban_slots.json`
- `analysis/`
- `ui_v2/`
- `utils/`
- `tools/`

## 已清理的个人运行数据

发布包会生成空白运行状态，不携带个人测试记录：

- `live_state.json`
- `live_draft.json`
- `match_sessions.json`
- `player_profile.json`
- `player_baseline.json`
- `draft_session_control.json`

## 识别进程兼容

源码运行：

```text
python lol_bp_screenshot.py --recommend TOP
```

冻结版运行：

```text
LoL BP Coach.exe --recognize TOP
```

客户端会根据是否为 PyInstaller 冻结环境自动选择启动方式。

## 安装位置

Inno Setup 默认安装到：

```text
%LOCALAPPDATA%/LoL BP Coach
```

原因：

- 普通 Windows 用户可写
- `data/cache/`
- `logs/`
- `config/`
- Lolalytics 缓存

都不需要管理员权限。

## 注意

如果本机未安装 Inno Setup，构建脚本仍会生成：

- 便携版 zip
- Windows IExpress 轻量安装器 exe
- `.iss` 安装器配置

安装 Inno Setup 后重新运行：

```text
python build_release.py
```

即可生成安装器 exe。

## 本次构建验证

- PyInstaller onedir：成功
- 便携版 zip：成功
- IExpress 安装器：成功
- Inno Setup：本机未安装，仅生成 `.iss`
- 英雄头像：173 个
- 缓存文件：4196 个
- 16.13 核心数据文件：3 个
- 发布目录大小：约 264 MB
