# -*- coding: utf-8 -*-
import ctypes
import os
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import mss
import numpy as np
import win32con
import win32gui
import win32process
import json
import sys
from typing import List, Dict, Tuple, Optional



cv2.setUseOptimized(True)


# =========================
# 基础配置
# =========================

INTERVAL_SECONDS = 0.5

# DragonTail 官方英雄小图标目录。
# 注意：不要用 E:\dragontail-16.11.1\img\head，那个目录是皮肤头像裁图，
# 和 LOL 客户端 BP 小头像不是同一套图，容易把黛安娜识别成菲奥娜。

# PyInstaller support
BASE = Path(sys._MEIPASS) if getattr(sys,"frozen",False) else Path(__file__).parent
TEMPLATE_DIR = BASE / "img" / "champion"
TEMPLATE_EXTENSIONS = (".png", ".jpg", ".jpeg")

LOL_WINDOW_KEYWORDS = ("League of Legends", "英雄联盟")
LOL_PROCESS_NAMES = {
    "LeagueClientUx.exe",
    "LeagueClient.exe",
    "League of Legends.exe",
}

# 默认不抢焦点。运行前请让 LOL 客户端处于可见状态，不要最小化。
FOCUS_LOL_WINDOW = False

# 你的截图基准尺寸。下面所有槽位坐标都按这个尺寸估算。
# 如果客户端窗口大小变化，脚本会按比例缩放坐标。
BASE_CLIENT_WIDTH = 1524
BASE_CLIENT_HEIGHT = 857

# 识别阈值。选人/禁用头像是圆形裁剪，分数通常不会特别高。
MATCH_THRESHOLD = 0.55
BAN_MATCH_THRESHOLD = 0.40

# 过滤空槽位、纯色块、文字块。
MIN_SLOT_STDDEV = 16.0

# 每个槽位裁剪后再向内缩一点，减少圆形边框、锁定框、红圈边框干扰。
SLOT_INNER_MARGIN = 7

# 反向 matchTemplate 缩放比例：
# 官方 champion icon 是 128x128，客户端圆形头像大约是 60x60 内核。
HERO_IMAGE_SCALES = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.80, 0.90, 1.00, 1.20)

# 槽位图像变化小于这个值时，复用上次识别结果。
SLOT_CHANGE_THRESHOLD = 3.0

SAVE_DEBUG_IMAGES = True

CLIENT_DEBUG_IMAGE = str(BASE / "client_debug.png")

BP_DEBUG_IMAGE = str(BASE / "bp_slots_debug.png")
WINDOW_NAME = "LOL BP Slots Recognition"

CALIBRATION_FILE = str(BASE / "ban_slots.json")

# Chinese hero names from DragonTail zh_CN data
ZH_CN_CHAMPION_DATA = BASE / "data" / "zh_CN" / "champion.json"



# =========================
# BP 槽位配置
# =========================
#
# 重点：这些是“已选择/已禁用”的槽位，不是中间可选英雄网格。
#
# 按你发的 1524x857 界面估算：
# - 己方已选：左侧 5 个圆形头像
# - 敌方已选：右侧 5 个圆形头像，排位中对方显示后会出现在这里
# - 禁用英雄：不同模式/阶段 UI 会略有不同，先留配置入口
#
# 如果 debug 图里的框偏了，就改这里。

ALLY_PICK_SLOTS = [
    ("ally_pick_1", 64, 126, 74, 74),
    ("ally_pick_2", 64, 223, 74, 74),
    ("ally_pick_3", 64, 320, 74, 74),
    ("ally_pick_4", 64, 417, 74, 74),
    ("ally_pick_5", 64, 514, 74, 74),
]

ENEMY_PICK_SLOTS = [
    ("enemy_pick_1", 1430, 126, 74, 74),
    ("enemy_pick_2", 1430, 223, 74, 74),
    ("enemy_pick_3", 1430, 320, 74, 74),
    ("enemy_pick_4", 1430, 417, 74, 74),
    ("enemy_pick_5", 1430, 514, 74, 74),
]

# 如果你进入排位 Ban 阶段后看到禁用头像，把对应坐标填到这里即可。
# 格式: ("名字", x, y, width, height)
ALLY_BAN_SLOTS: List[Tuple[str, int, int, int, int]] = []
ENEMY_BAN_SLOTS: List[Tuple[str, int, int, int, int]] = []


@dataclass(frozen=True)
class WindowRect:
    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class HeroSource:
    name: str
    image_bgr: np.ndarray


@dataclass(frozen=True)
class HeroTemplate:
    name: str
    image_bgr: np.ndarray


@dataclass(frozen=True)
class SlotDefinition:
    group: str
    slot_id: str
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SlotResult:
    group: str
    slot_id: str
    name: Optional[str]
    score: float
    x: int
    y: int
    width: int
    height: int


@dataclass
class CachedSlot:
    crop_bgr: np.ndarray
    name: Optional[str]
    score: float



def load_ban_slots() -> Tuple[List[Tuple], List[Tuple]]:
    """Load ban slot coordinates from calibration file."""
    config_path = Path(CALIBRATION_FILE)
    if not config_path.exists():
        return [], []

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    ally_bans = []
    enemy_bans = []

    for entry in data.get("ally_bans", []):
        ally_bans.append((entry["name"], entry["x"], entry["y"], entry["w"], entry["h"]))

    for entry in data.get("enemy_bans", []):
        enemy_bans.append((entry["name"], entry["x"], entry["y"], entry["w"], entry["h"]))

    return ally_bans, enemy_bans


