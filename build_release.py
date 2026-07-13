from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
import importlib.util
from pathlib import Path


APP_NAME = "LoL BP Coach"
APP_EXE = f"{APP_NAME}.exe"
VERSION = "0.2.5"

ROOT = Path(__file__).resolve().parent
RELEASE_DIR = ROOT / "release"
DIST_DIR = RELEASE_DIR / APP_NAME
BUILD_DIR = ROOT / "build_release_temp"
STAGING_DIR = ROOT / "build_release_staging"
INSTALLER_DIR = RELEASE_DIR / "installer"

RUNTIME_DIRS = [
    "analysis",
    "ui_v2",
    "utils",
    "tools",
    "img",
    "overlay",
]

RUNTIME_FILES = [
    "champion_data.json",
    "ban_slots.json",
    "recommendation_engine.py",
    "recommendation_engine_v3.py",
    "role_filter.py",
    "meta_filter.py",
    "meta_provider.py",
    "counter_analyzer.py",
    "meta_analyzer.py",
    "lol_bp_screenshot.py",
]

DATA_DIRS = [
    "16.13",
    "cache",
    "cache_seed",
    "patch_notes",
    "zh_CN",
]

DATA_FILES = [
    "botlane_pair_data.json",
    "champion_archetypes.json",
    "champion_draft_profile.json",
    "champion_roles.json",
    "counter_data.json",
    "counter_data_v2.json",
    "jungle_support_data.json",
    "meta_data.json",
    "patch_version.json",
    "role_data.json",
    "synergy_data.json",
    "synergy_data_v2.json",
    "tactical_rules.json",
]

BLANK_JSON_FILES = {
    "live_state.json": {
        "timestamp": 0,
        "role": "",
        "target_role": "",
        "ally": [],
        "enemy": [],
        "bans": [],
        "recommendations": [],
        "lane_recommendations": [],
        "role_inference": {},
        "inferred_lane_opponent": "",
        "coach": {},
        "prepick": {},
        "session_control": {},
    },
    "live_draft.json": {
        "timestamp": 0,
        "role": "",
        "target_role": "",
        "ally": [],
        "enemy": [],
        "bans": [],
        "recommendations": [],
        "lane_recommendations": [],
        "coach": {},
        "prepick": {},
    },
    "match_sessions.json": [],
    "player_profile.json": {},
    "player_baseline.json": {},
    "draft_session_control.json": {
        "paused": False,
        "session_id": "",
        "paused_at": 0,
        "resumed_at": 0,
        "started_at": 0,
        "frozen_state": {},
    },
    "companion_settings.json": {
        "dock_mode": "LEFT",
        "opacity": 90,
        "collapsed": False,
        "auto_attach": True,
        "x": 0,
        "y": 0,
    },
}


def main() -> int:
    clean()
    prepare_staging()
    write_support_files()
    build_pyinstaller()
    write_release_docs()
    write_inno_setup()
    make_portable_zip()
    build_iexpress_installer()
    maybe_build_installer()
    print_release_summary()
    return 0


def clean():
    for path in (BUILD_DIR, STAGING_DIR, RELEASE_DIR):
        if path.exists():
            shutil.rmtree(path)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for spec in ROOT.glob("*.spec"):
        spec.unlink()


