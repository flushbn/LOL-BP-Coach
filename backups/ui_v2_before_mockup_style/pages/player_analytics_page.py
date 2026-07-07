import sys, json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QGroupBox, QGridLayout, QScrollArea,
)
BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))
from analysis.player_analytics import get_analytics
from utils.champion_names import champion_display_name


class 玩家数据Page(QWidget):
    def __init__(self):
        super().__init__()
        self._analytics = get_analytics()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.addWidget(QLabel('<h2 style=color:#f5c518;>我的数据</h2>'))
        self._refresh_btn = QPushButton('刷新数据')
        self._refresh_btn.clicked.connect(self._refresh_data)
        layout.addWidget(self._refresh_btn)
        self._setup_widgets(layout)
        layout.addStretch()
        scroll.setWidget(inner)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        self._refresh_data()

    def _setup_widgets(self, layout):
        # Overall
        box1 = QGroupBox('总体数据')
        g1 = QGridLayout()
        self._lbl_games = QLabel('--')
        self._lbl_wr = QLabel('--')
        self._lbl_r30 = QLabel('--')
        self._lbl_r7 = QLabel('--')
        self._lbl_games.setStyleSheet('font-size:20px;font-weight:bold;color:#fff;')
        self._lbl_wr.setStyleSheet('font-size:20px;font-weight:bold;color:#4caf50;')
        g1.addWidget(QLabel('总场次'),0,0); g1.addWidget(self._lbl_games,0,1)
        g1.addWidget(QLabel('总胜率'),0,2); g1.addWidget(self._lbl_wr,0,3)
        g1.addWidget(QLabel('最近30场'),1,0); g1.addWidget(self._lbl_r30,1,1)
        g1.addWidget(QLabel('最近7天'),1,2); g1.addWidget(self._lbl_r7,1,3)
        box1.setLayout(g1)
        layout.addWidget(box1)

        # Hero Pool


        # Hero Pool
        box2 = QGroupBox('英雄分析')
        v2 = QVBoxLayout()
        v2.addWidget(QLabel('<b style=color:#4caf50;>核心英雄</b>'))
        self._core_table = self._make_table(['英雄','场次','胜率','标签'])
        v2.addWidget(self._core_table)
        v2.addWidget(QLabel('<b style=color:#e94560;>谨慎选择</b>'))
        self._caution_table = self._make_table(['英雄','场次','胜率','标签'])
        v2.addWidget(self._caution_table)
        box2.setLayout(v2)
        layout.addWidget(box2)

        # Position
        box3 = QGroupBox('位置分析')
        v3 = QVBoxLayout()
        self._pos_best = QLabel('最佳位置: --')
        self._pos_best.setStyleSheet('font-size:16px;color:#4caf50;')
        self._pos_worst = QLabel('待提升: --')
        self._pos_worst.setStyleSheet('font-size:16px;color:#e94560;')
        v3.addWidget(self._pos_best)
        v3.addWidget(self._pos_worst)
        self._pos_table = self._make_table(['位置','场次','胜率'])
        v3.addWidget(self._pos_table)
        box3.setLayout(v3)
        layout.addWidget(box3)

        # Style
        box4 = QGroupBox('风格分析')
        v4 = QVBoxLayout()
        self._style_desc = QLabel('--')
        self._style_desc.setStyleSheet('font-size:16px;color:#f5c518;')
        v4.addWidget(self._style_desc)
        self._arch_table = self._make_table(['风格','场次'])
        v4.addWidget(self._arch_table)
        box4.setLayout(v4)
        layout.addWidget(box4)

        # Trend
        box5 = QGroupBox('状态趋势')
        v5 = QVBoxLayout()
        self._trend_label = QLabel('--')
        self._trend_label.setStyleSheet('font-size:18px;font-weight:bold;color:#f5c518;')
        v5.addWidget(self._trend_label)
        self._trend_table = self._make_table(['区间','场次','胜率'])
        v5.addWidget(self._trend_table)
        box5.setLayout(v5)
        layout.addWidget(box5)

    def _make_table(self, headers):
        t = QTableWidget()
        t.setColumnCount(len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        return t

    def _refresh_data(self):
        a = self._analytics
        a.refresh()
        s = a.get_overall_stats()
        self._lbl_games.setText(str(s['games']))
        wr = s['winrate']
        self._lbl_wr.setText('{:.1f}%'.format(wr))
        self._lbl_r30.setText('{:.1f}%'.format(s['recent30_wr']))
        self._lbl_r7.setText('{:.1f}%'.format(s['recent7d_wr']))

        insights = a.get_hero_insights()
        self._fill_table(self._core_table, insights['core'])
        self._fill_table(self._caution_table, insights['caution'])

        pos = a.get_position_analysis()
        if pos['best']['pos']:
            self._pos_best.setText('最佳位置: {} ({:.1f}%)'.format(pos['best']['pos'], pos['best']['wr']))
        else:
            self._pos_best.setText('最佳位置: 暂无数据')
        if pos['worst']['pos']:
            self._pos_worst.setText('待提升: {} ({:.1f}%)'.format(pos['worst']['pos'], pos['worst']['wr']))
        else:
            self._pos_worst.setText('待提升: 暂无数据')
        pos_list = [{'pos': p, **d} for p, d in pos['positions'].items()]
        self._fill_table(self._pos_table, pos_list)

        sty = a.get_style()
        self._style_desc.setText('你的游戏风格: {}'.format(sty['style_description']))
        self._fill_table(self._arch_table, sty['archetypes'])

        trend = a.get_trend()
        self._trend_label.setText('当前状态: {}'.format(trend['trend']))
        trend_rows = []
        for k in ['last30', 'last20', 'last10']:
            if k in trend:
                seg_name = k.replace('last', '最近') + '场'
                trend_rows.append({'segment': seg_name, **trend[k]})
        self._fill_table(self._trend_table, trend_rows)

    def _fill_table(self, table, data):
        table.setRowCount(len(data))
        for i, item in enumerate(data):
            if table in (self._core_table, self._caution_table):
                values = [
                    champion_display_name(item.get('champion', '')),
                    item.get('games', ''),
                    '{:.1f}%'.format(item.get('winrate', 0)),
                    item.get('label', ''),
                ]
            elif table is self._pos_table:
                values = [
                    item.get('pos', ''),
                    item.get('games', ''),
                    '{:.1f}%'.format(item.get('winrate', 0)),
                ]
            elif table is self._arch_table:
                values = [item.get('name', ''), item.get('count', '')]
            elif table is self._trend_table:
                values = [
                    item.get('segment', ''),
                    item.get('games', ''),
                    '{:.1f}%'.format(item.get('winrate', 0)),
                ]
            else:
                values = list(item.values())
            for j, v in enumerate(values[:table.columnCount()]):
                cell = QTableWidgetItem(str(v))
                cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
                table.setItem(i, j, cell)
        table.resizeColumnsToContents()