def save_ban_slots(ally_bans: list, enemy_bans: list) -> None:
    """Save ban slot coordinates to calibration file."""
    data = {
        "ally_bans": [
            {"name": f"ally_ban_{i+1}", "x": x, "y": y, "w": w, "h": h}
            for i, (_, x, y, w, h) in enumerate(ally_bans)
        ],
        "enemy_bans": [
            {"name": f"enemy_ban_{i+1}", "x": x, "y": y, "w": w, "h": h}
            for i, (_, x, y, w, h) in enumerate(enemy_bans)
        ],
    }
    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def calibrate_ban_slots() -> None:
    """Interactive calibration mode to mark ban slot positions."""
    print("=== 禁位校准模式 ===")
    print("请确保 LOL 客户端已进入 Ban 选阶段（能看到禁位头像）。")
    print("按顺序点击每个禁位头像的中心位置。")
    print("  - 先点己方禁位（通常5个），再点敌方禁位（通常5个）")
    print("  - 按 D 删除上一个点，按 S 保存，按 Q 取消")
    print()

    hwnd = find_lol_window()
    if hwnd is None:
        print("未找到 LOL 客户端窗口！")
        return

    restore_lol_window(hwnd)

    # Brief pause - let user put terminal behind the client
    print("\n3s until screenshot - put LoL client in front!")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    window_rect = get_window_client_rect(hwnd)

    with mss.MSS() as sct:
        client_image = capture_client_image(sct, window_rect)
    if client_image is None:
        print("截图失败！")
        return

    scale_x = BASE_CLIENT_WIDTH / client_image.shape[1]
    scale_y = BASE_CLIENT_HEIGHT / client_image.shape[0]

    clicks = []

    def mouse_callback(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            clicks.append((x, y))
            img = client_image.copy()
            n = len(clicks)
            for i, (cx, cy) in enumerate(clicks):
                is_ally = i < n // 2 or n <= 5
                color = (0, 255, 0) if is_ally else (0, 165, 255)
                cv2.circle(img, (cx, cy), 36, color, 2)
                cv2.circle(img, (cx, cy), 4, color, -1)
                label_y = cy + 16 if is_ally else cy - 80
                cv2.putText(img, str(i+1), (cx + 10, label_y),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            cv2.imshow(WINDOW_NAME, img)

    cv2.namedWindow(WINDOW_NAME)
    cv2.setMouseCallback(WINDOW_NAME, mouse_callback)

    display_init = client_image.copy()
    cv2.putText(display_init, "Click each ban icon center -> S:save D:undo Q:quit",
                (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)
    cv2.imshow(WINDOW_NAME, display_init)

    while True:
        key = cv2.waitKey(0) & 0xFF
        if key == ord("q"):
            print("取消校准")
            clicks.clear()
            break
        elif key == ord("s"):
            if len(clicks) == 0:
                print("请至少点击一个禁位位置！")
                continue
            break
        elif key == ord("d"):
            if clicks:
                clicks.pop()
                img = client_image.copy()
                n = len(clicks)
                for i, (cx, cy) in enumerate(clicks):
                    is_ally = i < n // 2 or n <= 5
                    color = (0, 255, 0) if is_ally else (0, 165, 255)
                    cv2.circle(img, (cx, cy), 36, color, 2)
                    cv2.circle(img, (cx, cy), 4, color, -1)
                    label_y = cy + 16 if is_ally else cy - 80
                    cv2.putText(img, str(i+1), (cx + 10, label_y),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                cv2.imshow(WINDOW_NAME, img)
                print(f"删除最后一个点，剩余 {len(clicks)} 个")

    cv2.destroyAllWindows()

    if not clicks:
        return

    n = len(clicks)
    ally_count = min(n, 5)  # first 5 = ally, rest = enemy

    slot_size = 74
    ally_bans = []
    for i in range(ally_count):
        cx, cy = clicks[i]
        bx = round(cx * scale_x - slot_size / 2)
        by = round(cy * scale_y - slot_size / 2)
        ally_bans.append((f"ally_ban_{i+1}", bx, by, slot_size, slot_size))

    enemy_bans = []
    for i in range(ally_count, n):
        cx, cy = clicks[i]
        bx = round(cx * scale_x - slot_size / 2)
        by = round(cy * scale_y - slot_size / 2)
        enemy_bans.append((f"enemy_ban_{i+1}", bx, by, slot_size, slot_size))

    save_ban_slots(ally_bans, enemy_bans)
    print(f"\n已保存 {len(ally_bans)} 个己方禁位 + {len(enemy_bans)} 个敌方禁位到 {CALIBRATION_FILE}")
    ban_preview = client_image.copy()
    for (_, x, y, w, h) in ally_bans:
        sx, sy = round(x / scale_x), round(y / scale_y)
        sw, sh = round(w / scale_x), round(h / scale_y)
        cv2.rectangle(ban_preview, (sx, sy), (sx+sw, sy+sh), (0, 255, 0), 2)
    for (_, x, y, w, h) in enemy_bans:
        sx, sy = round(x / scale_x), round(y / scale_y)
        sw, sh = round(w / scale_x), round(h / scale_y)
        cv2.rectangle(ban_preview, (sx, sy), (sx+sw, sy+sh), (0, 165, 255), 2)
    cv2.imwrite(BP_DEBUG_IMAGE, ban_preview)
    print(f"预览已保存到 {BP_DEBUG_IMAGE}")


def get_process_path(pid: int) -> str:
    """通过 PID 获取进程路径，避免 pywin32 OpenProcess 权限问题。"""
    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return ""

    try:
        buffer_size = 1024
        buffer = ctypes.create_unicode_buffer(buffer_size)
        size = ctypes.c_ulong(buffer_size)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        return buffer.value if ok else ""
    finally:
        kernel32.CloseHandle(handle)


def get_window_process_name(hwnd: int) -> str:
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception:
        return ""

    return os.path.basename(get_process_path(pid))


def find_lol_window() -> Optional[int]:
    """只按 LOL 客户端进程找窗口，避免把浏览器页面误当成客户端。"""
    candidates: List[Tuple[int, int, str, str]] = []

    def callback(hwnd: int, _extra: object) -> None:
        if not win32gui.IsWindowVisible(hwnd):
            return

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return

        process_name = get_window_process_name(hwnd)
        if process_name not in LOL_PROCESS_NAMES:
            return

        if not any(keyword.lower() in title.lower() for keyword in LOL_WINDOW_KEYWORDS):
            return

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        area = max(0, right - left) * max(0, bottom - top)
        candidates.append((area, hwnd, title, process_name))

    win32gui.EnumWindows(callback, None)

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def get_window_client_rect(hwnd: int) -> WindowRect:
    client_left, client_top, client_right, client_bottom = win32gui.GetClientRect(hwnd)
    screen_left, screen_top = win32gui.ClientToScreen(hwnd, (client_left, client_top))
    screen_right, screen_bottom = win32gui.ClientToScreen(hwnd, (client_right, client_bottom))

    return WindowRect(
        left=screen_left,
        top=screen_top,
        width=screen_right - screen_left,
        height=screen_bottom - screen_top,
    )


def restore_lol_window(hwnd: int) -> None:
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.3)


def focus_lol_window(hwnd: int) -> None:
    try:
        restore_lol_window(hwnd)
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.2)
    except Exception as exc:
        print(f"无法自动切到 LOL 窗口，请手动把 LOL 放到最前: {exc}")


def capture_client_image(sct, window_rect: WindowRect) -> Optional[np.ndarray]:
    if window_rect.width <= 0 or window_rect.height <= 0:
        return None

    monitor = {
        "left": window_rect.left,
        "top": window_rect.top,
        "width": window_rect.width,
        "height": window_rect.height,
    }
    screenshot = sct.grab(monitor)
    image_bgra = np.array(screenshot)
    return cv2.cvtColor(image_bgra, cv2.COLOR_BGRA2BGR)



def load_chinese_name_map() -> Dict[str, str]:
    """Load English-to-Chinese hero name mapping from DragonTail."""
    if not ZH_CN_CHAMPION_DATA.exists():
        print(f"Warning: Chinese name data not found: {ZH_CN_CHAMPION_DATA}")
        return {}
    with open(ZH_CN_CHAMPION_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)
    name_map: Dict[str, str] = {}
    for key, info in data.get("data", {}).items():
        name_map[key] = info.get("name", key)
    print(f"Loaded {len(name_map)} Chinese hero names")
    return name_map
def load_hero_templates(template_dir: Path, name_map: Optional[Dict[str, str]] = None) -> List[HeroTemplate]:
    if not template_dir.exists():
        raise FileNotFoundError(f"英雄头像目录不存在: {template_dir}")

    templates: List[HeroTemplate] = []
    for image_path in sorted(template_dir.iterdir()):
        if not image_path.is_file() or image_path.suffix.lower() not in TEMPLATE_EXTENSIONS:
            continue

        hero_name = image_path.stem
        if hero_name.endswith("_0"):
            hero_name = hero_name[:-2]

        file_bytes = np.fromfile(str(image_path), dtype=np.uint8)
        image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if image is None:
            print(f"跳过无法读取的模板: {image_path}")
            continue

        for scale in HERO_IMAGE_SCALES:
            resized_width = int(image.shape[1] * scale)
            resized_height = int(image.shape[0] * scale)
            if resized_width < 20 or resized_height < 20:
                continue

            resized = cv2.resize(
                image,
                (resized_width, resized_height),
                interpolation=cv2.INTER_AREA,
            )
            templates.append(HeroTemplate(name=hero_name, image_bgr=resized))

    if not templates:
        raise RuntimeError(f"没有加载到任何英雄头像: {template_dir}")

    return templates


def build_slot_definitions() -> List[SlotDefinition]:
    slots: List[SlotDefinition] = []
    groups = [
        ("ally_picks", ALLY_PICK_SLOTS),
        ("enemy_picks", ENEMY_PICK_SLOTS),
    ]

    for group, raw_slots in groups:
        for slot_id, x, y, width, height in raw_slots:
            slots.append(SlotDefinition(group, slot_id, x, y, width, height))

    ally_bans, enemy_bans = load_ban_slots()
    if not ally_bans and not enemy_bans:
        ally_bans, enemy_bans = ALLY_BAN_SLOTS, ENEMY_BAN_SLOTS

    for slot_id, x, y, width, height in ally_bans:
        slots.append(SlotDefinition("ally_bans", slot_id, x, y, width, height))

    for slot_id, x, y, width, height in enemy_bans:
        slots.append(SlotDefinition("enemy_bans", slot_id, x, y, width, height))

    return slots


def scale_slot(slot: SlotDefinition, client_image: np.ndarray) -> SlotDefinition:
    scale_x = client_image.shape[1] / BASE_CLIENT_WIDTH
    scale_y = client_image.shape[0] / BASE_CLIENT_HEIGHT

    return SlotDefinition(
        group=slot.group,
        slot_id=slot.slot_id,
        x=round(slot.x * scale_x),
        y=round(slot.y * scale_y),
        width=round(slot.width * scale_x),
        height=round(slot.height * scale_y),
    )


def crop_slot(client_image: np.ndarray, slot: SlotDefinition) -> Optional[np.ndarray]:
    if slot.x < 0 or slot.y < 0:
        return None
    if slot.x + slot.width > client_image.shape[1] or slot.y + slot.height > client_image.shape[0]:
        return None

    crop = client_image[slot.y : slot.y + slot.height, slot.x : slot.x + slot.width]
    margin = SLOT_INNER_MARGIN
    if crop.shape[0] <= margin * 2 or crop.shape[1] <= margin * 2:
        return crop

    return crop[margin:-margin, margin:-margin]


def slot_has_enough_texture(slot_bgr: np.ndarray) -> bool:
    gray = cv2.cvtColor(slot_bgr, cv2.COLOR_BGR2GRAY)
    return float(gray.std()) >= MIN_SLOT_STDDEV


def best_match_slot(slot_bgr: np.ndarray, templates: List[HeroTemplate]) -> Tuple[Optional[str], float]:
    if not slot_has_enough_texture(slot_bgr):
        return None, 0.0

    best_name: Optional[str] = None
    best_score = -1.0

    for template in templates:
        if template.image_bgr.shape[1] < slot_bgr.shape[1] or template.image_bgr.shape[0] < slot_bgr.shape[0]:
            continue

        result = cv2.matchTemplate(template.image_bgr, slot_bgr, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(result)

        if score > best_score:
            best_score = float(score)
            best_name = template.name

    if best_score < MATCH_THRESHOLD:
        return None, best_score

    return best_name, best_score


def best_match_ban_slot(slot_bgr: np.ndarray, templates: List[HeroTemplate]) -> Tuple[Optional[str], float]:
    """Match tiny ban icons by resizing each template to the crop size."""
    if not slot_has_enough_texture(slot_bgr):
        return None, 0.0

    best_name: Optional[str] = None
    best_score = -1.0
    target_size = (slot_bgr.shape[1], slot_bgr.shape[0])

    for template in templates:
        resized = cv2.resize(template.image_bgr, target_size, interpolation=cv2.INTER_AREA)
        result = cv2.matchTemplate(resized, slot_bgr, cv2.TM_CCOEFF_NORMED)
        _, score, _, _ = cv2.minMaxLoc(result)

        if score > best_score:
            best_score = float(score)
            best_name = template.name

    if best_score < BAN_MATCH_THRESHOLD:
        return None, best_score

    return best_name, best_score


def can_reuse_cached_slot(crop: np.ndarray, cached: Optional[CachedSlot]) -> bool:
    """槽位画面几乎没变化时，直接复用上次识别结果。"""
    if cached is None:
        return False
    if cached.crop_bgr.shape != crop.shape:
        return False

    diff = cv2.absdiff(crop, cached.crop_bgr)
    return float(diff.mean()) < SLOT_CHANGE_THRESHOLD


def recognize_bp_slots(
    client_image: np.ndarray,
    templates: List[HeroTemplate],
    slot_cache: Dict[str, CachedSlot],
) -> Tuple[List[SlotResult], int]:
    results: List[SlotResult] = []
    recognized_count = 0

    for base_slot in build_slot_definitions():
        slot = scale_slot(base_slot, client_image)
        crop = crop_slot(client_image, slot)
        if crop is None:
            continue

        cached = slot_cache.get(slot.slot_id)
        if can_reuse_cached_slot(crop, cached):
            name = cached.name
            score = cached.score
        else:
            if "ban" in slot.group:
                name, score = best_match_ban_slot(crop, templates)
            else:
                name, score = best_match_slot(crop, templates)
            slot_cache[slot.slot_id] = CachedSlot(crop_bgr=crop.copy(), name=name, score=score)
            recognized_count += 1

        results.append(
            SlotResult(
                group=slot.group,
                slot_id=slot.slot_id,
                name=name,
                score=score,
                x=slot.x,
                y=slot.y,
                width=slot.width,
                height=slot.height,
            )
        )

    return results, recognized_count


def summarize_results(results: List[SlotResult]) -> Dict[str, List[str]]:
    summary = {
        "ally_picks": [],
        "enemy_picks": [],
        "ally_bans": [],
        "enemy_bans": [],
    }

    for result in results:
        if result.name is not None:
            summary[result.group].append(result.name)

    return summary


def draw_results(client_image: np.ndarray, results: List[SlotResult]) -> np.ndarray:
    preview = client_image.copy()

    for result in results:
        if "ban" in result.group:
            base_color = (0, 165, 255)  # orange for bans
        else:
            base_color = (0, 255, 0)    # green for picks

        color = base_color if result.name else (0, 0, 255)
        cv2.rectangle(
            preview,
            (result.x, result.y),
            (result.x + result.width, result.y + result.height),
            color,
            2,
        )

        label = f"{result.slot_id}:{result.name or 'Unknown'} {result.score:.2f}"
        cv2.putText(
            preview,
            label,
            (result.x, max(16, result.y - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            color,
            1,
            cv2.LINE_AA,
        )

    return preview


def print_summary(summary: Dict[str, List[str]]) -> None:
    print(f"[己方已选] {summary['ally_picks']}")
    print(f"[敌方已选] {summary['enemy_picks']}")
    if summary['ally_bans']:
        print(f"[己方禁用] {summary['ally_bans']}")
    if summary['enemy_bans']:
        print(f"[敌方禁用] {summary['enemy_bans']}")




def main_loop_with_analysis(analyzer) -> None:
    """Run the normal recognition loop with team analysis."""
    from recommendation_engine import print_analysis

    name_map = load_chinese_name_map()
    templates = load_hero_templates(TEMPLATE_DIR, name_map)
    hero_count = len({template.name for template in templates})
    print(f"英雄: {hero_count}，模板: {len(templates)}")
    print("按 Q 或 ESC 退出")

    latest_preview = None
    next_capture_at = 0.0
    last_summary = None
    slot_cache = {}
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    with mss.MSS() as sct:
        while True:
            now = time.monotonic()
            if now >= next_capture_at:
                hwnd = find_lol_window()
                if hwnd is None:
                    print("未找到 LOL 客户端窗口")
                    latest_preview = None
                else:
                    restore_lol_window(hwnd)
                    if FOCUS_LOL_WINDOW:
                        focus_lol_window(hwnd)
                    window_rect = get_window_client_rect(hwnd)
                    client_image = capture_client_image(sct, window_rect)
                    if client_image is None:
                        latest_preview = None
                    else:
                        start_time = time.perf_counter()
                        results, recognized_count = recognize_bp_slots(client_image, templates, slot_cache)
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        summary = summarize_results(results)
                        summary_changed = summary != last_summary
                        if summary_changed:
                            print_summary(summary)
                            print(f"识别耗时: {elapsed_ms:.0f} ms")
                            # Team analysis
                            print_analysis(summary, analyzer)
                                                        # V10: Write live state for unified UI
                            try:
                                import json
                                from pathlib import Path
                                from analysis.draft_session_control import write_live_state
                                ls={"ally":summary.get("ally_picks",[]),"enemy":summary.get("enemy_picks",[]),"bans":summary.get("ally_bans",[])+summary.get("enemy_bans",[]),"recommendations":[],"timestamp":int(time.time()),"target_role":""}
                                recs=[]
                                write_live_state(ls)
                            except: pass
                            last_summary = summary
                        latest_preview = draw_results(client_image, results)
                        if SAVE_DEBUG_IMAGES and summary_changed:
                            cv2.imwrite(CLIENT_DEBUG_IMAGE, client_image)
                            cv2.imwrite(BP_DEBUG_IMAGE, latest_preview)
                next_capture_at = now + INTERVAL_SECONDS
            if latest_preview is not None:
                cv2.imshow(WINDOW_NAME, latest_preview)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
    cv2.destroyAllWindows()


def recommend_loop(target_role):
    from recommendation_engine_v3 import RecommendationEngine

    hide_capture_window = os.environ.get("LOL_HIDE_CAPTURE", "").lower() in ("1", "true", "yes")
    name_map = load_chinese_name_map()
    templates = load_hero_templates(TEMPLATE_DIR, name_map)
    engine = RecommendationEngine()
    role_inference_engine = None
    lane_recommender = None
    bilateral_analyzer = None
    coach_advisor = None
    lane_state_analyzer = None
    macro_plan_advisor = None

    def read_selected_role():
        try:
            live_path = Path(__file__).parent / "data" / "live_draft.json"
            if live_path.exists():
                data = json.loads(live_path.read_text(encoding="utf-8"))
                role = data.get("role", "")
                if role:
                    return role
        except Exception:
            pass
        return target_role

    def write_recognition_snapshot(summary, effective_role, phase="recognizing", message="识别中"):
        try:
            from analysis.draft_session_control import is_paused, write_live_state
            if is_paused():
                return
            state_path = Path(__file__).parent / "data" / "live_state.json"
            draft_path = Path(__file__).parent / "data" / "live_draft.json"
            existing = {}
            if state_path.exists():
                try:
                    existing = json.loads(state_path.read_text(encoding="utf-8"))
                except Exception:
                    existing = {}
            ally = summary.get("ally_picks", [])
            enemy = summary.get("enemy_picks", [])
            bans = summary.get("ally_bans", []) + summary.get("enemy_bans", [])
            existing.update({
                "ally": ally,
                "enemy": enemy,
                "bans": bans,
                "timestamp": int(time.time()),
                "role": effective_role or "",
                "target_role": effective_role or "",
                "recognition": {
                    "phase": phase,
                    "message": message,
                    "ally_count": len(ally),
                    "enemy_count": len(enemy),
                    "ban_count": len(bans),
                    "last_scan_at": int(time.time()),
                    "recommendation_status": "calculating" if phase == "recognized" else phase,
                },
            })
            write_live_state(existing)
        except Exception as exc:
            print(f"SNAPSHOT_WRITE_ERR: {exc}")

    # Overlay window
    try:
        overlay = None
        if not os.environ.get("LOL_NO_OVERLAY"):
            from overlay.overlay_window import OverlayWindow
            overlay = OverlayWindow()
        overlay.set_status("Waiting for picks...")
    except Exception:
        overlay = None

    print(f"Recommendation mode active ? role: {target_role or 'All Roles'}")
    latest_preview = None
    next_capture_at = 0.0
    last_summary = None
    slot_cache = {}
    if not hide_capture_window:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    with mss.MSS() as sct:
        while True:
            now = time.monotonic()
            if now >= next_capture_at:
                hwnd = find_lol_window()
                if hwnd is None:
                    print("No LOL window found!")
                    latest_preview = None
                else:
                    restore_lol_window(hwnd)
                    window_rect = get_window_client_rect(hwnd)
                    client_image = capture_client_image(sct, window_rect)
                    if client_image is None:
                        latest_preview = None
                    else:
                        results, _ = recognize_bp_slots(client_image, templates, slot_cache)
                        summary = summarize_results(results)
                        summary_changed = summary != last_summary
                        if summary_changed:
                            effective_role = read_selected_role()
                            print_summary(summary)
                            ally = summary.get("ally_picks", [])
                            enemy = summary.get("enemy_picks", [])
                            ally_bans_list = summary.get("ally_bans", [])
                            enemy_bans_list = summary.get("enemy_bans", [])
                            write_recognition_snapshot(
                                summary,
                                effective_role,
                                phase="recognized",
                                message="已识别 BP，正在计算推荐",
                            )
                            recs = []
                            all_recs = []
                            reverse_map = {v:k for k,v in name_map.items()}
                            all_bans = [reverse_map.get(x, x) for x in set(ally_bans_list + enemy_bans_list)]
                            if ally or enemy or effective_role:
                                from recommendation_engine import TeamAnalyzer
                                _team_ana = TeamAnalyzer()
                                game_state = _team_ana.describe_game_state(ally_picks=ally, enemy_picks=enemy)
                                eng = game_state['enemy_summary']
                                ally_s = game_state['ally_summary']
                                print(f"{eng}. {ally_s}")
                                deficits = _team_ana._detect_missing(ally)
                                if deficits:
                                    print("Deficits:", deficits)
                                sug = game_state.get('suggestion', '')
                                if sug:
                                    print(sug)
                                all_excluded = list(set(ally + all_bans + enemy))
                                all_recs = engine.recommend(ally_picks=ally, enemy_picks=enemy, bans=all_excluded, target_role=effective_role, top_n=15)
                                recs = list(all_recs[:10])
                                if recs:
                                    # Add mechanic bonus champs that arent already in top 5
                                    existing = set(r["champion"] for r in recs)
                                    for r in all_recs:
                                        if r.get("mechanic_bonus", 0) >= 3 and r["champion"] not in existing:
                                            r_copy = dict(r)
                                            r_copy["final_score"] = r["final_score"]
                                            r_copy["is_mechanic_pick"] = True
                                            recs.append(r_copy)
                                            existing.add(r["champion"])
                                        if len(recs) >= 7:
                                            break
                                    print(f"  {'#':3s} {'Champion':14s} {'Role':12s} {'Counter':>7s} {'TeamC':>5s} {'Viable':>6s} {'Final':>5s}")
                                    print(f"  {'-' * 58}")
                                    for i, r in enumerate(recs, 1):
                                        bd = r["breakdown"]
                                        print(f"  {i:<3d} {r.get('champion_cn', r['champion']):<14s} {str(r['role']):12s} {bd['counter']:>7d} {bd['team_comp']:>5d} {bd.get('viability', bd['meta']):>6d} {r['final_score']:>5d}")
                                    if overlay:
                                        try:
                                            if not overlay.root.winfo_exists():
                                                break
                                        except:
                                            break
                                        overlay.set_target_role(effective_role)
                                        overlay.set_ally_enemy(ally, enemy)
                                        overlay.update_team_comp(game_state)
                                        overlay.update(recs)
                                        if not overlay.root.winfo_exists():
                                            break
                                        # V7: Lane Picks
                                        try:
                                            from analysis.lane_recommendation import LanePickRecommender
                                            lpr = LanePickRecommender()
                                            lane_recs = lpr.get_lane_picks(ally, enemy, effective_role)
                                            if lane_recs: print("Lane opponent:", lane_recs[0].get("opponent","?"))
                                            overlay.set_lane_picks(lane_recs)
                                        except: pass
                                        # V7: Comfort Picks
                                        try:
                                            from analysis.comfort_pick_recommender import ComfortPickRecommender
                                            cpr = ComfortPickRecommender()
                                            comfort_recs = cpr.filter(all_recs if 'all_recs' in dir() else recs)
                                            overlay.set_comfort_picks(comfort_recs)
                                        except Exception as e:
                                            print("COMFORT_ERR:", e)
                            # V10: Write live state for unified UI
                            try:
                                import json
                                from pathlib import Path
                                from analysis.draft_session_control import is_paused, write_live_state

                                if is_paused():
                                    last_summary = summary
                                    next_capture_at = now + INTERVAL_SECONDS
                                    continue

                                # --- Role Inference + Lane Recommendations ---
                                lane_recs_list = []
                                role_inference_data = {}
                                inferred_lane_opponent = None
                                if summary.get("enemy_picks"):
                                    try:
                                        from analysis.role_inference_engine import RoleInferenceEngine
                                        if role_inference_engine is None:
                                            role_inference_engine = RoleInferenceEngine()
                                        _rie = role_inference_engine
                                        role_inference_data = _rie.infer_roles(summary.get("enemy_picks", []))
                                        if effective_role:
                                            _inferred_lane = _rie.infer_enemy_lane(summary.get("enemy_picks", []), effective_role)
                                            inferred_lane_opponent = _inferred_lane.get("champion") if _inferred_lane else None
                                    except Exception as _e:
                                        print(f"ROLE_INFERENCE_ERR: {_e}")

                                if effective_role and summary.get("enemy_picks"):
                                    try:
                                        from analysis.lane_recommendation import LaneRecommendation
                                        if lane_recommender is None:
                                            lane_recommender = LaneRecommendation()
                                        _lr = lane_recommender
                                        _lane_bundle = _lr.get_recommendations_for_draft(
                                            role=effective_role,
                                            enemy_picks=summary.get("enemy_picks", []),
                                            top_n=5,
                                        )
                                        lane_recs_list = _lane_bundle.get("recommendations", [])
                                        if _lane_bundle.get("role_inference"):
                                            role_inference_data = _lane_bundle.get("role_inference", role_inference_data)
                                        inferred_lane_opponent = _lane_bundle.get("opponent") or inferred_lane_opponent
                                    except Exception as _e:
                                        print(f"LANE_REC_ERR: {_e}")

                                # --- Coach / Team Grade / Lane State ---
                                coach_data = {}
                                try:
                                    from analysis.team_analyzer import BilateralTeamAnalyzer
                                    from analysis.coach_advisor import CoachAdvisor
                                    from analysis.lane_state_analyzer import LaneStateAnalyzer
                                    from analysis.macro_plan_advisor import MacroPlanAdvisor
                                    if bilateral_analyzer is None:
                                        bilateral_analyzer = BilateralTeamAnalyzer()
                                    if coach_advisor is None:
                                        coach_advisor = CoachAdvisor()
                                    if lane_state_analyzer is None:
                                        lane_state_analyzer = LaneStateAnalyzer()
                                    if macro_plan_advisor is None:
                                        macro_plan_advisor = MacroPlanAdvisor()
                                    _ba = bilateral_analyzer
                                    _bilateral = _ba.analyze(
                                        ally_picks=summary.get("ally_picks", []),
                                        enemy_picks=summary.get("enemy_picks", [])
                                    )
                                    _lane_state = lane_state_analyzer.analyze(
                                        ally_picks=summary.get("ally_picks", []),
                                        enemy_picks=summary.get("enemy_picks", []),
                                        role_inference=role_inference_data,
                                    )
                                    _macro_plan = macro_plan_advisor.build_plan(_lane_state, _bilateral)
                                    _ca = coach_advisor
                                    _ally_grades_obj = {}
                                    for _k in ["frontline","engage","peel","burst","dps","lategame"]:
                                        _g = _bilateral.get("ally_scores", {}).get(_k, 0)
                                        _ally_grades_obj[_k] = {"score": _g}
                                    _combined = _ca.combined_advise(_ally_grades_obj, _bilateral)
                                    _dim_map = {"frontline":"frontline","engage":"engage","peel":"protect","burst":"burst","dps":"dps","lategame":"late"}
                                    ally_out = {}
                                    enemy_out = {}
                                    for _k, _lk in _dim_map.items():
                                        ally_out[_lk] = _bilateral.get("ally", {}).get(_k, "")
                                        enemy_out[_lk] = _bilateral.get("enemy", {}).get(_k, "")
                                    comparison_out = _bilateral.get("comparison", {})
                                    coach_data = {
                                        "ally": ally_out,
                                        "enemy": enemy_out,
                                        "comparison": comparison_out,
                                        "advice": "\n".join(_combined.get("advice", [])[:5]),
                                        "lane_state": _lane_state,
                                        "macro_plan": _macro_plan,
                                    }
                                except Exception as _e:
                                    print(f"COACH_ERR: {_e}")
                                ls = {
                                    "ally": summary.get("ally_picks", []),
                                    "enemy": summary.get("enemy_picks", []),
                                    "bans": summary.get("ally_bans", []) + summary.get("enemy_bans", []),
                                    "recommendations": [],
                                    "lane_recommendations": lane_recs_list,
                                    "role_inference": role_inference_data,
                                    "inferred_lane_opponent": inferred_lane_opponent or "",
                                    "coach": coach_data,
                                    "prepick": {},
                                    "timestamp": int(time.time()),
                                    "role": effective_role or "",
                                    "target_role": effective_role or "",
                                    "recognition": {
                                        "phase": "ready",
                                        "message": "推荐已更新",
                                        "ally_count": len(summary.get("ally_picks", [])),
                                        "enemy_count": len(summary.get("enemy_picks", [])),
                                        "ban_count": len(summary.get("ally_bans", []) + summary.get("enemy_bans", [])),
                                        "last_scan_at": int(time.time()),
                                        "recommendation_status": "ready",
                                    }
                                }
                                for r in recs[:10]:
                                    ls["recommendations"].append({
                                        "champion": r.get("champion", ""),
                                        "champion_cn": r.get("champion_cn", ""),
                                        "final_score": r.get("final_score", 0),
                                        "reasons": r.get("reasons", [])
                                    })
                                ls_path = Path(__file__).parent / "data" / "live_state.json"
                                ld_path = Path(__file__).parent / "data" / "live_draft.json"
                                # Preserve existing lane_recs if we can't find new ones
                                if not lane_recs_list:
                                    try:
                                        _existing = json.loads(ld_path.read_text(encoding='utf-8')) if ld_path.exists() else {}
                                        old_lane = _existing.get("lane_recommendations", [])
                                        if old_lane:
                                            lane_recs_list = old_lane
                                            ls["lane_recommendations"] = old_lane
                                    except:
                                        pass
                                write_live_state(ls)
                            except Exception as _v10e:
                                print(f"STATE_WRITE_ERR: {_v10e}")
                            last_summary = summary
                        if hide_capture_window:
                            latest_preview = None
                        else:
                            latest_preview = draw_results(client_image, results)
                            if SAVE_DEBUG_IMAGES and summary_changed:
                                cv2.imwrite(CLIENT_DEBUG_IMAGE, client_image)
                                cv2.imwrite(BP_DEBUG_IMAGE, latest_preview)
                next_capture_at = now + INTERVAL_SECONDS
            if not hide_capture_window and latest_preview is not None:
                cv2.imshow(WINDOW_NAME, latest_preview)
            if hide_capture_window:
                time.sleep(0.02)
            else:
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q")):
                    break
    if not hide_capture_window:
        cv2.destroyAllWindows()


def diagnose_mode():
    name_map = load_chinese_name_map()
    templates = load_hero_templates(TEMPLATE_DIR, name_map)
    hero_count = len({t.name for t in templates})
    print(f"Champions: {hero_count}, templates: {len(templates)}")
    print()

    hwnd = find_lol_window()
    if hwnd is None:
        print("No LOL window found!")
        return

    restore_lol_window(hwnd)
    window_rect = get_window_client_rect(hwnd)
    with mss.MSS() as sct:
        client_image = capture_client_image(sct, window_rect)
    if client_image is None:
        print("Screenshot failed!")
        return

    print(f"Image: {client_image.shape[1]}x{client_image.shape[0]}")
    print("-" * 60)
    display_img = client_image.copy()
    all_slots = build_slot_definitions()

    for base_slot in all_slots:
        slot = scale_slot(base_slot, client_image)
        crop = crop_slot(client_image, slot)
        if crop is None:
            continue
        color = (0, 255, 0) if "ally" in slot.group else (0, 165, 255)
        cv2.rectangle(display_img, (slot.x, slot.y), (slot.x + slot.width, slot.y + slot.height), color, 2)
        cv2.putText(display_img, slot.slot_id, (slot.x, max(14, slot.y - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1, cv2.LINE_AA)
        if not slot_has_enough_texture(crop):
            print(f"[{slot.group:12s}] {slot.slot_id:20s} SKIP empty/no texture")
            continue
        # Ban slots use dedicated ban matcher
        if b'ban' in slot.group:
            name, score = best_match_ban_slot(crop, templates)
            passed = score >= BAN_MATCH_THRESHOLD
        else:
            matches = []
            for t in templates:
                if t.image_bgr.shape[0] < crop.shape[0] or t.image_bgr.shape[1] < crop.shape[1]:
                    continue
                result = cv2.matchTemplate(t.image_bgr, crop, cv2.TM_CCOEFF_NORMED)
                _, score, _, _ = cv2.minMaxLoc(result)
                matches.append((float(score), t.name))
            matches.sort(reverse=True)
            top5 = matches[:5]
            best_name, best_score = top5[0]
            passed = best_score >= MATCH_THRESHOLD
        if passed:
            print(chr(91)+slot.group.rjust(12)+chr(93)+chr(32)+slot.slot_id.ljust(20)+chr(32)+chr(79)+chr(75)+chr(32)+chr(32)+name.ljust(12)+chr(32)+format(score, chr(46)+chr(52)+chr(102)))
        else:
            if b'ban' in slot.group:
                print(chr(91)+slot.group.rjust(12)+chr(93)+chr(32)+slot.slot_id.ljust(20)+chr(32)+chr(76)+chr(79)+chr(87)+chr(32)+chr(40)+chr(98)+chr(101)+chr(115)+chr(116)+chr(61)+name.ljust(12)+chr(32)+format(score,chr(46)+chr(52)+chr(102))+chr(44)+chr(32)+chr(110)+chr(101)+chr(101)+chr(100)+chr(62)+chr(61)+str(BAN_MATCH_THRESHOLD)+chr(41))
            else:
                print(chr(91)+slot.group.rjust(12)+chr(93)+chr(32)+slot.slot_id.ljust(20)+chr(32)+chr(76)+chr(79)+chr(87)+chr(32)+chr(40)+chr(98)+chr(101)+chr(115)+chr(116)+chr(61)+best_name.ljust(12)+chr(32)+format(best_score,chr(46)+chr(52)+chr(102))+chr(44)+chr(32)+chr(110)+chr(101)+chr(101)+chr(100)+chr(62)+chr(61)+str(MATCH_THRESHOLD)+chr(41))
                print(chr(70)+chr(79)+chr(82)+chr(58)+chr(32)+chr(84)+chr(79)+chr(80)+chr(53)+chr(58))
                for j, (s, nm) in enumerate(matches[:5]):
                    print(chr(32)*39+str(j+1)+chr(46)+chr(32)+nm.ljust(20)+chr(32)+format(s,chr(46)+chr(52)+chr(102)))
                print(f"{' ' * 39}{i+1}. {n:20s} {s:.4f}")

    cv2.imwrite(BP_DEBUG_IMAGE, display_img)
    print(f"\nDiagnostic saved: {BP_DEBUG_IMAGE}")
    print("Press Q or ESC to close.")
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.imshow(WINDOW_NAME, display_img)
    while True:
        key = cv2.waitKey(50) & 0xFF
        if key in (27, ord("q")):
            break
    cv2.destroyAllWindows()

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in ("--calibrate", "--calibrate-bans"):
        calibrate_ban_slots()
        return
    if len(sys.argv) > 1 and sys.argv[1] == "--analyze":
        from recommendation_engine import TeamAnalyzer
        _analyzer = TeamAnalyzer()
        main_loop_with_analysis(_analyzer)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--recommend":
        target_role = sys.argv[2] if len(sys.argv) > 2 else None
        recommend_loop(target_role)
        return

    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        diagnose_mode()
        return

    name_map = load_chinese_name_map()
    templates = load_hero_templates(TEMPLATE_DIR, name_map)
    hero_count = len({template.name for template in templates})
    print(f"已加载英雄: {hero_count}，预计算模板: {len(templates)}，模板目录: {TEMPLATE_DIR}")
    print("识别目标: 左侧己方已选、右侧对方已选；用 --calibrate 标记禁位坐标后可识别禁位")

    latest_preview: Optional[np.ndarray] = None
    next_capture_at = 0.0
    last_summary: Optional[Dict[str, List[str]]] = None
    slot_cache: Dict[str, CachedSlot] = {}
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    with mss.MSS() as sct:
        while True:
            now = time.monotonic()

            if now >= next_capture_at:
                hwnd = find_lol_window()
                if hwnd is None:
                    print("未找到 LOL 客户端窗口，请确认 LeagueClientUx.exe 正在运行。")
                    latest_preview = None
                else:
                    restore_lol_window(hwnd)
                    if FOCUS_LOL_WINDOW:
                        focus_lol_window(hwnd)

                    window_rect = get_window_client_rect(hwnd)
                    client_image = capture_client_image(sct, window_rect)
                    if client_image is None:
                        print("LOL 窗口当前无法截图，请手动点开客户端，不要最小化。")
                        latest_preview = None
                    else:
                        start_time = time.perf_counter()
                        results, recognized_count = recognize_bp_slots(client_image, templates, slot_cache)
                        elapsed_ms = (time.perf_counter() - start_time) * 1000
                        summary = summarize_results(results)
                        summary_changed = summary != last_summary
                        if summary_changed:
                            print_summary(summary)
                            print(f"本次识别耗时: {elapsed_ms:.0f} ms，重新识别槽位: {recognized_count}")
                                                        # V10: Write live state for unified UI
                            try:
                                import json
                                from pathlib import Path
                                from analysis.draft_session_control import write_live_state
                                ls={"ally":summary.get("ally_picks",[]),"enemy":summary.get("enemy_picks",[]),"bans":summary.get("ally_bans",[])+summary.get("enemy_bans",[]),"recommendations":[],"timestamp":int(time.time()),"target_role":""}
                                recs=[]
                                write_live_state(ls)
                            except: pass
                            last_summary = summary

                        latest_preview = draw_results(client_image, results)
                        if SAVE_DEBUG_IMAGES and summary_changed:
                            cv2.imwrite(CLIENT_DEBUG_IMAGE, client_image)
                            cv2.imwrite(BP_DEBUG_IMAGE, latest_preview)

                next_capture_at = now + INTERVAL_SECONDS

            if latest_preview is not None:
                cv2.imshow(WINDOW_NAME, latest_preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

ALLY_BAN_SLOTS: list[tuple[str, int, int, int, int]] = [["ally_ban_1", 64, 45, 55, 55], ["ally_ban_2", 64, 142, 55, 55], ["ally_ban_3", 64, 239, 55, 55], ["ally_ban_4", 64, 336, 55, 55], ["ally_ban_5", 64, 433, 55, 55]]
ENEMY_BAN_SLOTS: list[tuple[str, int, int, int, int]] = [["enemy_ban_1", 1430, 45, 55, 55], ["enemy_ban_2", 1430, 142, 55, 55], ["enemy_ban_3", 1430, 239, 55, 55], ["enemy_ban_4", 1430, 336, 55, 55], ["enemy_ban_5", 1430, 433, 55, 55]]
