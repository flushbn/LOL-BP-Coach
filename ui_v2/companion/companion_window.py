# LoL BP Coach Companion Window
import sys as _sys, json, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in _sys.path: _sys.path.insert(0, str(ROOT))
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QScrollArea, QSlider, QVBoxLayout, QWidget)
from ui_v2.companion.client_tracker import detect_window
from ui_v2.companion.state_reader import read_state
from utils.champion_names import champion_display_name
from utils.window_capture_exclusion import exclude_window_from_capture
SETTINGS_PATH = ROOT / 'data' / 'companion_settings.json'
def _load_settings():
    try:
        if SETTINGS_PATH.exists(): return json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
    except: pass
    return {'dock_mode':'FREE','opacity':90,'collapsed':False,'auto_attach':True,'x':0,'y':0}
def _save_settings(s):
    try: SETTINGS_PATH.write_text(json.dumps(s,indent=2),encoding='utf-8')
    except: pass
class CompanionWindow(QWidget):
    W = 240
    H = 520
    COLLAPSED_W = 120
    COLLAPSED_H = 80
    def __init__(self):
        super().__init__()
        self.setWindowTitle('LoL BP Coach')
        # scrollable window
        self.resize(self.W, self.H)
        self.setMinimumSize(180, 200)
        flags = Qt.WindowStaysOnTopHint | Qt.Tool | Qt.FramelessWindowHint
        self.setWindowFlags(flags)
        self.setStyleSheet('QWidget{background:#1a1a2e;color:#e0e0e0;font-size:11px}')
        self._settings = _load_settings()
        self._dock_mode = self._settings.get('dock_mode','FREE')
        self._opacity = self._settings.get('opacity',90)
        self._collapsed = self._settings.get('collapsed',False)
        self._drag_pos = None
        self._all_champs = self._load_champs()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4,4,4,4)
        layout.setSpacing(4)
        self._build_title_bar(layout)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setStyleSheet('QScrollArea{border:none;background:transparent} QScrollBar:vertical{background:#16213e;width:8px;border-radius:4px} QScrollBar::handle:vertical{background:#0f3460;border-radius:4px;min-height:30px} QScrollBar::handle:vertical:hover{background:#e94560} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px}')
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0,0,0,0)
        self._content_layout.setSpacing(4)
        self._build_status(self._content_layout)
        self._build_recs(self._content_layout)
        self._build_lane(self._content_layout)
        self._build_coach(self._content_layout)
        self._build_prepick(self._content_layout)
        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll)
        self._build_opacity_control(layout)
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start(500)
        self._dock_timer = QTimer()
        self._dock_timer.timeout.connect(self._auto_dock)
        self._dock_timer.start(1000)
        self.setWindowOpacity(self._opacity/100)
        if self._collapsed: self._toggle_collapse()
        self._poll()
        self._auto_dock()
        QTimer.singleShot(300, self._enable_capture_exclusion)
    def _enable_capture_exclusion(self):
        exclude_window_from_capture(int(self.winId()))
    def _load_champs(self):
        try:
            p = ROOT / 'champion_data.json'
            return sorted(json.loads(p.read_text(encoding='utf-8')).keys())
        except: return []
    def _build_title_bar(self, layout):
        bar = QHBoxLayout()
        bar.setContentsMargins(0,0,0,0)
        t = QLabel('LoL BP Coach')
        t.setStyleSheet('color:#f5c518;font-weight:bold;font-size:12px')
        bar.addWidget(t)
        bar.addStretch()
        self._btn_collapse = QPushButton('[-]')
        self._btn_collapse.setFixedWidth(30)
        self._btn_collapse.clicked.connect(self._toggle_collapse)
        bar.addWidget(self._btn_collapse)
        bc = QPushButton('X')
        bc.setFixedWidth(24)
        bc.clicked.connect(self.close)
        bar.addWidget(bc)
        layout.addLayout(bar)
    def _build_status(self, layout):
        g = QGroupBox('Status')
        gl = QVBoxLayout(g); gl.setSpacing(1)
        self._conn_label = QLabel('Connecting...')
        gl.addWidget(self._conn_label)
        self._role_label = QLabel('')
        gl.addWidget(self._role_label)
        rl = QHBoxLayout(); rl.setSpacing(2)
        rl.addWidget(QLabel('Role:'))
        self._role_btns = {}
        for rid, rcn in [('TOP','Top'),('JUNGLE','Jng'),('MID','Mid'),('ADC','ADC'),('SUPPORT','Sup')]:
            b = QPushButton(rcn)
            b.setCheckable(True)
            b.setStyleSheet('QPushButton{background:#0f3460;color:#e0e0e0;padding:2px 6px;font-size:11px}QPushButton:checked{background:#e94560;color:white;font-weight:bold}')
            b.clicked.connect(lambda ch, r=rid: self._on_role_change(r))
            self._role_btns[rid] = b
            rl.addWidget(b)
        gl.addLayout(rl)
        self._time_label = QLabel('')
        gl.addWidget(self._time_label)
        layout.addWidget(g)
    def _build_recs(self, layout):
        g = QGroupBox('Picks'); gl = QVBoxLayout(g); gl.setSpacing(1)
        self._rec_label = QLabel('No data'); self._rec_label.setWordWrap(True)
        gl.addWidget(self._rec_label); layout.addWidget(g)
    def _build_lane(self, layout):
        g = QGroupBox('Lane'); gl = QVBoxLayout(g); gl.setSpacing(1)
        self._lane_label = QLabel('No data'); self._lane_label.setWordWrap(True)
        gl.addWidget(self._lane_label); layout.addWidget(g)
    def _build_coach(self, layout):
        g = QGroupBox('Analysis'); gl = QVBoxLayout(g); gl.setSpacing(1)
        self._coach_label = QLabel('No data'); self._coach_label.setWordWrap(True)
        gl.addWidget(self._coach_label)
        self._advice_label = QLabel(''); self._advice_label.setWordWrap(True)
        self._advice_label.setStyleSheet('color:#a0a0a0')
        gl.addWidget(self._advice_label); layout.addWidget(g)
    def _build_prepick(self, layout):
        g = QGroupBox('Prep'); gl = QVBoxLayout(g); gl.setSpacing(1)
        self._search = QLineEdit(); self._search.setPlaceholderText('Search...')
        self._search.textChanged.connect(self._on_search)
        gl.addWidget(self._search)
        self._pick_list = QListWidget(); self._pick_list.setMaximumHeight(60)
        self._pick_list.itemClicked.connect(self._on_pick)
        gl.addWidget(self._pick_list)
        self._pick_detail = QLabel(''); self._pick_detail.setWordWrap(True)
        self._pick_detail.setStyleSheet('color:#a0a0a0')
        gl.addWidget(self._pick_detail); layout.addWidget(g)
    def _build_opacity_control(self, layout):
        bar = QHBoxLayout(); bar.setContentsMargins(0,0,0,0)
        bar.addWidget(QLabel('Opacity:'))
        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(70,100)
        self._opacity_slider.setValue(self._opacity)
        self._opacity_slider.valueChanged.connect(self._set_opacity)
        bar.addWidget(self._opacity_slider)
        self._opacity_label = QLabel(f'{self._opacity}%')
        self._opacity_label.setFixedWidth(30)
        bar.addWidget(self._opacity_label); layout.addLayout(bar)
    def _set_opacity(self, v):
        self._opacity = v
        self._opacity_label.setText(f'{v}%')
        self.setWindowOpacity(v/100)
        self._settings['opacity'] = v; _save_settings(self._settings)
    def _toggle_collapse(self):
        self._collapsed = not self._collapsed
        self._scroll.setVisible(not self._collapsed)
        if self._collapsed:
            self.resize(self.COLLAPSED_W, self.COLLAPSED_H)
            self.setMinimumSize(120, 60)
            self._btn_collapse.setText('[+]')
        else:
            self.resize(self.W, self.H)
            self.setMinimumSize(180, 200)
            self._btn_collapse.setText('[-]')
        self._settings['collapsed'] = self._collapsed; _save_settings(self._settings)
    def _on_search(self, text):
        self._pick_list.clear()
        if not text.strip(): return
        t = text.strip().lower()
        for c in self._all_champs:
            display = champion_display_name(c)
            if t in c.lower() or t in display.lower():
                self._pick_list.addItem(display)
                if self._pick_list.count() >= 8: break
    def _on_pick(self, item):
        self._pick_detail.setText(item.text())
    def _poll(self):
        s = read_state()
        ts = s.get('timestamp',0)
        role = s.get('role','')
        c = ts > 0
        if c:
            from datetime import datetime
            t = datetime.fromtimestamp(ts).strftime('%H:%M:%S')
            self._conn_label.setText('Connected')
            self._role_label.setText(f'Role: {role}')
            self._time_label.setText(f'Updated: {t}')
        else:
            self._conn_label.setText('Disconnected')
            self._role_label.setText('')
            self._time_label.setText('Waiting...')
        self._update_recs(s); self._update_lane(s); self._update_coach(s)
        for rid, b in getattr(self,'_role_btns',{}).items():
            b.setChecked(rid == role)
    def _on_role_change(self, role):
        fp = ROOT / 'data' / 'live_draft.json'
        try:
            if fp.exists(): d = json.loads(fp.read_text(encoding='utf-8'))
            else: d = {}
            d['role'] = role; d['timestamp'] = int(time.time())
            fp.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
            sp = ROOT / 'data' / 'live_state.json'
            if sp.exists():
                try: s = json.loads(sp.read_text(encoding='utf-8'))
                except: s = {}
            else: s = {}
            s['role'] = role; s['target_role'] = role; s['timestamp'] = d['timestamp']
            sp.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
            self._poll()
        except Exception as e: print(f'COMPANION_ROLE_ERR: {e}')
    def _update_recs(self, s):
        recs = s.get('recommendations',[])
        if not recs: self._rec_label.setText('No data'); return
        lines = []
        for r in recs[:5]:
            n = champion_display_name(r.get('champion_cn') or r.get('champion','')); sc = r.get('final_score',r.get('score',''))
            lb = r.get('lane_bonus', 0)
            lr = r.get('lane_reason', '')
            rs = r.get('reasons',[])
            top_line = f'{n} {sc}'
            if lb != 0:
                top_line += f'  Lane{lb:+d}'
            rs_str = '; '.join(rs[:2]) if isinstance(rs,list) else ''
            display = top_line
            if rs_str:
                display += '<br>' + rs_str
            lines.append(display)
        self._rec_label.setText('<br>'.join(lines))
    def _update_lane(self, s):
        recs = s.get('lane_recommendations',[])
        lines = []
        inferred = s.get('inferred_lane_opponent','')
        if inferred:
            lines.append(f'对位: {champion_display_name(inferred)}')
        role_inf = s.get('role_inference',{})
        if role_inf:
            top_parts = []
            role_cn = {'TOP':'上','JUNGLE':'野','MID':'中','ADC':'射','SUPPORT':'辅'}
            for champ, probs in list(role_inf.items())[:3]:
                if isinstance(probs, dict) and probs:
                    role, prob = sorted(probs.items(), key=lambda x: x[1], reverse=True)[0]
                    top_parts.append(f'{champion_display_name(champ)} {role_cn.get(role, role)}{round(prob*100)}%')
            if top_parts:
                lines.append(' / '.join(top_parts))
        if not recs:
            self._lane_label.setText('<br>'.join(lines) if lines else 'No data')
            return
        for r in recs[:5]:
            n = champion_display_name(r.get('champion','')); sc = r.get('lane_score','')
            dl = r.get('delta','')
            lines.append(f'{n} score={sc}' + (f' delta={dl:+.1f}' if dl else ''))
        self._lane_label.setText('<br>'.join(lines))
    def _update_coach(self, s):
        c = s.get('coach',{})
        ally = c.get('ally',{}); enemy = c.get('enemy',{})
        dims = [('frontline','FL'),('engage','Eng'),('protect','Prot'),('burst','Burst'),('dps','DPS'),('late','Late')]
        lines = []
        if ally:
            pts = []
            for k,lb in dims:
                g = ally.get(k,'')
                if g: pts.append(f'{lb} {g}')
            if pts: lines.append('Ally: '+' | '.join(pts))
        if enemy:
            pts = []
            for k,lb in dims:
                g = enemy.get(k,'')
                if g: pts.append(f'{lb} {g}')
            if pts: lines.append('Enemy: '+' | '.join(pts))
        self._coach_label.setText('<br>'.join(lines) if lines else 'No analysis')
        if 'advice' in c and c['advice']:
            self._advice_label.setText(c['advice'][:150])
        else: self._advice_label.setText('')
    def _auto_dock(self):
        if self._dock_mode == 'FREE': return
        client = detect_window()
        if not client:
            if self.x() < 0 or self.y() < 0: self.move(0,100)
            return
        cx,cy,cw,ch = client['x'],client['y'],client['w'],client['h']
        cw2 = self.W if not self._collapsed else self.COLLAPSED_W
        if self._dock_mode == 'LEFT': nx,ny = cx-cw2-80,cy
        else: nx,ny = cx+cw+10,cy
        if self.x() != nx or self.y() != ny:
            self.move(nx,ny)
            self._settings['x']=nx; self._settings['y']=ny
            _save_settings(self._settings)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos = e.globalPosition().toPoint()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos:
            self.move(e.globalPosition().toPoint()-self._drag_pos)
    def mouseReleaseEvent(self, e):
        self._drag_pos = None; _save_settings(self._settings)
    def _save_pos(self):
        self._settings['x']=self.x(); self._settings['y']=self.y()
if __name__ == '__main__':
    app = QApplication(_sys.argv)
    app.setApplicationName('LoL BP Coach')
    w = CompanionWindow()
    w.show()
    _sys.exit(app.exec())