def prepare_staging():
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    data_stage = STAGING_DIR / "data"
    data_stage.mkdir(parents=True, exist_ok=True)

    for directory in DATA_DIRS:
        source = ROOT / "data" / directory
        target = data_stage / directory
        if source.exists():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)

    for file_name in DATA_FILES:
        source = ROOT / "data" / file_name
        if source.exists():
            shutil.copy2(source, data_stage / file_name)

    import json

    for file_name, payload in BLANK_JSON_FILES.items():
        (data_stage / file_name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    (STAGING_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (STAGING_DIR / "config").mkdir(parents=True, exist_ok=True)


def write_support_files():
    (ROOT / "requirements_release.txt").write_text(
        "\n".join(
            [
                "PySide6",
                "requests",
                "lxml",
                "numpy",
                "opencv-python",
                "mss",
                "pywin32",
                "Pillow",
                "pygetwindow",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def build_pyinstaller():
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--name",
        APP_NAME,
        "--distpath",
        str(RELEASE_DIR),
        "--workpath",
        str(BUILD_DIR),
    ]

    for directory in RUNTIME_DIRS:
        source = ROOT / directory
        if source.exists():
            command += ["--add-data", f"{source}{os.pathsep}{directory}"]

    for file_name in RUNTIME_FILES:
        source = ROOT / file_name
        if source.exists():
            command += ["--add-data", f"{source}{os.pathsep}."]

    command += [
        "--add-data",
        f"{STAGING_DIR / 'data'}{os.pathsep}data",
        "--add-data",
        f"{STAGING_DIR / 'logs'}{os.pathsep}logs",
        "--add-data",
        f"{STAGING_DIR / 'config'}{os.pathsep}config",
    ]

    hidden_imports = [
        "cv2",
        "numpy",
        "mss",
        "win32gui",
        "win32con",
        "win32process",
        "requests",
        "lxml",
        "lxml.etree",
        "lxml.html",
        "PIL",
        "lol_bp_screenshot",
        "recommendation_engine",
        "recommendation_engine_v3",
        "analysis.draft_session_control",
        "analysis.macro_plan_advisor",
        "analysis.lane_state_analyzer",
    ]
    if importlib.util.find_spec("pygetwindow") is not None:
        hidden_imports.append("pygetwindow")
    for item in hidden_imports:
        command += ["--hidden-import", item]

    command.append(str(ROOT / "desktop_app.py"))

    print("Building PyInstaller release...")
    subprocess.run(command, cwd=str(ROOT), check=True)
    generated_spec = ROOT / f"{APP_NAME}.spec"
    if generated_spec.exists():
        shutil.copy2(generated_spec, ROOT / "release.spec")


def write_release_docs():
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    (DIST_DIR / "VERSION.txt").write_text(f"{APP_NAME}\nVersion: {VERSION}\n", encoding="utf-8")
    (DIST_DIR / "README.txt").write_text(
        f"""LoL BP Coach {VERSION}

启动方式：
1. 双击 "{APP_EXE}"
2. 选择你的分路
3. 点击“启动识别”
4. 进入 LOL BP 界面后等待推荐刷新

已内置资源：
- 16.13 BP 数据
- 英雄头像 img/champion
- 中文英雄数据 data/zh_CN
- Lolalytics 缓存与 cache_seed
- 版本公告 patch_notes

说明：
- 首次启动会自动创建 data / logs / config。
- 识别失败不会闪退，错误会写入 logs/crash.log 或 logs/recognition.log。
- 定格按钮可锁定当前推荐，避免 BP 界面变化导致误识别覆盖。
""",
        encoding="utf-8-sig",
    )


def write_inno_setup():
    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    iss = INSTALLER_DIR / "LoL-BP-Coach.iss"
    iss.write_text(
        f"""#define MyAppName "{APP_NAME}"
#define MyAppVersion "{VERSION}"
#define MyAppExeName "{APP_EXE}"

[Setup]
AppId={{{{8C6EF1A7-B3B0-4F22-9D44-8E3A9D6F41C2}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
DefaultDirName={{localappdata}}\\{{#MyAppName}}
DefaultGroupName={{#MyAppName}}
OutputDir={INSTALLER_DIR}
OutputBaseFilename=LoL-BP-Coach-Inno-Setup-{VERSION}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Files]
Source: "{DIST_DIR}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: checkedonce

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "启动 {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
""",
        encoding="utf-8",
    )


def make_portable_zip():
    zip_path = RELEASE_DIR / f"LoL-BP-Coach-portable-{VERSION}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file_path in DIST_DIR.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(RELEASE_DIR))


def maybe_build_installer():
    iscc = find_iscc()
    if not iscc:
        print("Inno Setup ISCC.exe not found; installer config generated only.")
        return
    print("Building Inno Setup installer...")
    subprocess.run([str(iscc), str(INSTALLER_DIR / "LoL-BP-Coach.iss")], check=True)


def build_iexpress_installer():
    from shutil import which

    iexpress = which("iexpress.exe") or str(Path(os.environ.get("WINDIR", "C:/Windows")) / "System32" / "iexpress.exe")
    if not Path(iexpress).exists():
        print("IExpress not found; skipping lightweight setup exe.")
        return

    INSTALLER_DIR.mkdir(parents=True, exist_ok=True)
    portable_zip = RELEASE_DIR / f"LoL-BP-Coach-portable-{VERSION}.zip"
    install_script = INSTALLER_DIR / "install_release.ps1"
    setup_exe = INSTALLER_DIR / f"LoL-BP-Coach-Setup-{VERSION}.exe"
    sed_file = INSTALLER_DIR / "LoL-BP-Coach-IExpress.sed"

    install_script.write_text(
        rf"""$ErrorActionPreference = "Stop"
$zip = Join-Path $PSScriptRoot "LoL-BP-Coach-portable-{VERSION}.zip"

function Select-InstallTarget {{
  $defaultRoot = Join-Path $env:LOCALAPPDATA "Programs"
  $defaultTarget = Join-Path $defaultRoot "LoL BP Coach"
  try {{
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = "请选择 LoL BP Coach 的安装位置"
    $dialog.SelectedPath = $defaultRoot
    $dialog.ShowNewFolderButton = $true
    $result = $dialog.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK -or [string]::IsNullOrWhiteSpace($dialog.SelectedPath)) {{
      return $null
    }}
    $selected = $dialog.SelectedPath
  }} catch {{
    try {{
      $shellApp = New-Object -ComObject Shell.Application
      $folder = $shellApp.BrowseForFolder(0, "请选择 LoL BP Coach 的安装位置", 0, 0)
      if ($null -eq $folder) {{ return $null }}
      $selected = $folder.Self.Path
    }} catch {{
      $selected = $defaultRoot
    }}
  }}

  if ([string]::IsNullOrWhiteSpace($selected)) {{
    return $defaultTarget
  }}
  if ((Split-Path -Leaf $selected) -ieq "LoL BP Coach") {{
    return $selected
  }}
  return Join-Path $selected "LoL BP Coach"
}}

$target = Select-InstallTarget
if ([string]::IsNullOrWhiteSpace($target)) {{
  exit 0
}}
$tmp = Join-Path $env:TEMP "LoL-BP-Coach-Install"
if (Test-Path $tmp) {{ Remove-Item -LiteralPath $tmp -Recurse -Force }}
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
Expand-Archive -LiteralPath $zip -DestinationPath $tmp -Force
$source = Join-Path $tmp "LoL BP Coach"
if (-not (Test-Path $source)) {{ throw "安装包内容不完整：找不到 LoL BP Coach 文件夹" }}
New-Item -ItemType Directory -Force -Path $target | Out-Null
$exclude = @(
  "live_state.json",
  "live_draft.json",
  "match_sessions.json",
  "player_profile.json",
  "player_baseline.json",
  "draft_session_control.json",
  "companion_settings.json"
)
$copyArgs = @(
  "`"$source`"",
  "`"$target`"",
  "/E",
  "/R:2",
  "/W:1",
  "/XF"
) + $exclude
$robocopy = Start-Process -FilePath "robocopy.exe" -ArgumentList $copyArgs -Wait -PassThru -NoNewWindow
if ($robocopy.ExitCode -gt 7) {{ throw "复制文件失败，Robocopy ExitCode=$($robocopy.ExitCode)" }}
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "LoL BP Coach.lnk"
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $target "LoL BP Coach.exe"
$shortcut.WorkingDirectory = $target
$shortcut.IconLocation = $shortcut.TargetPath
$shortcut.Save()

$programs = [Environment]::GetFolderPath("Programs")
$group = Join-Path $programs "LoL BP Coach"
New-Item -ItemType Directory -Force -Path $group | Out-Null
$startShortcutPath = Join-Path $group "LoL BP Coach.lnk"
$startShortcut = $shell.CreateShortcut($startShortcutPath)
$startShortcut.TargetPath = Join-Path $target "LoL BP Coach.exe"
$startShortcut.WorkingDirectory = $target
$startShortcut.IconLocation = $startShortcut.TargetPath
$startShortcut.Save()

$readme = Join-Path $target "安装位置.txt"
"LoL BP Coach 已安装到：`r`n$target`r`n`r`n启动方式：`r`n1. 桌面快捷方式：LoL BP Coach`r`n2. 开始菜单：LoL BP Coach`r`n3. 直接运行：$($shortcut.TargetPath)" | Set-Content -LiteralPath $readme -Encoding UTF8

try {{
  $shell.Popup("LoL BP Coach 安装完成。`n安装位置：$target`n已创建桌面和开始菜单快捷方式。", 8, "LoL BP Coach", 64) | Out-Null
}} catch {{}}

Start-Process -FilePath "explorer.exe" -ArgumentList "`"$target`""
Start-Process -FilePath (Join-Path $target "LoL BP Coach.exe")
""",
        encoding="utf-8-sig",
    )

    shutil.copy2(portable_zip, INSTALLER_DIR / portable_zip.name)
    sed_file.write_text(
        f"""[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=LoL BP Coach installation finished.
TargetName={setup_exe}
FriendlyName=LoL BP Coach Installer
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File install_release.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles

[SourceFiles]
SourceFiles0={INSTALLER_DIR}

[SourceFiles0]
{portable_zip.name}=
install_release.ps1=
""",
        encoding="utf-8",
    )
    print("Building lightweight IExpress installer...")
    subprocess.run([str(iexpress), "/N", "/Q", str(sed_file)], check=True)


def find_iscc() -> Path | None:
    from shutil import which

    found = which("ISCC.exe") or which("iscc.exe")
    if found:
        return Path(found)
    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def print_release_summary():
    total_size = sum(path.stat().st_size for path in DIST_DIR.rglob("*") if path.is_file())
    print(f"Release folder: {DIST_DIR}")
    print(f"Portable zip: {RELEASE_DIR / f'LoL-BP-Coach-portable-{VERSION}.zip'}")
    print(f"Installer config: {INSTALLER_DIR / 'LoL-BP-Coach.iss'}")
    print(f"Total size: {total_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    raise SystemExit(main())
