from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from analysis.data_patch_manager import DataPatchManager
from analysis.data_update_service import DataUpdateService, LOG_PATH


class UpdateWorker(QObject):
    progress = Signal(int, str)
    done = Signal(dict)

    def __init__(self, action: str, patch: str | None = None):
        super().__init__()
        self.action = action
        self.patch = patch

    def run(self):
        service = DataUpdateService()
        try:
            if self.action == "all":
                result = service.update_all_data(progress=self.progress.emit, online=True)
            elif self.action == "lolalytics":
                self.progress.emit(5, "开始更新全英雄 Lolalytics 数据")
                result = {"ok": True, **service.update_full_lolalytics_data(self.patch, progress=self.progress.emit)}
                self.progress.emit(100, "全英雄 Lolalytics 数据已完成")
            elif self.action == "cache":
                self.progress.emit(30, "重建缓存目录")
                removed = service.rebuild_cache(self.patch)
                result = {"ok": True, "removed_cache": removed}
                self.progress.emit(100, "缓存已重建")
            else:
                result = {"ok": False, "error": f"Unknown action: {self.action}"}
        except Exception as exc:
            result = {"ok": False, "error": str(exc)}
            self.progress.emit(100, f"失败: {exc}")
        self.done.emit(result)


class PatchStatusWorker(QObject):
    done = Signal(dict)

    def run(self):
        try:
            self.done.emit(DataPatchManager().get_status())
        except Exception as exc:
            self.done.emit({
                "current_patch": "unknown",
                "latest_patch": "unknown",
                "outdated": False,
                "error": str(exc),
                "local_patches": [],
            })


class UpdatePage(QWidget):
    status_changed = Signal()
    patch_status_ready = Signal(dict)

    def __init__(self):
        super().__init__()
        self.manager = DataPatchManager()
        self.thread: QThread | None = None
        self.worker: UpdateWorker | None = None
        self.status_thread: QThread | None = None
        self.status_worker: PatchStatusWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("数据更新中心")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.current_label = QLabel("当前版本: 检查中")
        self.latest_label = QLabel("最新版本: 检查中")
        self.status_label = QLabel("状态: 检查中")
        self.status_label.setObjectName("CoachGrades")
        layout.addWidget(self.current_label)
        layout.addWidget(self.latest_label)
        layout.addWidget(self.status_label)

        patch_row = QHBoxLayout()
        patch_row.addWidget(QLabel("切换 Patch"))
        self.patch_combo = QComboBox()
        patch_row.addWidget(self.patch_combo, 1)
        self.switch_button = QPushButton("切换")
        self.switch_button.clicked.connect(self.switch_patch)
        patch_row.addWidget(self.switch_button)
        layout.addLayout(patch_row)

        buttons = QHBoxLayout()
        self.update_button = QPushButton("一键更新")
        self.update_button.clicked.connect(lambda: self.run_action("all"))
        self.lolalytics_button = QPushButton("更新全英雄在线数据（含装备）")
        self.lolalytics_button.clicked.connect(lambda: self.run_action("lolalytics"))
        self.cache_button = QPushButton("重建缓存")
        self.cache_button.clicked.connect(lambda: self.run_action("cache"))
        self.log_button = QPushButton("查看更新日志")
        self.log_button.clicked.connect(self.load_log)
        for button in (self.update_button, self.lolalytics_button, self.cache_button, self.log_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        layout.addWidget(self.progress)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("更新日志与状态会显示在这里")
        layout.addWidget(self.output, 1)

        QTimer.singleShot(0, self.refresh_status)

    def render(self, state: dict):
        return

    def refresh_status(self):
        if self.status_thread and self.status_thread.isRunning():
            return
        self.status_thread = QThread(self)
        self.status_worker = PatchStatusWorker()
        self.status_worker.moveToThread(self.status_thread)
        self.status_thread.started.connect(self.status_worker.run)
        self.status_worker.done.connect(self._apply_status)
        self.status_worker.done.connect(self.patch_status_ready)
        self.status_worker.done.connect(self.status_thread.quit)
        self.status_worker.done.connect(self.status_worker.deleteLater)
        self.status_thread.finished.connect(self.status_thread.deleteLater)
        self.status_thread.finished.connect(self._clear_status_worker)
        self.status_thread.start()

    def _clear_status_worker(self):
        self.status_thread = None
        self.status_worker = None

    def _apply_status(self, status: dict):
        current = status.get("current_patch", "unknown")
        latest = status.get("latest_patch", "unknown")
        outdated = status.get("outdated", False)
        self.current_label.setText(f"当前版本: {current}")
        self.latest_label.setText(f"最新版本: {latest}")
        if status.get("error"):
            self.status_label.setText(f"状态: 在线检查失败，使用本地数据 ({status['error']})")
        elif outdated:
            self.status_label.setText("状态: 已过期，建议更新")
        else:
            self.status_label.setText("状态: 已是最新")

        self.patch_combo.clear()
        patches = status.get("local_patches", [])
        if current not in patches and current != "unknown":
            patches.append(current)
        self.patch_combo.addItems(sorted(set(patches)))
        index = self.patch_combo.findText(current)
        if index >= 0:
            self.patch_combo.setCurrentIndex(index)

    def run_action(self, action: str):
        if self.thread and self.thread.isRunning():
            return
        self.set_buttons_enabled(False)
        self.progress.setValue(0)
        self.output.append(f"开始任务: {action}")
        patch = self.patch_combo.currentText() or None
        self.thread = QThread(self)
        self.worker = UpdateWorker(action, patch)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def on_progress(self, value: int, message: str):
        self.progress.setValue(value)
        self.output.append(message)

    def on_done(self, result: dict):
        if result.get("ok"):
            self.output.append("任务完成")
        else:
            self.output.append(f"任务失败: {result.get('error', 'unknown')}")
        self.set_buttons_enabled(True)
        self.refresh_status()
        self.status_changed.emit()

    def switch_patch(self):
        patch = self.patch_combo.currentText()
        if not patch:
            return
        try:
            self.manager.switch_patch(patch)
            self.output.append(f"已切换到 patch {patch}")
            self.refresh_status()
            self.status_changed.emit()
        except Exception as exc:
            self.output.append(f"切换失败: {exc}")

    def load_log(self):
        path = Path(LOG_PATH)
        if path.exists():
            self.output.setPlainText(path.read_text(encoding="utf-8")[-8000:])
        else:
            self.output.setPlainText("暂无更新日志")

    def set_buttons_enabled(self, enabled: bool):
        for button in (self.update_button, self.lolalytics_button, self.cache_button, self.switch_button):
            button.setEnabled(enabled)
