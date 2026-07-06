from __future__ import annotations

from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from utils.champion_names import champion_display_name


ROLE_LABELS = {
    "TOP": "上路",
    "JUNGLE": "打野",
    "MID": "中路",
    "MIDDLE": "中路",
    "ADC": "射手",
    "BOTTOM": "射手",
    "SUPPORT": "辅助",
    "UTILITY": "辅助",
}


class LanePage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("对线推荐")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        self.enemy = QLabel("可能对位英雄：暂无")
        self.enemy.setObjectName("MutedText")
        layout.addWidget(self.enemy)

        self.inference = QLabel("敌方位置推断：暂无数据")
        self.inference.setObjectName("CoachGrades")
        self.inference.setWordWrap(True)
        layout.addWidget(self.inference)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["英雄", "分数", "Delta", "场次"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

    def render(self, state: dict):
        recs = state.get("lane_recommendations", [])[:10]
        inferred_opponent = state.get("inferred_lane_opponent", "")
        enemy = inferred_opponent
        for rec in recs:
            enemy = rec.get("opponent", "") or enemy
        self.enemy.setText(f"可能对位英雄：{champion_display_name(enemy) or '暂无'}")
        self.inference.setText(self._format_inference(state.get("role_inference", {})))

        self.table.setRowCount(len(recs))
        for row, rec in enumerate(recs):
            values = [
                champion_display_name(rec.get("champion", "")),
                rec.get("lane_score", ""),
                rec.get("delta", ""),
                rec.get("games", ""),
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def _format_inference(self, inference: dict) -> str:
        if not inference:
            return "敌方位置推断：暂无数据"

        blocks = ["敌方位置推断"]
        for champion, probabilities in inference.items():
            if not isinstance(probabilities, dict):
                continue
            sorted_roles = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)
            if not sorted_roles:
                continue
            lines = [f"{champion_display_name(champion)}："]
            for index, (role, probability) in enumerate(sorted_roles[:3]):
                mark = "✔" if index == 0 else "⚠" if index == 1 else " "
                role_label = ROLE_LABELS.get(role, role)
                lines.append(f"{mark} {role_label} {round(float(probability) * 100)}%")
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

