import requests, json, os, time, re
from lxml import html
from pathlib import Path


class LolalyticsClient:
    _current_patch = None
    BASE = 'https://lolalytics.com'
    CACHE_BASE = Path(__file__).resolve().parent.parent / "data" / "cache" / "lolalytics"
    CACHE_TTL = 86400

    LANE_MAP = {
        'top': 'top', 'jg': 'jungle', 'jng': 'jungle', 'jungle': 'jungle',
        'mid': 'middle', 'middle': 'middle',
        'bot': 'bottom', 'bottom': 'bottom', 'adc': 'bottom',
        'sup': 'support', 'supp': 'support', 'support': 'support',
    }

    TIER_MAP = {
        'challenger': 'challenger', 'c': 'challenger',
        'grandmaster': 'grandmaster', 'gm': 'grandmaster',
        'master': 'master', 'm': 'master',
        'diamond_plus': 'diamond_plus', 'd+': 'diamond_plus',
        'emerald': 'emerald', 'e': 'emerald', 'eme': 'emerald',
        'platinum_plus': 'platinum_plus', 'p+': 'platinum_plus',
        'gold_plus': 'gold_plus', 'g+': 'gold_plus',
        'all': 'all',
    }

    def __init__(self, cache_base=None, patch=None):
        if cache_base:
            self.CACHE_BASE = Path(cache_base)
        self.CACHE_BASE.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        if patch:
            self._current_patch = patch
        else:
            self._current_patch = self._detect_patch()

    def get_current_patch(self):
        if not self._current_patch:
            self._current_patch = self._detect_patch()
        return self._current_patch

    def _detect_patch(self):
        try:
            r = self._session.get(f'{self.BASE}/lol/tierlist/', timeout=10)
            r.raise_for_status()
            m = re.search(r'Patch\s*(\d+\.\d+)', r.text)
            if m:
                return m.group(1)
            m = re.search(r'(\d{2}\.\d{2,3})', r.text[:5000])
            if m:
                return m.group(1)
        except Exception:
            pass
        return 'unknown'

    def _cache_dir(self, patch=None):
        p = patch or self._current_patch or 'unknown'
        d = self.CACHE_BASE / p
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _cache_key(self, endpoint, **params):
        parts = [endpoint]
        for k, v in sorted(params.items()):
            if v: parts.append(f'{k}={v}')
        return '_'.join(parts).replace('/', '_').lower()

    def _cache_get(self, key, patch=None):
        # Primary: patch-aware directory
        path = self._cache_dir(patch) / f'{key}.json'
        if path.exists():
            try:
                age = time.time() - path.stat().st_mtime
                if age < self.CACHE_TTL:
                    raw = json.loads(path.read_text(encoding='utf-8'))
                    if isinstance(raw, dict) and 'data' in raw and 'patch' in raw:
                        return raw['data']
                    return raw
            except Exception:
                pass
        # Fallback: old flat directory (backward compat)
        legacy = self.CACHE_BASE / f'{key}.json'
        if legacy.exists():
            try:
                age = time.time() - legacy.stat().st_mtime
                if age < self.CACHE_TTL:
                    return json.loads(legacy.read_text(encoding='utf-8'))
            except Exception:
                pass
        return None

    def _cache_set(self, key, data, patch=None):
        p = patch or self._current_patch or 'unknown'
        path = self._cache_dir(p) / f'{key}.json'
        wrapped = {
            'patch': p,
            'timestamp': int(time.time()),
            'data': data,
        }
        path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2), encoding='utf-8')

    def clean_old_cache(self, max_days=30):
        now = time.time()
        cutoff = now - max_days * 86400
        removed = 0
        for patch_dir in self.CACHE_BASE.iterdir():
            if not patch_dir.is_dir():
                continue
            for f in patch_dir.iterdir():
                if f.suffix == '.json':
                    try:
                        if f.stat().st_mtime < cutoff:
                            f.unlink()
                            removed += 1
                    except Exception:
                        pass
        return removed

    def _fetch(self, url, timeout=15):
        try:
            r = self._session.get(url, timeout=timeout)
            r.raise_for_status()
            return html.fromstring(r.content)
        except Exception:
            return None

    def _normalize(self, name):
        name = name.lower().strip()
        for ch in [chr(39), '.', ' ', '&', '_']:
            name = name.replace(ch, '')
        aliases = {
            'monkeyking': 'wukong',
        }
        name = aliases.get(name, name)
        return name

    def _build_url(self, path, lane='', tier=''):
        params = []
        if lane:
            l = self.LANE_MAP.get(lane.lower())
            if l: params.append(f'lane={l}')
        if tier:
            t = self.TIER_MAP.get(tier.lower(), tier)
            params.append(f'tier={t}')
        qs = '&'.join(params)
        return f'{self.BASE}{path}?{qs}' if qs else f'{self.BASE}{path}'

    def _extract_ssr_texts(self, html_text):
        texts = []
        pos = 0
        while True:
            start = html_text.find('<!--t=', pos)
            if start < 0: break
            end_comment = html_text.find('-->', start)
            if end_comment < 0: break
            end_value = html_text.find('<!---->', end_comment)
            if end_value < 0: break
            texts.append(html_text[end_comment+3:end_value])
            pos = end_value + 7
        return texts

    # ---- Public API ----

    def get_champion_stats(self, champion, lane='', tier='emerald'):
        key = self._cache_key('stats', champion=champion, lane=lane, tier=tier)
        cached = self._cache_get(key)
        if cached: return cached

        champ = self._normalize(champion)
        url = self._build_url(f'/lol/{champ}/build/', lane, tier)
        tree = self._fetch(url)
        if tree is None: return None

        stats = []
        xp = './/*[contains(@class, ' + chr(39) + 'mb-1' + chr(39) + ') and contains(@class, ' + chr(39) + 'font-bold' + chr(39) + ')]'
        for el in tree.xpath(xp):
            t = (el.text_content() or '').strip()
            if t and len(t) < 40: stats.append(t)

        if len(stats) < 8: return None
        def pct(v):
            try: return float(v.replace('%', '').replace(',', ''))
            except: return 0.0
        try:
            rank = int(stats[5].split('/')[0].strip()) if '/' in stats[5] else 0
        except Exception:
            rank = 0
        result = {
            'winrate': pct(stats[0]),
            'pickrate': pct(stats[3]),
            'banrate': pct(stats[6]),
            'tier': stats[4],
            'rank': rank,
            'games': int(stats[7].replace(',', '')) if stats[7].replace(',', '').isdigit() else 0,
        }
        self._cache_set(key, result)
        return result

    def get_matchup(self, champion, opponent, lane='', tier='emerald'):
        key = self._cache_key('matchup', a=champion, b=opponent, lane=lane, tier=tier)
        cached = self._cache_get(key)
        if cached: return cached
        c1 = self._normalize(champion)
        c2 = self._normalize(opponent)
        url = self._build_url(f'/lol/{c1}/vs/{c2}/build/', lane, tier)
        tree = self._fetch(url)
        if tree is None: return None
        stats = []
        xp = './/*[contains(@class, ' + chr(39) + 'mb-1' + chr(39) + ') and contains(@class, ' + chr(39) + 'font-bold' + chr(39) + ')]'
        for el in tree.xpath(xp):
            t = (el.text_content() or '').strip()
            if t and len(t) < 40: stats.append(t)
        if len(stats) < 2: return None
        wr_val = float(stats[0].replace(chr(37), chr(32)).strip())
        gc = 0
        if len(stats) > 1:
            try: gc = int(stats[1].replace(chr(44), '').strip())
            except: pass
        result = {
            'champion': champion,
            'opponent': opponent,
            'winrate': wr_val,
            'avg_winrate': None,
            'delta': round(wr_val - 50, 1),
            'games': gc,
}
        self._cache_set(key, result)
        return result

    def get_counters(self, champion, lane='', tier='emerald'):
        key = self._cache_key('counters', champion=champion, lane=lane, tier=tier)
        cached = self._cache_get(key)
        if cached: return cached
        champ = self._normalize(champion)
        url = self._build_url(f'/lol/{champ}/counters/', lane, tier)
        try:
            r = self._session.get(url, timeout=15)
            r.raise_for_status()
        except Exception:
            return None
        texts = self._extract_ssr_texts(r.text)
        pct_pat = __import__('re').compile(r'^\d+\.\d+$')
        results = []
        i = 0
        while i < len(texts):
            t = texts[i].strip()
            if (i + 2 < len(texts) and
                t and t[0].isalpha() and t[0].isupper() and
                len(t) < 25 and
                pct_pat.match(texts[i+1].strip()) and
                pct_pat.match(texts[i+2].strip())):
                wr1 = float(texts[i+1].strip())
                wr2 = float(texts[i+2].strip())
                delta = round(wr1 - wr2, 1)
                name = t.replace('&#39;', chr(39)).replace('&amp;', '&')
                results.append({'champion': name, 'delta': delta})
                i += 13
            else:
                i += 1
        self._cache_set(key, results)
        return results

    def get_runes(self, champion, lane='', tier='emerald'):
        champ = self._normalize(champion)
        url = self._build_url(f'/lol/{champ}/build/', lane, tier)
        tree = self._fetch(url)
        if tree is None: return []
        seen = set()
        results = []
        for el in tree.xpath('.//img[contains(@src, ' + chr(39) + 'rune68/' + chr(39) + ')]'):
            alt = el.get('alt', '')
            if alt and alt not in seen and len(alt) < 40:
                seen.add(alt)
                results.append({'name': alt, 'winrate': None, 'pickrate': None})
        return results

    def get_builds(self, champion, lane='', tier='emerald'):
        champ = self._normalize(champion)
        url = self._build_url(f'/lol/{champ}/build/', lane, tier)
        tree = self._fetch(url)
        if tree is None: return []
        seen = set()
        items = []
        for el in tree.xpath('.//img[contains(@src, ' + chr(39) + 'item64/' + chr(39) + ')]'):
            alt = el.get('alt', '')
            if alt and alt not in seen and len(alt) < 40:
                seen.add(alt)
                items.append(alt)
        return [{'items': items[:6], 'winrate': None}]

    def get_tierlist(self, lane='', tier='emerald', limit=50):
        url = self._build_url('/lol/tierlist/', lane, tier)
        try:
            r = self._session.get(url, timeout=15)
            r.raise_for_status()
        except Exception:
            return None
        texts = self._extract_ssr_texts(r.text)
        skip = {'list', 'GLOBAL', 'Home', 'Tier List', 'Leaderboard', 'Counters'}
        champs = []
        current_tier = None
        for t in texts:
            t = t.strip()
            if not t or t in skip or len(t) > 50: continue
            if t.replace(',', '').replace('.', '').isdigit(): continue
            if t in (chr(83)+chr(43), chr(83), chr(83)+chr(45), chr(65)+chr(43), chr(65), chr(65)+chr(45), chr(66)+chr(43), chr(66), chr(66)+chr(45), chr(67)+chr(43), chr(67), chr(67)+chr(45), chr(68)+chr(43), chr(68), chr(68)+chr(45), chr(70)):
                current_tier = t
            elif current_tier and t[0].isupper() and len(t) < 25:
                champs.append({'name': t, 'tier': current_tier})
                if limit and len(champs) >= limit: break
        return champs

