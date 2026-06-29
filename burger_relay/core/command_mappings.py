"""Built-in hard-match command mappings and ingredient tables.

All Chinese danmaku keywords are mapped directly — no LLM needed for recognition.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Exclusion prefixes — the following word gets "without"
# ---------------------------------------------------------------------------
_EXCLUDE_PREFIXES = (
    "不要", "不加", "去掉", "去除", "别加", "无", "去",
    "without", "no",
)

# ---------------------------------------------------------------------------
# Trigger words → !Burgie (even without ! prefix)
# ---------------------------------------------------------------------------
BURGER_TRIGGERS: tuple[str, ...] = (
    "点单", "点餐", "来个", "来一个", "我要", "要一个",
    "点个", "下单", "订", "点菜",
)

# ---------------------------------------------------------------------------
# Ingredient map: Chinese → English
# ---------------------------------------------------------------------------
INGREDIENT_MAP: dict[str, str] = {
    # -- Doneness --
    "生": "raw",
    "生肉": "raw",
    "生的": "raw",
    "三分熟": "raw",
    "三成熟": "raw",
    "轻熟": "medium",
    "五分熟": "medium",
    "五成熟": "medium",
    "五分": "medium",
    "半熟": "medium",
    "全熟": "well done",
    "七分熟": "well done",
    "焦": "well done",
    "焦香": "well done",
    "熟透": "well done",
    "烤焦": "well done",
    # -- Veggie --
    "素食": "vegan",
    "素": "vegan",
    "纯素": "vegan",
    "素的": "vegan",
    "素肉": "vegan",
    "全素": "vegan",
    # -- Toppings --
    "肉": "meat",
    "肉饼": "meat",
    "肉排": "meat",
    "洋葱": "onion",
    "烤洋葱": "grilled onion",
    "焦糖洋葱": "grilled onion",
    "番茄": "tomato",
    "西红柿": "tomato",
    "生菜": "lettuce",
    "青菜": "lettuce",
    "芝士": "cheese",
    "奶酪": "cheese",
    "起司": "cheese",
    "双倍芝士": "extra cheese",
    "多芝士": "extra cheese",
    "多加芝士": "extra cheese",
    "额外芝士": "extra cheese",
    # -- Sauces --
    "番茄酱": "ketchup",
    "芥末": "mustard",
    "芥末酱": "mustard",
    "蛋黄酱": "mayo",
    "美乃滋": "mayo",
    "沙拉酱": "mayo",
    "特色酱": "fav sauce",
    "最爱酱": "fav sauce",
    "不加酱": "without sauce",
    "去酱": "without sauce",
    "无酱": "without sauce",
    # -- Drinks --
    "可乐": "cola",
    "柠檬水": "lemonade",
    "柠檬汁": "lemonade",
    "橙汁": "orange soda",
    "橘子汽水": "orange soda",
    "芬达": "orange soda",
    # -- Special --
    "压饼": "smash",
    "压扁": "smash",
    "拍扁": "smash",
    "拍饼": "smash",
}

# ---------------------------------------------------------------------------
# Complaint map: Chinese keyword → command
# ---------------------------------------------------------------------------
COMPLAINT_MAP: dict[str, str] = {
    # Dirty
    "脏了": "!Dirty",
    "掉了": "!Dirty",
    "掉地上": "!Dirty",
    "地上": "!Dirty",
    "弄脏": "!Dirty",
    # Fire
    "着火": "!Fire",
    "起火": "!Fire",
    "烧了": "!Fire",
    "着火了": "!Fire",
    "火": "!Fire",
    "烧焦": "!Fire",
    # Noise
    "吵": "!Noise",
    "太吵": "!Noise",
    "噪音": "!Noise",
    "太吵了": "!Noise",
    "闹": "!Noise",
    # Fence
    "栅栏": "!Fence",
    "围栏": "!Fence",
    # Window
    "窗户": "!Window",
    "扔窗": "!Window",
    "扔出去": "!Window",
    # Door
    "出门": "!Door",
    "离开厨房": "!Door",
    "去仓库": "!Door",
    "跑了": "!Door",
}

# ---------------------------------------------------------------------------
# Interact map: Chinese keyword → command
# ---------------------------------------------------------------------------
INTERACT_MAP: dict[str, str] = {
    "按铃": "!Bell",
    "打铃": "!Bell",
    "铃铛": "!Bell",
    "敲铃": "!Bell",
    "按铃2": "!Bell2",
    "铃2": "!Bell2",
    "按铃3": "!Bell3",
    "铃3": "!Bell3",
    "铃歌": "!Bellsong",
    "连续铃": "!Bellsong",
    "再见": "!Leave",
    "拜拜": "!Leave",
    "走了": "!Leave",
    "离开": "!Leave",
}


# ---------------------------------------------------------------------------
# Hard-match engine
# ---------------------------------------------------------------------------

def get_hard_match_command(text: str) -> str | None:
    """Try to hard-match a danmaku text to a game command using built-in rules.

    Priority:
    1. Burger triggers (e.g. "点单 ...") → parse as !Burgie
    2. Exact complaint/interact keyword matches
    3. !Burgie / !command prefix matches
    """
    t = text.strip()
    if not t:
        return None

    t_lower = t.lower()

    # ---- 1) Burger trigger words ----
    for trigger in BURGER_TRIGGERS:
        if t_lower.startswith(trigger):
            rest = t[len(trigger):].strip()
            if rest:
                return _parse_burgie(rest)
            return "!Burgie"

    # ---- 2) Exact keyword match ----
    if t_lower in COMPLAINT_MAP:
        return COMPLAINT_MAP[t_lower]
    if t_lower in INTERACT_MAP:
        return INTERACT_MAP[t_lower]

    # ---- 3) Keyword-in-text match ----
    # Longer keywords checked first to avoid partial matches
    sorted_complaints = sorted(COMPLAINT_MAP.items(), key=lambda x: -len(x[0]))
    for kw, cmd in sorted_complaints:
        if kw in t_lower:
            return cmd

    sorted_interacts = sorted(INTERACT_MAP.items(), key=lambda x: -len(x[0]))
    for kw, cmd in sorted_interacts:
        if kw in t_lower:
            return cmd

    return None


def _parse_burgie(rest: str) -> str:
    """Parse the ingredient part of a !Burgie command."""
    if not rest or not rest.strip():
        return "!Burgie"

    rest = rest.strip()
    sorted_ings = sorted(INGREDIENT_MAP.items(), key=lambda x: -len(x[0]))
    max_prefix_len = max((len(p) for p in _EXCLUDE_PREFIXES), default=5)

    included: list[str] = []
    excluded: list[str] = []
    matched_positions: set[int] = set()

    for chinese, english in sorted_ings:
        pos = 0
        while True:
            idx = rest.find(chinese, pos)
            if idx == -1:
                break
            # Check exclusion prefix
            lookback = max(0, idx - max_prefix_len - 1)
            before = rest[lookback:idx]
            is_excluded = any(
                before.endswith(p) or before.rstrip().endswith(p)
                for p in _EXCLUDE_PREFIXES
            )
            pos = idx + len(chinese)

            this_range = set(range(idx, idx + len(chinese)))
            if this_range & matched_positions:
                continue

            matched_positions.update(this_range)
            if is_excluded:
                excluded.append(english)
            else:
                included.append(english)

    if not included:
        return f"!Burgie {rest}"

    cmd = "!Burgie"
    for ing in included:
        cmd += f" + {ing}"
    for ex in excluded:
        cmd += f" + without {ex}"
    return cmd


def is_hard_match(text: str) -> bool:
    """Check if text can be resolved via hard matching alone."""
    return get_hard_match_command(text) is not None
