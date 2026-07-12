# Installer Path Selection V1

## 问题

朋友反馈：安装程序双击后显示安装完成，但找不到安装后的文件。

## 原因

当前 IExpress 轻量安装器默认安装到：

```text
%LOCALAPPDATA%\LoL BP Coach
```

该路径不直观，且安装完成提示没有明确展示安装目录。

另外，PowerShell 5 对 UTF-8 无 BOM 脚本可能按系统编码解析，中文提示有概率导致安装脚本解析异常，但 IExpress 仍显示完成。

## 修复

修改 `build_release.py`：

1. 安装时弹出目录选择窗口。
2. 如果用户选择普通文件夹，会自动安装到该目录下的 `LoL BP Coach` 子目录。
3. 如果用户直接选择名为 `LoL BP Coach` 的目录，则直接使用该目录。
4. 安装完成后：
   - 创建桌面快捷方式
   - 创建开始菜单快捷方式
   - 写入 `安装位置.txt`
   - 打开安装目录
   - 启动客户端
5. 安装脚本改为 UTF-8 BOM，兼容 Windows PowerShell 5。

## 新安装包

```text
release/installer/LoL-BP-Coach-Setup-0.2.1.exe
```

## 验证

- 已重新生成 IExpress 安装器。
- `install_release.ps1` 已确认 UTF-8 BOM：`EF BB BF`
- PowerShell 脚本语法检查通过。

## 是否影响客户端功能

不影响。

本次仅修改安装器生成逻辑，不修改推荐、识别、UI、数据层。
