import sys
import os
import re
import json
import math
import sqlite3
import hashlib
import subprocess
import urllib.request
import urllib.parse
from pathlib import Path
from collections import OrderedDict, Counter
from concurrent.futures import ThreadPoolExecutor

from PIL import Image
from PIL.ExifTags import TAGS
from send2trash import send2trash

try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False

from PySide6.QtCore import (
    Qt, QThread, Signal, QObject, QRunnable, QThreadPool,
    QAbstractListModel, QModelIndex, QSize, QMimeData, QUrl, QTimer, QItemSelectionModel, QItemSelection
)
from PySide6.QtGui import QPixmap, QImage, QAction, QColor, QDrag, QKeySequence, QShortcut, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QListView, QLabel, QFileDialog,
    QSplitter, QTextEdit, QCheckBox, QMessageBox, QProgressBar,
    QMenu, QAbstractItemView, QComboBox
)

DB_PATH = "ai_images_index_v2.db"
CONFIG_PATH = "config.json"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
THUMB_SIZE = 160

# モダン・ダークテーマ スタイルシート
APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #181a1f;
    color: #e2e6ed;
    font-family: "Segoe UI", "Yu Gothic UI", "Meiryo", sans-serif;
    font-size: 13px;
}
QLineEdit, QComboBox, QTextEdit {
    background-color: #22252c;
    color: #f0f3f8;
    border: 1px solid #353a45;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #3b82f6;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #3b82f6;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QPushButton {
    background-color: #2a2f3a;
    color: #e6eaf2;
    border: 1px solid #3c4250;
    border-radius: 6px;
    padding: 5px 11px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #353b49;
    border-color: #4f586b;
}
QPushButton:pressed {
    background-color: #20242d;
}
QPushButton:disabled {
    background-color: #1f2229;
    color: #666d7d;
}
QPushButton#PrimaryBtn {
    background-color: #2563eb;
    border-color: #3b82f6;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#PrimaryBtn:hover {
    background-color: #1d4ed8;
}
QPushButton#AccentBtn {
    background-color: #0d9488;
    border-color: #14b8a6;
    color: #ffffff;
    font-weight: bold;
}
QPushButton#AccentBtn:hover {
    background-color: #0f766e;
}
QPushButton#DangerBtn {
    background-color: #991b1b;
    border-color: #b91c1c;
    color: #ffffff;
}
QPushButton#DangerBtn:hover {
    background-color: #7f1d1d;
}
QListView {
    background-color: #14161a;
    border: 1px solid #2c313c;
    border-radius: 8px;
    padding: 6px;
    outline: none;
}
QListView::item {
    background-color: #1e2128;
    border: 1px solid #2b303b;
    border-radius: 6px;
    padding: 4px;
    color: #d8dde6;
}
QListView::item:hover {
    background-color: #262b35;
    border-color: #475569;
}
QListView::item:selected {
    background-color: #1e3a5f;
    border: 1px solid #3b82f6;
    color: #ffffff;
}
QCheckBox {
    spacing: 6px;
    color: #cfd5e0;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid #474e5d;
    background-color: #22252c;
}
QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #3b82f6;
}
QProgressBar {
    background-color: #22252c;
    border: 1px solid #353a45;
    border-radius: 5px;
    text-align: center;
    height: 16px;
}
QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 4px;
}
QSplitter::handle {
    background-color: #2c313c;
    width: 3px;
}
QStatusBar {
    background-color: #131519;
    color: #9ca3af;
    border-top: 1px solid #282c36;
}
QLabel#BadgeLabel {
    background-color: #252a34;
    border: 1px solid #384050;
    border-radius: 5px;
    padding: 4px 8px;
    color: #cbd5e1;
    font-size: 12px;
}
QScrollBar:vertical {
    background: #181a1f;
    width: 10px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #363c48;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #4b5364;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

# AI生成プロンプト特化 日本語->英語タグ辞書
JA_TAG_DICT: dict[str, list[str]] = {
    "女の子": ["1girl", "girl"],
    "少女": ["1girl", "girl"],
    "女性": ["1girl", "woman"],
    "男の子": ["1boy", "boy"],
    "少年": ["1boy", "boy"],
    "男性": ["1boy", "man"],
    "複数人": ["multiple_girls", "2girls", "group"],
    "青目": ["blue_eyes"],
    "青い目": ["blue_eyes"],
    "赤目": ["red_eyes"],
    "赤い目": ["red_eyes"],
    "緑目": ["green_eyes"],
    "緑の目": ["green_eyes"],
    "金目": ["yellow_eyes", "golden_eyes"],
    "オッドアイ": ["heterochromia"],
    "金髪": ["blonde_hair"],
    "黒髪": ["black_hair"],
    "茶髪": ["brown_hair"],
    "銀髪": ["silver_hair"],
    "白髪": ["white_hair"],
    "ピンク髪": ["pink_hair"],
    "青髪": ["blue_hair"],
    "赤髪": ["red_hair"],
    "ロングヘア": ["long_hair"],
    "長髪": ["long_hair"],
    "ショートヘア": ["short_hair"],
    "短髪": ["short_hair"],
    "ツインテール": ["twintails"],
    "ポニーテール": ["ponytail"],
    "ボブ": ["bob_cut"],
    "制服": ["school_uniform"],
    "セーラー服": ["serafuku", "school_uniform"],
    "ブレザー": ["blazer", "school_uniform"],
    "メイド": ["maid", "maid_headdress"],
    "メイド服": ["maid", "maid_headdress"],
    "着物": ["kimono"],
    "浴衣": ["yukata"],
    "ドレス": ["dress"],
    "水着": ["swimsuit", "bikini"],
    "鎧": ["armor"],
    "私服": ["casual"],
    "パーカー": ["hoodie"],
    "眼鏡": ["glasses"],
    "メガネ": ["glasses"],
    "帽子": ["hat"],
    "リボン": ["ribbon"],
    "猫耳": ["cat_ears"],
    "獣耳": ["animal_ears", "fox_ears", "cat_ears"],
    "狐耳": ["fox_ears"],
    "翼": ["wings"],
    "羽": ["wings", "feathers"],
    "天使": ["angel", "angel_wings"],
    "悪魔": ["demon", "demon_horns", "demon_wings"],
    "笑顔": ["smile"],
    "微笑み": ["smile", "light_smile"],
    "泣き顔": ["crying", "tears"],
    "赤面": ["blush"],
    "照れ": ["blush"],
    "剣": ["sword", "katana"],
    "魔法": ["magic"],
    "サイバーパンク": ["cyberpunk", "neon"],
    "ファンタジー": ["fantasy"],
    "夜景": ["night", "night_sky", "city_lights"],
    "夜": ["night"],
    "青空": ["blue_sky"],
    "夕暮れ": ["sunset"],
    "桜": ["cherry_blossoms"],
    "海": ["ocean", "beach"],
    "森": ["forest"],
    "室内部屋": ["indoors"],
    "室内": ["indoors"],
    "屋外": ["outdoors"],
    "モノクロ": ["monochrome", "greyscale"],
    "白黒": ["monochrome", "greyscale"],
    "高品質": ["masterpiece", "best_quality"],
}

# 表記ゆれ・類義タググループ
SYNONYM_GROUPS: list[set[str]] = [
    {"smile", "grin", "laugh", "happy", "light_smile"},
    {"cry", "crying", "tears", "sad", "sobbing"},
    {"cyberpunk", "neon", "sci_fi", "futuristic"},
    {"night", "night_sky", "moonlight", "starry_sky"},
    {"school_uniform", "serafuku", "blazer"},
    {"sword", "katana", "blade", "weapon"},
    {"swimsuit", "bikini", "one_piece_swimsuit"},
    {"cat_ears", "nekomimi", "animal_ears"},
    {"monochrome", "greyscale", "grayscale"},
    {"masterpiece", "best_quality", "high_quality"},
]

_TRANSLATION_CACHE: dict[str, str] = {}
_JA_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]")


def resource_path(relative_path: str) -> str:
    """PyInstaller単一exe実行時と通常Python実行時の両方でリソースパスを解決する"""
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


# ==========================================
# 1. プロンプト正規化・翻訳・メタデータ＆ハッシュ抽出
# ==========================================
def normalize_prompt(text: str) -> str:
    """強調構文・重み数値・記号を除去して検索用テキストを生成する"""
    if not text:
        return ""
    # LoRA / Hypernetタグのコロン・重みをスペース区切りへ (<lora:name:0.8> -> lora name)
    text = re.sub(r"<([^:>]+):([^:>]+)(?::[^>]+)?>", r" \1 \2 ", text)
    # 重み数値の除去 (:1.2, :0.85 など)
    text = re.sub(r":\s*[+-]?\d+(?:\.\d+)?", " ", text)
    # 括弧やカンマなどの区切り記号をスペースへ置換（アンダースコアは単語の一部として保持）
    text = re.sub(r"[()\[\]{},|\"'`~!@#$%^&*+=\\/?;<>]+", " ", text)
    # 連続空白の圧縮と小文字化
    return re.sub(r"\s+", " ", text).strip().lower()


def compute_dhash(img: Image.Image, hash_size: int = 8) -> str:
    """Pillowのみで高速計算できる64bit差分ハッシュ(dHash)を16進文字列で返す"""
    try:
        gray = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
        bits = 0
        for row in range(hash_size):
            row_start = row * (hash_size + 1)
            for col in range(hash_size):
                left = pixels[row_start + col]
                right = pixels[row_start + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return f"{bits:016x}"
    except Exception:
        return ""


def hamming_distance_hex(hex1: str, hex2: str) -> int:
    """16進dHash同士のハミング距離を返す"""
    if not hex1 or not hex2 or len(hex1) != len(hex2):
        return 64
    return (int(hex1, 16) ^ int(hex2, 16)).bit_count()


def _translate_ja_to_en(word: str) -> str:
    """日本語単語を英語へ翻訳（キャッシュ付き・APIキー不要）"""
    if word in _TRANSLATION_CACHE:
        return _TRANSLATION_CACHE[word]

    translated = ""
    if HAS_DEEP_TRANSLATOR:
        try:
            translated = GoogleTranslator(source="ja", target="en").translate(word) or ""
        except Exception:
            translated = ""

    if not translated:
        try:
            q = urllib.parse.quote(word)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=ja&tl=en&dt=t&q={q}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and data[0] and data[0][0]:
                    translated = str(data[0][0][0])
        except Exception:
            translated = ""

    cleaned = normalize_prompt(translated)
    _TRANSLATION_CACHE[word] = cleaned
    return cleaned


def _expand_variants(term: str, expand_similar: bool) -> list[str]:
    """アンダースコア表記ゆれ・類義タグを展開する"""
    variants = []
    base = term.strip().lower()
    if not base:
        return variants

    def add_unique(val: str):
        v = val.strip()
        if v and v not in variants:
            variants.append(v)

    add_unique(base)
    if "_" in base:
        add_unique(base.replace("_", " "))
        if expand_similar:
            add_unique(base.replace("_", ""))
    elif " " in base:
        add_unique(base.replace(" ", "_"))
        if expand_similar:
            add_unique(base.replace(" ", ""))

    if expand_similar:
        for group in SYNONYM_GROUPS:
            if base in group or base.replace(" ", "_") in group:
                for syn in sorted(group):
                    add_unique(syn)
                    if "_" in syn:
                        add_unique(syn.replace("_", " "))
    return variants


def _token_to_candidates(tok: str, expand_similar: bool) -> tuple[list[str], bool]:
    """1トークンを英語タグ候補リストへ変換する。(候補リスト, 日本語翻訳が発生したか)を返す"""
    candidates: list[str] = []
    translated_flag = False
    if _JA_PATTERN.search(tok):
        translated_flag = True
        if tok in JA_TAG_DICT:
            for tag in JA_TAG_DICT[tok]:
                for v in _expand_variants(tag, expand_similar):
                    if v not in candidates:
                        candidates.append(v)
        else:
            en_text = _translate_ja_to_en(tok)
            if en_text:
                if " " in en_text:
                    for v in _expand_variants(en_text.replace(" ", "_"), expand_similar):
                        if v not in candidates:
                            candidates.append(v)
                for sub in en_text.split():
                    if sub not in {"a", "an", "the", "of", "in", "on", "with"}:
                        for v in _expand_variants(sub, expand_similar):
                            if v not in candidates:
                                candidates.append(v)
            if not candidates:
                candidates.append(tok.lower())
    else:
        norm_tok = normalize_prompt(tok)
        for sub in norm_tok.split():
            for v in _expand_variants(sub, expand_similar):
                if v not in candidates:
                    candidates.append(v)
    return candidates, translated_flag


def build_search_groups(
    raw_query: str,
    expand_similar: bool = False
) -> tuple[list[list[str]], list[list[str]], str]:
    """
    クエリをAND結合されたOR候補リスト（通常検索用 + マイナス除外用）に変換する。
    戻り値: (include_groups, exclude_groups, 変換表示テキスト)
    """
    cleaned = re.sub(r"[()\[\]{},|\"'`~!@#$%^&*+=\\/?;<>]+", " ", raw_query).strip()
    if not cleaned:
        return [], [], ""

    raw_tokens = [t for t in cleaned.split() if t]
    inc_groups: list[list[str]] = []
    exc_groups: list[list[str]] = []
    display_parts: list[str] = []
    has_translation = False
    has_exclusion = False

    for tok in raw_tokens:
        is_exclude = False
        if tok.startswith("-") and len(tok) > 1:
            is_exclude = True
            has_exclusion = True
            tok = tok[1:]

        candidates, tr_flag = _token_to_candidates(tok, expand_similar)
        if tr_flag:
            has_translation = True

        if candidates:
            prefix = "NOT " if is_exclude else ""
            if is_exclude:
                exc_groups.append(candidates)
            else:
                inc_groups.append(candidates)

            if len(candidates) == 1:
                display_parts.append(f"{prefix}{candidates[0]}")
            else:
                display_parts.append(
                    f"{prefix}({' OR '.join(candidates[:4])}{'...' if len(candidates) > 4 else ''})"
                )

    display_str = ""
    if has_translation or expand_similar or has_exclusion:
        display_str = f'検索式: "{raw_query.strip()}" → ' + " AND ".join(display_parts)
    return inc_groups, exc_groups, display_str


def _is_valid_ai_text(text: str) -> bool:
    """Exif UserComment 等がカメラメモではなくAI生成メタデータかを厳格判定する"""
    if not text:
        return False
    signatures = ("Steps:", "Negative prompt:", "Sampler:", "Seed:", "CFG scale:", "Model:")
    if any(sig in text for sig in signatures):
        return True
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict) and any(k in obj for k in ("prompt", "workflow", "inputs", "uc", "steps")):
                return True
        except Exception:
            pass
    return False


def _extract_model_and_loras_a1111(pos: str, raw: str) -> tuple[str, list[str]]:
    """A1111/Forge形式からモデル名とLoRAリストを抽出する"""
    model_name = ""
    m = re.search(r"(?:^|,\s*)Model:\s*([^,\n]+)", raw)
    if m:
        model_name = os.path.splitext(os.path.basename(m.group(1).strip()))[0]

    loras: list[str] = []
    for lm in re.finditer(r"<lora:([^:>]+)(?::[^>]+)?>", pos, flags=re.IGNORECASE):
        name = os.path.splitext(os.path.basename(lm.group(1).strip()))[0]
        if name and name not in loras:
            loras.append(name)

    # LoRA hashes フィールドからの補完抽出
    lh = re.search(r'Lora hashes:\s*"([^"]+)"', raw)
    if lh:
        for pair in lh.group(1).split(","):
            if ":" in pair:
                name = os.path.splitext(os.path.basename(pair.split(":", 1)[0].strip()))[0]
                if name and name not in loras:
                    loras.append(name)

    return model_name, loras


def _split_a1111_parameters(raw: str) -> tuple[str, str, str, str, list[str]]:
    pos, neg = "", ""
    if "Negative prompt:" in raw:
        parts = raw.split("Negative prompt:", 1)
        pos = parts[0].strip()
        rest = parts[1]
        if "\nSteps:" in rest:
            neg = rest.split("\nSteps:", 1)[0].strip()
        else:
            neg = rest.strip()
    else:
        pos = raw.split("\nSteps:", 1)[0].strip()
    model_name, loras = _extract_model_and_loras_a1111(pos, raw)
    return pos, neg, raw, model_name, loras


def _parse_comfyui_graph(data: dict) -> tuple[str, str, str, list[str]]:
    """
    ComfyUIのノードグラフを解析し、サンプラー接続を辿ってポジティブ・ネガティブを分離抽出する。
    あわせて Checkpoint / UNet / 各種LoRAノード（rgthree含む）も網羅的に抽出する。
    """
    model_name = ""
    loras: list[str] = []

    def add_lora(raw_name: str):
        if not raw_name or raw_name.lower() == "none":
            return
        cleaned = os.path.splitext(os.path.basename(raw_name.strip()))[0]
        if cleaned and cleaned not in loras:
            loras.append(cleaned)

    # 1. モデル名とLoRA名の全ノード走査
    for node in data.values():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        if not model_name and isinstance(inputs.get("ckpt_name"), str):
            model_name = os.path.splitext(os.path.basename(inputs["ckpt_name"]))[0]
        if not model_name and isinstance(inputs.get("unet_name"), str):
            model_name = os.path.splitext(os.path.basename(inputs["unet_name"]))[0]

        if isinstance(inputs.get("lora_name"), str):
            add_lora(inputs["lora_name"])

        # rgthree Power Lora Loader などの動的キー (lora_01, lora_1 等) に対応
        for k, v in inputs.items():
            if k.startswith("lora_") and isinstance(v, dict):
                if v.get("on", True) and isinstance(v.get("lora"), str):
                    add_lora(v["lora"])

    # 2. 特定ノードから上流へテキストを収集するヘルパー
    def collect_upstream_texts(start_node_id: str, visited: set[str]) -> list[str]:
        if start_node_id in visited or start_node_id not in data:
            return []
        visited.add(start_node_id)
        node = data[start_node_id]
        if not isinstance(node, dict):
            return []
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            return []

        collected: list[str] = []
        # テキスト入力フィールドを持つノード（CLIPTextEncode, CLIPTextEncodeSDXL 等）
        for text_key in ("text", "text_g", "text_l", "prompt", "positive", "negative"):
            val = inputs.get(text_key)
            if isinstance(val, str) and val.strip():
                collected.append(val.strip())

        # 上流リンク ([node_id, output_slot]) を辿る
        for val in inputs.values():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], (str, int)):
                collected.extend(collect_upstream_texts(str(val[0]), visited))
        return collected

    pos_texts: list[str] = []
    neg_texts: list[str] = []
    found_sampler_links = False

    # 3. サンプラー系ノードの positive / negative 入力リンクを起点に分離収集
    for node in data.values():
        if not isinstance(node, dict):
            continue
        class_type = str(node.get("class_type", ""))
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            continue

        if "Sampler" in class_type or ("positive" in inputs and "negative" in inputs):
            pos_link = inputs.get("positive")
            neg_link = inputs.get("negative")
            if isinstance(pos_link, list) and len(pos_link) >= 1:
                found_sampler_links = True
                for t in collect_upstream_texts(str(pos_link[0]), set()):
                    if t not in pos_texts:
                        pos_texts.append(t)
            if isinstance(neg_link, list) and len(neg_link) >= 1:
                found_sampler_links = True
                for t in collect_upstream_texts(str(neg_link[0]), set()):
                    if t not in neg_texts:
                        neg_texts.append(t)

    # 4. サンプラーリンクが見つからない特殊ワークフローの場合は全ノードテキストをフォールバック収集
    if not found_sampler_links:
        for node in data.values():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {})
            if isinstance(inputs, dict):
                for text_key in ("text", "text_g", "text_l"):
                    val = inputs.get(text_key)
                    if isinstance(val, str) and val.strip() and val.strip() not in pos_texts:
                        pos_texts.append(val.strip())

    # テキスト内の <lora:...> 記述も補完抽出
    all_joined = "\n".join(pos_texts + neg_texts)
    for lm in re.finditer(r"<lora:([^:>]+)(?::[^>]+)?>", all_joined, flags=re.IGNORECASE):
        add_lora(lm.group(1))

    return "\n".join(pos_texts), "\n".join(neg_texts), model_name, loras


def parse_image_metadata(filepath: str) -> tuple[bool, str, str, str, str, str, str]:
    """
    AI生成画像かどうかを厳格判定し、
    (is_ai_generated, positive, negative, raw_parameters, model, loras_csv, dhash) を返す。
    非生成画像は is_ai_generated=False を返す。
    """
    try:
        with Image.open(filepath) as img:
            info = img.info or {}

            # 1. Stable Diffusion WebUI (A1111 / Forge)
            if "parameters" in info:
                raw = str(info["parameters"]).strip()
                if raw:
                    pos, neg, raw, model_name, loras = _split_a1111_parameters(raw)
                    dhash = compute_dhash(img)
                    return True, pos, neg, raw, model_name, ",".join(loras), dhash

            # 2. ComfyUI (有効なJSONノード構造を持つ場合のみ)
            if "prompt" in info or "workflow" in info:
                raw_prompt = str(info.get("prompt") or info.get("workflow") or "").strip()
                try:
                    data = json.loads(raw_prompt)
                    if isinstance(data, dict) and data:
                        pos_str, neg_str, model_name, loras = _parse_comfyui_graph(data)
                        dhash = compute_dhash(img)
                        return True, pos_str, neg_str, raw_prompt, model_name, ",".join(loras), dhash
                except json.JSONDecodeError:
                    pass

            # 3. NovelAI
            software = str(info.get("Software", ""))
            if "Description" in info and ("NovelAI" in software or "Comment" in info or "Source" in info):
                pos = str(info["Description"]).strip()
                neg = ""
                if "Comment" in info:
                    try:
                        c_data = json.loads(str(info["Comment"]))
                        if isinstance(c_data, dict):
                            neg = str(c_data.get("uc", "")).strip()
                    except Exception:
                        pass
                model_name = str(info.get("Source", "NovelAI")).strip()
                raw = json.dumps(info, ensure_ascii=False)
                dhash = compute_dhash(img)
                return True, pos, neg, raw, model_name, "", dhash

            # 4. Exif (JPEG / WebP) - AI生成シグネチャを含む場合のみ認定
            exif = img.getexif()
            if exif:
                for tag_id, value in exif.items():
                    if TAGS.get(tag_id) == "UserComment" and isinstance(value, bytes):
                        decoded = ""
                        if value.startswith(b"UNICODE\x00"):
                            decoded = value[8:].decode("utf-16-be", errors="ignore").strip("\x00 ")
                        elif value.startswith(b"ASCII\x00\x00\x00"):
                            decoded = value[8:].decode("ascii", errors="ignore").strip("\x00 ")
                        if decoded and _is_valid_ai_text(decoded):
                            dhash = compute_dhash(img)
                            if "Steps:" in decoded or "Negative prompt:" in decoded:
                                pos, neg, raw, model_name, loras = _split_a1111_parameters(decoded)
                                return True, pos, neg, raw, model_name, ",".join(loras), dhash
                            return True, decoded, "", decoded, "", "", dhash
    except Exception:
        pass
    return False, "", "", "", "", "", ""


# ==========================================
# 2. データベース管理 (SQLite + FTS5 + 明示的id主キー移行)
# ==========================================
class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
        conn.execute("PRAGMA temp_store=MEMORY")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            cur = conn.cursor()

            # 既存テーブルのカラム構成を確認し、id主キー未導入DBなら安全に移行する
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='images'")
            table_exists = cur.fetchone() is not None

            if table_exists:
                cur.execute("PRAGMA table_info(images)")
                cols_info = {row[1]: row for row in cur.fetchall()}
                if "id" not in cols_info:
                    # 旧スキーマ (path TEXT PRIMARY KEY) から id INTEGER PRIMARY KEY AUTOINCREMENT へ移行
                    cur.execute("ALTER TABLE images RENAME TO images_legacy")
                    self._create_images_table(cur)
                    legacy_cols = set(cols_info.keys())
                    sel_rating = "rating" if "rating" in legacy_cols else "CASE WHEN favorite = 1 THEN 5 ELSE 0 END"
                    sel_model = "COALESCE(model, '')" if "model" in legacy_cols else "''"
                    sel_loras = "COALESCE(loras, '')" if "loras" in legacy_cols else "''"
                    sel_dhash = "COALESCE(dhash, '')" if "dhash" in legacy_cols else "''"
                    cur.execute(f"""
                        INSERT INTO images (path, mtime, positive, negative, raw_meta, favorite, rating, model, loras, dhash)
                        SELECT path, mtime, positive, negative, raw_meta, favorite, {sel_rating}, {sel_model}, {sel_loras}, {sel_dhash}
                        FROM images_legacy
                    """)
                    cur.execute("DROP TABLE images_legacy")
                    # FTS5テーブルも新しい id と完全に一致するよう再構築
                    cur.execute("DROP TABLE IF EXISTS images_fts")
                    self._create_fts_table(cur)
                    cur.execute("SELECT id, path, positive, negative FROM images")
                    for img_id, path, pos, neg in cur.fetchall():
                        cur.execute(
                            "INSERT INTO images_fts (rowid, path, norm_positive, norm_negative) VALUES (?, ?, ?, ?)",
                            (img_id, path, normalize_prompt(pos or ""), normalize_prompt(neg or ""))
                        )
                else:
                    self._create_fts_table(cur)
            else:
                self._create_images_table(cur)
                self._create_fts_table(cur)

            # 旧favorite=1のレコードでrating=0のものを互換補正
            cur.execute("UPDATE images SET rating = 5 WHERE favorite = 1 AND (rating IS NULL OR rating = 0)")

            # 高速絞り込み・ソート用インデックス
            cur.execute("CREATE INDEX IF NOT EXISTS idx_images_mtime ON images(mtime DESC)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_images_model ON images(model)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_images_rating ON images(rating DESC, mtime DESC)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS ignored_files (
                    path TEXT PRIMARY KEY,
                    mtime REAL
                )
            """)
            conn.commit()

    def _create_images_table(self, cur: sqlite3.Cursor):
        cur.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                mtime REAL,
                positive TEXT,
                negative TEXT,
                raw_meta TEXT,
                favorite INTEGER DEFAULT 0,
                rating INTEGER DEFAULT 0,
                model TEXT DEFAULT '',
                loras TEXT DEFAULT '',
                dhash TEXT DEFAULT ''
            )
        """)

    def _create_fts_table(self, cur: sqlite3.Cursor):
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS images_fts USING fts5(
                path UNINDEXED,
                norm_positive,
                norm_negative
            )
        """)

    def get_duplicate_candidates(self) -> list[dict]:
        """Read only indexed image locations; file content is checked on disk."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(
                "SELECT path, mtime, rating, model, loras FROM images ORDER BY path"
            ).fetchall()]

    def get_image_detail(self, path: str) -> dict | None:
        """右パネル表示用に1件の詳細メタデータのみを取得する"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM images WHERE path = ?", (path,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_existing_mtimes(self) -> dict[str, float]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT path, mtime FROM images")
            return dict(cur.fetchall())

    def get_ignored_mtimes(self) -> dict[str, float]:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("SELECT path, mtime FROM ignored_files")
            return dict(cur.fetchall())

    def upsert_ignored(self, records: list[tuple[str, float]]):
        if not records:
            return
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executemany("""
                INSERT INTO ignored_files (path, mtime)
                VALUES (?, ?)
                ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime
            """, records)
            conn.commit()

    def delete_ignored_paths(self, paths: list[str]):
        if not paths:
            return
        with self._connect() as conn:
            cur = conn.cursor()
            cur.executemany("DELETE FROM ignored_files WHERE path = ?", [(p,) for p in paths])
            conn.commit()

    def upsert_images(self, records: list[tuple]):
        """records: [(path, mtime, positive, negative, raw_meta, model, loras, dhash), ...]"""
        if not records:
            return
        with self._connect() as conn:
            cur = conn.cursor()
            for path, mtime, pos, neg, raw, model, loras, dhash in records:
                cur.execute("SELECT id FROM images WHERE path = ?", (path,))
                old_row = cur.fetchone()
                if old_row:
                    cur.execute("DELETE FROM images_fts WHERE rowid = ?", (old_row[0],))

                cur.execute("""
                    INSERT INTO images (path, mtime, positive, negative, raw_meta, favorite, rating, model, loras, dhash)
                    VALUES (
                        ?, ?, ?, ?, ?,
                        COALESCE((SELECT favorite FROM images WHERE path = ?), 0),
                        COALESCE((SELECT rating FROM images WHERE path = ?), 0),
                        ?, ?, ?
                    )
                    ON CONFLICT(path) DO UPDATE SET
                        mtime=excluded.mtime,
                        positive=excluded.positive,
                        negative=excluded.negative,
                        raw_meta=excluded.raw_meta,
                        model=excluded.model,
                        loras=excluded.loras,
                        dhash=excluded.dhash
                """, (path, mtime, pos, neg, raw, path, path, model, loras, dhash))

                cur.execute("SELECT id FROM images WHERE path = ?", (path,))
                new_row = cur.fetchone()
                if new_row:
                    norm_pos = normalize_prompt(pos)
                    norm_neg = normalize_prompt(neg)
                    cur.execute(
                        "INSERT INTO images_fts (rowid, path, norm_positive, norm_negative) VALUES (?, ?, ?, ?)",
                        (new_row[0], path, norm_pos, norm_neg)
                    )
                cur.execute("DELETE FROM ignored_files WHERE path = ?", (path,))
            conn.commit()

    def delete_paths(self, paths: list[str]):
        if not paths:
            return
        with self._connect() as conn:
            cur = conn.cursor()
            for p in paths:
                cur.execute("SELECT id FROM images WHERE path = ?", (p,))
                r = cur.fetchone()
                if r:
                    cur.execute("DELETE FROM images_fts WHERE rowid = ?", (r[0],))
            cur.executemany("DELETE FROM images WHERE path = ?", [(p,) for p in paths])
            conn.commit()

    def set_rating(self, path: str, rating: int) -> int:
        rating = max(0, min(5, int(rating)))
        fav_flag = 1 if rating > 0 else 0
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE images SET rating = ?, favorite = ? WHERE path = ?", (rating, fav_flag, path))
            conn.commit()
        return rating

    def get_filter_options(self) -> tuple[list[str], list[str]]:
        """DBに存在するモデル一覧とLoRA一覧を件数順で返す"""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT model, COUNT(*) as cnt FROM images
                WHERE model IS NOT NULL AND model != ''
                GROUP BY model ORDER BY cnt DESC
            """)
            models = [r[0] for r in cur.fetchall()]

            cur.execute("SELECT loras FROM images WHERE loras IS NOT NULL AND loras != ''")
            lora_counter: Counter = Counter()
            for (loras_str,) in cur.fetchall():
                for item in loras_str.split(","):
                    item = item.strip()
                    if item:
                        lora_counter[item] += 1
            loras = [name for name, _ in lora_counter.most_common()]
            return models, loras

    def search(
        self,
        query: str,
        include_negative: bool = False,
        min_rating: int = 0,
        expand_similar: bool = False,
        model_filter: str = "",
        lora_filter: str = "",
        sort_by: str = "mtime_desc"
    ) -> tuple[list[dict], str]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            inc_groups, exc_groups, display_info = build_search_groups(query, expand_similar)

            extra_where = []
            extra_params: list = []

            if min_rating > 0:
                extra_where.append("i.rating >= ?")
                extra_params.append(min_rating)
            if model_filter:
                extra_where.append("i.model = ?")
                extra_params.append(model_filter)
            if lora_filter:
                extra_where.append("(',' || i.loras || ',') LIKE ?")
                extra_params.append(f"%,{lora_filter},%")

            order_map = {
                "mtime_desc": "i.mtime DESC",
                "mtime_asc": "i.mtime ASC",
                "rating_desc": "i.rating DESC, i.mtime DESC",
                "name_asc": "i.path ASC",
            }
            order_sql = order_map.get(sort_by, "i.mtime DESC")

            if not inc_groups and not exc_groups:
                where_clause = ("WHERE " + " AND ".join(extra_where)) if extra_where else ""
                cur.execute(f"""
                    SELECT i.id, i.path, i.rating, i.model, i.loras
                    FROM images i
                    {where_clause}
                    ORDER BY {order_sql}
                """, extra_params)
                rows = [dict(r) for r in cur.fetchall()]
                return rows, display_info

            if not inc_groups:
                where_clause = ("WHERE " + " AND ".join(extra_where)) if extra_where else ""
                cur.execute(f"""
                    SELECT i.id, i.path, i.rating, i.model, i.loras, f.norm_positive, f.norm_negative
                    FROM images i
                    LEFT JOIN images_fts f ON i.id = f.rowid
                    {where_clause}
                    ORDER BY {order_sql}
                """, extra_params)
                rows = [dict(r) for r in cur.fetchall()]
            else:
                and_clauses = []
                for opts in inc_groups:
                    or_parts = []
                    for opt in opts:
                        safe_opt = opt.replace('"', "")
                        if not safe_opt:
                            continue
                        if expand_similar and " " not in safe_opt and len(safe_opt) >= 4:
                            or_parts.append(f'"{safe_opt}"*')
                        else:
                            or_parts.append(f'"{safe_opt}"')
                    if or_parts:
                        and_clauses.append("(" + " OR ".join(or_parts) + ")")

                fts_expr = " AND ".join(and_clauses)
                col_filter = "{norm_positive norm_negative}" if include_negative else "norm_positive"
                all_where = ["images_fts MATCH ?"] + extra_where
                all_params = [f"{col_filter} : ({fts_expr})"] + extra_params
                select_cols = (
                    "i.id, i.path, i.rating, i.model, i.loras, f.norm_positive, f.norm_negative"
                    if exc_groups else
                    "i.id, i.path, i.rating, i.model, i.loras"
                )
                try:
                    cur.execute(f"""
                        SELECT {select_cols}
                        FROM images i
                        JOIN images_fts f ON i.id = f.rowid
                        WHERE {' AND '.join(all_where)}
                        ORDER BY {order_sql}
                    """, all_params)
                    rows = [dict(r) for r in cur.fetchall()]
                except sqlite3.OperationalError:
                    sql_conds = []
                    like_params = []
                    for opts in inc_groups:
                        sub_conds = []
                        for opt in opts:
                            like_q = f"%{opt}%"
                            if include_negative:
                                sub_conds.append("(f.norm_positive LIKE ? OR f.norm_negative LIKE ?)")
                                like_params.extend([like_q, like_q])
                            else:
                                sub_conds.append("f.norm_positive LIKE ?")
                                like_params.append(like_q)
                        if sub_conds:
                            sql_conds.append("(" + " OR ".join(sub_conds) + ")")
                    fb_where = sql_conds + extra_where
                    fb_params = like_params + extra_params
                    cur.execute(f"""
                        SELECT {select_cols}
                        FROM images i
                        JOIN images_fts f ON i.id = f.rowid
                        WHERE {' AND '.join(fb_where) if fb_where else '1=1'}
                        ORDER BY {order_sql}
                    """, fb_params)
                    rows = [dict(r) for r in cur.fetchall()]

            # マイナス検索（除外ワード）フィルタリング
            if exc_groups and rows:
                filtered_rows = []
                for r in rows:
                    target_text = (r.get("norm_positive") or "")
                    if include_negative:
                        target_text += " " + (r.get("norm_negative") or "")
                    padded = f" {target_text} "
                    excluded = False
                    for opts in exc_groups:
                        if any(f" {opt} " in padded or opt in target_text for opt in opts):
                            excluded = True
                            break
                    if not excluded:
                        r.pop("norm_positive", None)
                        r.pop("norm_negative", None)
                        filtered_rows.append(r)
                rows = filtered_rows

            return rows, display_info

    def find_similar_prompt(self, target_path: str, min_rating: int = 0, limit: int = 300) -> list[dict]:
        """
        2段階高速類似検索:
        1) 基準画像の主要タグでFTS5から候補（最大3,000件）を高速抽出
        2) 候補群に対してコサイン類似度を計算し上位をランキング返却
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()

            cur.execute("""
                SELECT i.id, i.path, i.rating, i.model, i.loras, f.norm_positive
                FROM images i
                JOIN images_fts f ON i.id = f.rowid
                WHERE i.path = ?
            """, (target_path,))
            t_row = cur.fetchone()
            if not t_row:
                return []
            target_row = dict(t_row)

            target_tokens = [t for t in (target_row.get("norm_positive") or "").split() if len(t) > 1]
            if not target_tokens:
                return []

            target_vec = Counter(target_tokens)
            target_norm = math.sqrt(sum(v * v for v in target_vec.values()))
            if target_norm == 0:
                return []

            # 品質タグなどの汎用すぎる語を除いた特徴的な上位タグで候補を絞る
            generic_tags = {"masterpiece", "best_quality", "high_quality", "absurdres", "highres"}
            distinctive = [t for t, _ in target_vec.most_common() if t not in generic_tags]
            seed_tags = (distinctive[:8] or [t for t, _ in target_vec.most_common(8)])

            rows: list[dict] = []
            if seed_tags:
                or_expr = " OR ".join(f'"{t.replace(chr(34), "")}"' for t in seed_tags if t)
                rating_sql = "AND i.rating >= ?" if min_rating > 0 else ""
                params: list = [f"norm_positive : ({or_expr})"]
                if min_rating > 0:
                    params.append(min_rating)
                try:
                    cur.execute(f"""
                        SELECT i.id, i.path, i.rating, i.model, i.loras, f.norm_positive
                        FROM images i
                        JOIN images_fts f ON i.id = f.rowid
                        WHERE images_fts MATCH ? {rating_sql}
                        LIMIT 3000
                    """, params)
                    rows = [dict(r) for r in cur.fetchall()]
                except sqlite3.OperationalError:
                    rows = []

            # 候補が極端に少ない場合のみ全件から取得
            if len(rows) < 20:
                rating_clause = "WHERE i.rating >= ?" if min_rating > 0 else ""
                fb_params = [min_rating] if min_rating > 0 else []
                cur.execute(f"""
                    SELECT i.id, i.path, i.rating, i.model, i.loras, f.norm_positive
                    FROM images i
                    JOIN images_fts f ON i.id = f.rowid
                    {rating_clause}
                """, fb_params)
                rows = [dict(r) for r in cur.fetchall()]

        if not any(r["path"] == target_path for r in rows):
            rows.append(target_row)

        scored: list[tuple[float, dict]] = []
        for r in rows:
            if r["path"] == target_path:
                r_copy = {k: v for k, v in r.items() if k != "norm_positive"}
                r_copy["similarity"] = 100
                scored.append((1.01, r_copy))
                continue

            tokens = [t for t in (r.get("norm_positive") or "").split() if len(t) > 1]
            if not tokens:
                continue
            vec = Counter(tokens)
            dot = sum(target_vec[k] * vec[k] for k in target_vec if k in vec)
            if dot == 0:
                continue
            norm = math.sqrt(sum(v * v for v in vec.values()))
            if norm == 0:
                continue
            sim = dot / (target_norm * norm)
            if sim >= 0.15:
                r_copy = {k: v for k, v in r.items() if k != "norm_positive"}
                r_copy["similarity"] = min(99, int(round(sim * 100)))
                scored.append((sim, r_copy))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    def find_similar_visual(self, target_path: str, min_rating: int = 0, limit: int = 300) -> list[dict]:
        """選択された画像と見た目（dHashハミング距離）が似ている順にランキング取得する"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rating_clause = "WHERE rating >= ?" if min_rating > 0 else ""
            params = [min_rating] if min_rating > 0 else []
            cur.execute(f"SELECT id, path, rating, model, loras, dhash FROM images {rating_clause}", params)
            rows = [dict(r) for r in cur.fetchall()]

        target_row = next((r for r in rows if r["path"] == target_path), None)
        if not target_row:
            return []

        target_hash = target_row.get("dhash") or ""
        if not target_hash and os.path.exists(target_path):
            try:
                with Image.open(target_path) as img:
                    target_hash = compute_dhash(img)
            except Exception:
                pass
        if not target_hash:
            return []

        scored: list[tuple[int, dict]] = []
        for r in rows:
            if r["path"] == target_path:
                r_copy = {k: v for k, v in r.items() if k != "dhash"}
                r_copy["similarity"] = 100
                scored.append((-1, r_copy))
                continue
            h = r.get("dhash") or ""
            if not h:
                continue
            dist = hamming_distance_hex(target_hash, h)
            if dist <= 24:
                pct = max(1, min(99, int(round((1.0 - dist / 64.0) * 100))))
                r_copy = {k: v for k, v in r.items() if k != "dhash"}
                r_copy["similarity"] = pct
                scored.append((dist, r_copy))

        scored.sort(key=lambda x: x[0])
        return [item for _, item in scored[:limit]]


# ==========================================
# 3. 非同期サムネイル生成 (LIFO優先制御) & ドラッグ対応仮想化ビュー
# ==========================================
class ThumbnailSignals(QObject):
    loaded = Signal(str, QImage)


class ThumbnailTask(QRunnable):
    def __init__(self, path: str, size: int, signals: ThumbnailSignals):
        super().__init__()
        self.path = path
        self.size = size
        self.signals = signals

    def run(self):
        if not os.path.exists(self.path):
            return
        img = QImage(self.path)
        if not img.isNull():
            scaled = img.scaled(
                self.size, self.size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.signals.loaded.emit(self.path, scaled)


class ImageGridModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[dict] = []
        self.path_to_row: dict[str, int] = {}
        self.cache: OrderedDict[str, QPixmap] = OrderedDict()
        self.max_cache = 1500
        self.pending: set[str] = set()
        self._priority_counter = 0

        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(min(8, os.cpu_count() or 4))

        self.signals = ThumbnailSignals()
        self.signals.loaded.connect(self._on_thumb_loaded)

        placeholder = QImage(THUMB_SIZE, THUMB_SIZE, QImage.Format_RGB32)
        placeholder.fill(QColor("#252932"))
        self.placeholder_pixmap = QPixmap.fromImage(placeholder)

    def set_items(self, items: list[dict]):
        self.beginResetModel()
        self.items = items
        self.path_to_row = {row["path"]: idx for idx, row in enumerate(items)}
        self.pending.clear()
        self._priority_counter = 0
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.items)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.items)):
            return None

        row_data = self.items[index.row()]
        path = row_data["path"]

        if role == Qt.DisplayRole:
            sim_prefix = f"[{row_data['similarity']}%] " if "similarity" in row_data else ""
            if "_duplicate_keep" in row_data:
                sim_prefix = "[残す・最新] " if row_data["_duplicate_keep"] else "[古い重複] "
            rating = row_data.get("rating") or 0
            star_prefix = f"{'★' * rating} " if rating > 0 else ""
            return f"{sim_prefix}{star_prefix}{os.path.basename(path)}"

        if role == Qt.DecorationRole:
            if path in self.cache:
                self.cache.move_to_end(path)
                return self.cache[path]

            if path not in self.pending:
                self.pending.add(path)
                # 後から表示要求された（現在画面に見えている）サムネイルほど高優先度(LIFO)で実行
                self._priority_counter += 1
                task = ThumbnailTask(path, THUMB_SIZE, self.signals)
                self.pool.start(task, self._priority_counter)
            return self.placeholder_pixmap

        if role == Qt.UserRole:
            return row_data

        return None

    def _on_thumb_loaded(self, path: str, qimg: QImage):
        self.pending.discard(path)
        pix = QPixmap.fromImage(qimg)
        self.cache[path] = pix
        if len(self.cache) > self.max_cache:
            self.cache.popitem(last=False)

        row = self.path_to_row.get(path)
        if row is not None:
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.DecorationRole])

    def update_rating_at(self, row: int, new_rating: int):
        if 0 <= row < len(self.items):
            self.items[row]["rating"] = new_rating
            self.items[row]["favorite"] = 1 if new_rating > 0 else 0
            idx = self.index(row, 0)
            self.dataChanged.emit(idx, idx, [Qt.DisplayRole])

    def remove_paths(self, paths_set: set[str]):
        for p in paths_set:
            self.cache.pop(p, None)
            self.pending.discard(p)
        remaining = [item for item in self.items if item["path"] not in paths_set]
        self.set_items(remaining)


class DraggableImageListView(QListView):
    """ブラウザ（ComfyUI/WebUI）やエクスプローラーへ直接ファイルをドラッグ＆ドロップできるQListView"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)

    def startDrag(self, supportedActions):
        indexes = self.selectionModel().selectedIndexes()
        rows = sorted({idx.row() for idx in indexes})
        if not rows:
            return
        model = self.model()
        urls = []
        for r in rows:
            path = model.items[r]["path"]
            if os.path.exists(path):
                urls.append(QUrl.fromLocalFile(os.path.normpath(path)))
        if not urls:
            return

        mime = QMimeData()
        mime.setUrls(urls)

        drag = QDrag(self)
        drag.setMimeData(mime)
        first_path = model.items[rows[0]]["path"]
        if first_path in model.cache:
            drag.setPixmap(model.cache[first_path].scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.exec(Qt.CopyAction)


# ==========================================
# 4. バックグラウンドスキャナー & バックグラウンド検索ワーカー
# ==========================================
class SearchWorker(QThread):
    """大量データでもメインUIを絶対に固まらせない非同期検索ワーカー"""
    search_finished = Signal(int, list, str, str)

    def __init__(
        self,
        seq_id: int,
        db: DatabaseManager,
        mode: str,
        params: dict
    ):
        super().__init__()
        self.seq_id = seq_id
        self.db = db
        self.mode = mode
        self.params = params

    def run(self):
        try:
            if self.mode == "normal":
                results, display_info = self.db.search(**self.params)
                self.search_finished.emit(self.seq_id, results, display_info, self.mode)
            elif self.mode == "similar_prompt":
                results = self.db.find_similar_prompt(
                    self.params["target_path"],
                    min_rating=self.params["min_rating"]
                )
                self.search_finished.emit(
                    self.seq_id,
                    results,
                    os.path.basename(self.params["target_path"]),
                    self.mode
                )
            elif self.mode == "similar_visual":
                results = self.db.find_similar_visual(
                    self.params["target_path"],
                    min_rating=self.params["min_rating"]
                )
                self.search_finished.emit(
                    self.seq_id,
                    results,
                    os.path.basename(self.params["target_path"]),
                    self.mode
                )
        except Exception:
            self.search_finished.emit(self.seq_id, [], "", self.mode)


class FilterOptionsWorker(QThread):
    """モデル・LoRA一覧の集計をバックグラウンドで実行するワーカー"""
    options_loaded = Signal(list, list)

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

    def run(self):
        try:
            models, loras = self.db.get_filter_options()
            self.options_loaded.emit(models, loras)
        except Exception:
            self.options_loaded.emit([], [])


class ScanWorker(QThread):
    progress = Signal(int, int)
    finished_scan = Signal(int, int, int)

    def __init__(
        self,
        root_dir: str,
        exclude_keywords: list[str],
        db: DatabaseManager,
        force_rescan: bool = False
    ):
        super().__init__()
        self.root_dir = root_dir
        self.exclude_keywords = [k.strip().lower() for k in exclude_keywords if k.strip()]
        self.db = db
        self.force_rescan = force_rescan

    def _is_excluded_name(self, name: str) -> bool:
        low = name.lower()
        return any(kw in low for kw in self.exclude_keywords)

    def _scandir_recursive(self, base_dir: str, existing: dict, ignored: dict, found_paths: set, to_process: list):
        """Windowsで高速に大量ファイルを走査するos.scandir再帰処理"""
        try:
            with os.scandir(base_dir) as it:
                for entry in it:
                    name = entry.name
                    if entry.is_dir(follow_symlinks=False):
                        if not self._is_excluded_name(name):
                            self._scandir_recursive(entry.path, existing, ignored, found_paths, to_process)
                    elif entry.is_file(follow_symlinks=False):
                        ext = os.path.splitext(name)[1].lower()
                        if ext not in IMAGE_EXTS:
                            continue
                        str_p = entry.path
                        found_paths.add(str_p)
                        try:
                            mtime = entry.stat(follow_symlinks=False).st_mtime
                        except OSError:
                            continue
                        if not self.force_rescan:
                            if str_p in existing and existing[str_p] == mtime:
                                continue
                            if str_p in ignored and ignored[str_p] == mtime:
                                continue
                        to_process.append((str_p, mtime))
        except OSError:
            pass

    def run(self):
        existing = self.db.get_existing_mtimes()
        ignored = self.db.get_ignored_mtimes()
        found_paths = set()
        to_process = []

        if not self._is_excluded_name(os.path.basename(self.root_dir)):
            self._scandir_recursive(self.root_dir, existing, ignored, found_paths, to_process)

        stale_paths = [p for p in existing.keys() if p not in found_paths]
        if stale_paths:
            self.db.delete_paths(stale_paths)

        stale_ignored = [p for p in ignored.keys() if p not in found_paths]
        if stale_ignored:
            self.db.delete_ignored_paths(stale_ignored)

        total = len(to_process)
        ai_records = []
        non_ai_records = []

        if total > 0:
            def worker(item):
                path, mtime = item
                is_ai, pos, neg, raw, model, loras, dhash = parse_image_metadata(path)
                return (is_ai, path, mtime, pos, neg, raw, model, loras, dhash)

            with ThreadPoolExecutor(max_workers=8) as executor:
                for idx, res in enumerate(executor.map(worker, to_process), 1):
                    is_ai, path, mtime, pos, neg, raw, model, loras, dhash = res
                    if is_ai:
                        ai_records.append((path, mtime, pos, neg, raw, model, loras, dhash))
                    else:
                        non_ai_records.append((path, mtime))
                    if idx % 50 == 0 or idx == total:
                        self.progress.emit(idx, total)

            if ai_records:
                self.db.upsert_images(ai_records)
            if non_ai_records:
                self.db.upsert_ignored(non_ai_records)
                # 強制再スキャン時に非AIと判定されたファイルが旧imagesに残っていれば除去
                if self.force_rescan:
                    reclassified_non_ai = [p for p, _ in non_ai_records if p in existing]
                    if reclassified_non_ai:
                        self.db.delete_paths(reclassified_non_ai)

        self.finished_scan.emit(len(ai_records), len(stale_paths), len(non_ai_records))


# ==========================================
# 5. メインGUIウィンドウ
# ==========================================
def sha256_file(path: str) -> str:
    """Stream the entire file without loading large images into memory."""
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class DuplicateWorker(QThread):
    duplicates_found = Signal(list, dict, int)

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db

    def run(self):
        # Size prefilter dramatically reduces disk I/O on large collections.
        from collections import defaultdict
        by_size = defaultdict(list)
        for row in self.db.get_duplicate_candidates():
            path = row["path"]
            try:
                if os.path.isfile(path) and not os.path.islink(path):
                    size = os.path.getsize(path)
                    by_size[size].append(row)
            except OSError:
                continue
        groups = defaultdict(list)
        errors = 0
        for size, rows in by_size.items():
            if len(rows) < 2:
                continue
            for row in rows:
                try:
                    path = row["path"]
                    # Detect files modified during reading.
                    before = os.stat(path)
                    if before.st_size != size:
                        continue
                    digest = sha256_file(path)
                    after = os.stat(path)
                    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                        continue
                    item = dict(row)
                    item["mtime"] = after.st_mtime
                    item["_sha256"] = digest
                    item["_size"] = size
                    groups[(size, digest)].append(item)
                except (OSError, PermissionError):
                    errors += 1
        duplicates = []
        keep_by_path = {}
        for key, rows in groups.items():
            if len(rows) < 2:
                continue
            # Preserve most recently modified file (tie: deterministic path).
            rows.sort(key=lambda r: (-r["mtime"], r["path"].casefold()))
            keeper = rows[0]
            for row in rows:
                row["_duplicate_keep"] = (row["path"] == keeper["path"])
                if row["path"] != keeper["path"]:
                    keep_by_path[row["path"]] = (keeper["path"], key[0], key[1])
            duplicates.extend(rows)
        self.duplicates_found.emit(duplicates, keep_by_path, errors)


class PromptFinderWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI生成画像プロンプト検索ツール (Pro Edition)")
        self.db = DatabaseManager()
        self.model = ImageGridModel(self)
        self.search_seq = 0
        self._active_workers: list[QThread] = []
        self._current_detail_row: dict | None = None
        self._duplicate_keep_by_path: dict[str, tuple[str, int, str]] = {}
        self._duplicate_mode = False

        self._build_ui()
        self._setup_shortcuts()
        self._load_config()

        # ウィンドウ表示をブロックしないよう遅延初期化
        QTimer.singleShot(0, self._initial_load)

    def _initial_load(self):
        self._refresh_filter_combos()
        self.perform_search()

    def _track_worker(self, worker: QThread):
        self._active_workers.append(worker)
        worker.finished.connect(lambda: self._cleanup_worker(worker))

    def _cleanup_worker(self, worker: QThread):
        if worker in self._active_workers:
            self._active_workers.remove(worker)
        worker.deleteLater()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 8)
        main_layout.setSpacing(8)

        # --- 1段目: フォルダ指定 & スキャン ---
        top_bar = QHBoxLayout()
        top_bar.setSpacing(6)
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("画像が保存されているルートフォルダを選択...")
        btn_browse = QPushButton("フォルダ選択")
        btn_browse.clicked.connect(self.select_folder)

        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("除外フォルダ (例: grids, extras, temp)")

        self.chk_force_rescan = QCheckBox("強制再抽出")
        self.chk_force_rescan.setToolTip("チェックを入れると更新日時が変わっていない既存画像もすべて再解析します")

        self.btn_scan = QPushButton("スキャン / 更新")
        self.btn_scan.setObjectName("PrimaryBtn")
        self.btn_scan.clicked.connect(self.start_scan)

        top_bar.addWidget(QLabel("フォルダ:"))
        top_bar.addWidget(self.dir_input, 3)
        top_bar.addWidget(btn_browse)
        top_bar.addWidget(QLabel("除外:"))
        top_bar.addWidget(self.exclude_input, 2)
        top_bar.addWidget(self.chk_force_rescan)
        top_bar.addWidget(self.btn_scan)
        main_layout.addLayout(top_bar)

        # --- 2段目: プロンプト検索バー（日本語翻訳・マイナス検索・類似拡張） ---
        search_bar = QHBoxLayout()
        search_bar.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "検索ワード (例: 女の子 青い目 -monochrome) ※日本語自動翻訳・重み無視・マイナス除外対応"
        )
        self.search_input.returnPressed.connect(self.perform_search)

        self.chk_similar_expand = QCheckBox("表記ゆれ・類義拡張")
        self.chk_similar_expand.stateChanged.connect(self.perform_search)

        self.chk_negative = QCheckBox("ネガティブも検索")
        self.chk_negative.stateChanged.connect(self.perform_search)

        btn_search = QPushButton("検索")
        btn_search.setObjectName("PrimaryBtn")
        btn_search.clicked.connect(self.perform_search)

        btn_reset = QPushButton("クリア")
        btn_reset.clicked.connect(self.reset_filters)

        search_bar.addWidget(self.search_input, 4)
        search_bar.addWidget(self.chk_similar_expand)
        search_bar.addWidget(self.chk_negative)
        search_bar.addWidget(btn_search)
        search_bar.addWidget(btn_reset)
        main_layout.addLayout(search_bar)

        # --- 3段目: モデル / LoRA / 評価 / ソート フィルタバー ---
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(6)

        self.combo_model = QComboBox()
        self.combo_model.setMinimumWidth(180)
        self.combo_model.currentIndexChanged.connect(self.perform_search)

        self.combo_lora = QComboBox()
        self.combo_lora.setMinimumWidth(180)
        self.combo_lora.currentIndexChanged.connect(self.perform_search)

        self.combo_rating = QComboBox()
        self.combo_rating.addItem("評価: すべて", 0)
        self.combo_rating.addItem("★1 以上", 1)
        self.combo_rating.addItem("★★2 以上", 2)
        self.combo_rating.addItem("★★★3 以上", 3)
        self.combo_rating.addItem("★★★★4 以上", 4)
        self.combo_rating.addItem("★★★★★5 のみ", 5)
        self.combo_rating.currentIndexChanged.connect(self.perform_search)

        self.combo_sort = QComboBox()
        self.combo_sort.addItem("並び順: 新しい順", "mtime_desc")
        self.combo_sort.addItem("並び順: 古い順", "mtime_asc")
        self.combo_sort.addItem("並び順: 評価が高い順", "rating_desc")
        self.combo_sort.addItem("並び順: パス名順", "name_asc")
        self.combo_sort.currentIndexChanged.connect(self.perform_search)

        filter_bar.addWidget(QLabel("モデル:"))
        filter_bar.addWidget(self.combo_model, 2)
        filter_bar.addWidget(QLabel("LoRA:"))
        filter_bar.addWidget(self.combo_lora, 2)
        filter_bar.addWidget(self.combo_rating, 1)
        filter_bar.addWidget(self.combo_sort, 1)
        main_layout.addLayout(filter_bar)

        duplicate_bar = QHBoxLayout()
        self.btn_find_duplicates = QPushButton("重複画像を検索（完全一致）")
        self.btn_find_duplicates.clicked.connect(self.find_duplicates)
        self.btn_select_old_duplicates = QPushButton("古い重複を一括選択")
        self.btn_select_old_duplicates.setEnabled(False)
        self.btn_select_old_duplicates.clicked.connect(self.select_old_duplicates)
        self.btn_delete_duplicates = QPushButton("選択した重複をゴミ箱へ")
        self.btn_delete_duplicates.setObjectName("DangerBtn")
        self.btn_delete_duplicates.setEnabled(False)
        self.btn_delete_duplicates.clicked.connect(self.delete_selected_images)
        duplicate_bar.addWidget(self.btn_find_duplicates)
        duplicate_bar.addWidget(self.btn_select_old_duplicates)
        duplicate_bar.addWidget(self.btn_delete_duplicates)
        duplicate_bar.addStretch()
        main_layout.addLayout(duplicate_bar)

        # --- プログレスバー ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # --- メイン分割領域 ---
        self.splitter = QSplitter(Qt.Horizontal)

        # 左ペイン: ドラッグ＆ドロップ対応 バッチ仮想化サムネイルビュー
        self.list_view = DraggableImageListView()
        self.list_view.setModel(self.model)
        self.list_view.setViewMode(QListView.IconMode)
        self.list_view.setIconSize(QSize(THUMB_SIZE, THUMB_SIZE))
        self.list_view.setGridSize(QSize(THUMB_SIZE + 24, THUMB_SIZE + 44))
        self.list_view.setResizeMode(QListView.Adjust)
        self.list_view.setLayoutMode(QListView.Batched)
        self.list_view.setBatchSize(200)
        self.list_view.setUniformItemSizes(True)
        self.list_view.setWordWrap(True)
        self.list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_view.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_view.customContextMenuRequested.connect(self.show_context_menu)
        self.splitter.addWidget(self.list_view)

        # 右ペイン: プレビュー & メタデータバッジ & アクション操作
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(6)

        self.preview_label = QLabel("画像を選択するとプレビューとプロンプトが表示されます\n（キー操作: 1〜5で評価 / Deleteでゴミ箱 / D&Dで外部へ渡せます）")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(250)
        self.preview_label.setStyleSheet(
            "background-color: #121418; color: #8b949e; border: 1px solid #2c313c; border-radius: 8px;"
        )
        right_layout.addWidget(self.preview_label)

        # メタデータ情報バッジ（モデル / LoRA / 評価）
        self.meta_badge_label = QLabel("モデル: - ｜ LoRA: - ｜ 評価: 未設定")
        self.meta_badge_label.setObjectName("BadgeLabel")
        self.meta_badge_label.setWordWrap(True)
        right_layout.addWidget(self.meta_badge_label)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color: #9ca3af; font-size: 12px;")
        right_layout.addWidget(self.path_label)

        # アクションボタン1段目（類似検索 & 評価）
        sim_bar = QHBoxLayout()
        sim_bar.setSpacing(5)
        btn_sim_prompt = QPushButton("類似プロンプト検索")
        btn_sim_prompt.setObjectName("PrimaryBtn")
        btn_sim_prompt.clicked.connect(self.search_similar_prompt)

        btn_sim_visual = QPushButton("見た目類似検索 (dHash)")
        btn_sim_visual.setObjectName("AccentBtn")
        btn_sim_visual.clicked.connect(self.search_similar_visual)

        self.combo_set_rating = QComboBox()
        self.combo_set_rating.addItem("評価変更...", -1)
        self.combo_set_rating.addItem("評価なし (0)", 0)
        self.combo_set_rating.addItem("★ (1)", 1)
        self.combo_set_rating.addItem("★★ (2)", 2)
        self.combo_set_rating.addItem("★★★ (3)", 3)
        self.combo_set_rating.addItem("★★★★ (4)", 4)
        self.combo_set_rating.addItem("★★★★★ (5)", 5)
        self.combo_set_rating.currentIndexChanged.connect(self.on_rating_combo_changed)

        sim_bar.addWidget(btn_sim_prompt, 2)
        sim_bar.addWidget(btn_sim_visual, 2)
        sim_bar.addWidget(self.combo_set_rating, 1)
        right_layout.addLayout(sim_bar)

        # アクションボタン2段目（各種コピー & ファイル操作）
        action_bar = QHBoxLayout()
        action_bar.setSpacing(5)
        btn_copy_pos = QPushButton("ポジティブコピー")
        btn_copy_pos.clicked.connect(self.copy_positive)

        btn_copy_neg = QPushButton("ネガティブコピー")
        btn_copy_neg.clicked.connect(self.copy_negative)

        btn_copy_all = QPushButton("全パラメータコピー")
        btn_copy_all.clicked.connect(self.copy_raw_meta)

        btn_open_dir = QPushButton("場所を開く")
        btn_open_dir.clicked.connect(self.open_in_explorer)

        btn_delete = QPushButton("ゴミ箱")
        btn_delete.setObjectName("DangerBtn")
        btn_delete.clicked.connect(self.delete_selected_images)

        action_bar.addWidget(btn_copy_pos)
        action_bar.addWidget(btn_copy_neg)
        action_bar.addWidget(btn_copy_all)
        action_bar.addWidget(btn_open_dir)
        action_bar.addWidget(btn_delete)
        right_layout.addLayout(action_bar)

        right_layout.addWidget(QLabel("ポジティブプロンプト:"))
        self.pos_text = QTextEdit()
        self.pos_text.setReadOnly(True)
        right_layout.addWidget(self.pos_text, 2)

        right_layout.addWidget(QLabel("ネガティブプロンプト / 生成パラメータ:"))
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        right_layout.addWidget(self.raw_text, 2)

        self.splitter.addWidget(right_panel)
        self.splitter.setSizes([840, 480])
        main_layout.addWidget(self.splitter, 1)

        self.statusBar().showMessage("準備完了")

    def _setup_shortcuts(self):
        """サムネイル一覧での高速キーボード選別ショートカット"""
        for score in range(6):
            sc = QShortcut(QKeySequence(str(score)), self.list_view)
            sc.setContext(Qt.WidgetShortcut)
            sc.activated.connect(lambda s=score: self.apply_rating_to_selected(s))

        sc_del = QShortcut(QKeySequence(Qt.Key_Delete), self.list_view)
        sc_del.setContext(Qt.WidgetShortcut)
        sc_del.activated.connect(self.delete_selected_images)

    def _refresh_filter_combos(self):
        """DB内のモデル・LoRA一覧をバックグラウンド集計してドロップダウンへ反映"""
        worker = FilterOptionsWorker(self.db)
        worker.options_loaded.connect(self._on_filter_options_loaded)
        self._track_worker(worker)
        worker.start()

    def _on_filter_options_loaded(self, models: list[str], loras: list[str]):
        cur_model = self.combo_model.currentData() or ""
        cur_lora = self.combo_lora.currentData() or ""

        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        self.combo_model.addItem("すべてのモデル", "")
        for m in models:
            self.combo_model.addItem(m, m)
        idx_m = self.combo_model.findData(cur_model)
        self.combo_model.setCurrentIndex(idx_m if idx_m >= 0 else 0)
        self.combo_model.blockSignals(False)

        self.combo_lora.blockSignals(True)
        self.combo_lora.clear()
        self.combo_lora.addItem("すべてのLoRA", "")
        for l_name in loras:
            self.combo_lora.addItem(l_name, l_name)
        idx_l = self.combo_lora.findData(cur_lora)
        self.combo_lora.setCurrentIndex(idx_l if idx_l >= 0 else 0)
        self.combo_lora.blockSignals(False)

    # --- 設定の読み込み・保存 ---
    def _load_config(self):
        default_cfg = {
            "root_dir": "",
            "excludes": "grids, extras, temp",
            "expand_similar": False,
            "include_negative": False,
            "min_rating": 0,
            "sort_by": "mtime_desc",
            "window_width": 1340,
            "window_height": 840,
            "splitter_sizes": [840, 480]
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    default_cfg.update(json.load(f))
            except Exception:
                pass

        self.dir_input.setText(default_cfg["root_dir"])
        self.exclude_input.setText(default_cfg["excludes"])
        self.chk_similar_expand.setChecked(default_cfg["expand_similar"])
        self.chk_negative.setChecked(default_cfg["include_negative"])

        idx_r = self.combo_rating.findData(default_cfg.get("min_rating", 0))
        if idx_r >= 0:
            self.combo_rating.setCurrentIndex(idx_r)

        idx_s = self.combo_sort.findData(default_cfg.get("sort_by", "mtime_desc"))
        if idx_s >= 0:
            self.combo_sort.setCurrentIndex(idx_s)

        self.resize(default_cfg["window_width"], default_cfg["window_height"])
        self.splitter.setSizes(default_cfg["splitter_sizes"])

    def _save_config(self):
        cfg = {
            "root_dir": self.dir_input.text().strip(),
            "excludes": self.exclude_input.text().strip(),
            "expand_similar": self.chk_similar_expand.isChecked(),
            "include_negative": self.chk_negative.isChecked(),
            "min_rating": self.combo_rating.currentData() or 0,
            "sort_by": self.combo_sort.currentData() or "mtime_desc",
            "window_width": self.width(),
            "window_height": self.height(),
            "splitter_sizes": self.splitter.sizes()
        }
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)

    # --- フォルダ選択 & スキャン ---
    def select_folder(self):
        start_dir = self.dir_input.text().strip() or ""
        folder = QFileDialog.getExistingDirectory(self, "画像フォルダを選択", start_dir)
        if folder:
            self.dir_input.setText(folder)
            self._save_config()

    def start_scan(self):
        root_dir = self.dir_input.text().strip()
        if not root_dir or not os.path.isdir(root_dir):
            QMessageBox.warning(self, "エラー", "有効な対象フォルダを選択してください。")
            return

        self._save_config()
        excludes = self.exclude_input.text().split(",")
        force = self.chk_force_rescan.isChecked()
        self.btn_scan.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.statusBar().showMessage("フォルダを走査中（強制再抽出）..." if force else "フォルダを走査中...")

        self.worker = ScanWorker(root_dir, excludes, self.db, force_rescan=force)
        self.worker.progress.connect(self.on_scan_progress)
        self.worker.finished_scan.connect(self.on_scan_finished)
        self.worker.start()

    def on_scan_progress(self, current: int, total: int):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(f"メタデータ・ハッシュ抽出中: {current} / {total} 枚")

    def on_scan_finished(self, added_count: int, removed_count: int, ignored_count: int):
        self.btn_scan.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.chk_force_rescan.setChecked(False)
        self._refresh_filter_combos()
        self.statusBar().showMessage(
            f"スキャン完了（AI画像登録: {added_count}件 / 非AI除外: {ignored_count}件 / 削除整理: {removed_count}件）"
        )
        self.perform_search()

    # --- 非同期検索 & フィルタクリア & 類似検索 ---
    def reset_filters(self):
        self.search_input.clear()
        self.combo_model.blockSignals(True)
        self.combo_lora.blockSignals(True)
        self.combo_rating.blockSignals(True)
        self.combo_model.setCurrentIndex(0)
        self.combo_lora.setCurrentIndex(0)
        self.combo_rating.setCurrentIndex(0)
        self.combo_model.blockSignals(False)
        self.combo_lora.blockSignals(False)
        self.combo_rating.blockSignals(False)
        self.perform_search()

    def find_duplicates(self):
        if any(isinstance(w, DuplicateWorker) and w.isRunning() for w in self._active_workers):
            return
        self.search_seq += 1
        self._duplicate_mode = False
        self._duplicate_keep_by_path = {}
        self.btn_select_old_duplicates.setEnabled(False)
        self.btn_delete_duplicates.setEnabled(False)
        self.btn_find_duplicates.setEnabled(False)
        self.statusBar().showMessage("重複画像の内容を確認中（完全一致・SHA-256）...")
        worker = DuplicateWorker(self.db)
        expected_seq = self.search_seq
        worker.duplicates_found.connect(lambda rows, mapping, errors: self._on_duplicates_found(rows, mapping, errors, expected_seq))
        worker.finished.connect(lambda: self.btn_find_duplicates.setEnabled(True))
        self._track_worker(worker)
        worker.start()

    def _on_duplicates_found(self, rows: list[dict], keep_by_path: dict, errors: int, expected_seq: int):
        if self.search_seq != expected_seq:
            return
        self._duplicate_mode = True
        self._duplicate_keep_by_path = keep_by_path
        self.model.set_items(rows)
        self.list_view.scrollToTop()
        self.btn_select_old_duplicates.setEnabled(bool(keep_by_path))
        self.btn_delete_duplicates.setEnabled(bool(keep_by_path))
        groups = len({(v[1], v[2]) for v in keep_by_path.values()})
        self.statusBar().showMessage(
            f"完全一致の重複: {groups}組 / {len(keep_by_path)}枚が整理候補 / 読取失敗: {errors}件。各組の最新1枚を保護します。"
        )

    def select_old_duplicates(self):
        if not self._duplicate_mode:
            return
        selection = self.list_view.selectionModel()
        selection.clearSelection()
        bulk = QItemSelection()
        count = 0
        for row, item in enumerate(self.model.items):
            if item["path"] in self._duplicate_keep_by_path:
                index = self.model.index(row, 0)
                bulk.select(index, index)
                count += 1
        if count:
            selection.select(bulk, QItemSelectionModel.Select)
        self.statusBar().showMessage(
            f"古い重複 {count}枚を選択しました。元ファイルはまだ削除していません。ゴミ箱ボタンで確認してください。"
        )

    def perform_search(self):
        self._duplicate_mode = False
        self._duplicate_keep_by_path = {}
        self.btn_select_old_duplicates.setEnabled(False)
        self.btn_delete_duplicates.setEnabled(False)
        self.search_seq += 1
        seq = self.search_seq
        params = {
            "query": self.search_input.text(),
            "include_negative": self.chk_negative.isChecked(),
            "min_rating": self.combo_rating.currentData() or 0,
            "expand_similar": self.chk_similar_expand.isChecked(),
            "model_filter": self.combo_model.currentData() or "",
            "lora_filter": self.combo_lora.currentData() or "",
            "sort_by": self.combo_sort.currentData() or "mtime_desc",
        }
        self.statusBar().showMessage("検索・絞り込み中...")
        worker = SearchWorker(seq, self.db, "normal", params)
        worker.search_finished.connect(self._on_search_completed)
        self._track_worker(worker)
        worker.start()

    def search_similar_prompt(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "類似プロンプト検索", "基準にする画像を1枚選択してください。")
            return
        self.search_seq += 1
        seq = self.search_seq
        params = {
            "target_path": self.model.items[rows[-1]]["path"],
            "min_rating": self.combo_rating.currentData() or 0,
        }
        self.statusBar().showMessage("類似プロンプトを計算中...")
        worker = SearchWorker(seq, self.db, "similar_prompt", params)
        worker.search_finished.connect(self._on_search_completed)
        self._track_worker(worker)
        worker.start()

    def search_similar_visual(self):
        rows = self._selected_rows()
        if not rows:
            QMessageBox.information(self, "見た目類似検索", "基準にする画像を1枚選択してください。")
            return
        self.search_seq += 1
        seq = self.search_seq
        params = {
            "target_path": self.model.items[rows[-1]]["path"],
            "min_rating": self.combo_rating.currentData() or 0,
        }
        self.statusBar().showMessage("見た目類似度 (dHash) を計算中...")
        worker = SearchWorker(seq, self.db, "similar_visual", params)
        worker.search_finished.connect(self._on_search_completed)
        self._track_worker(worker)
        worker.start()

    def _on_search_completed(self, seq_id: int, results: list[dict], info_text: str, mode: str):
        if seq_id != self.search_seq:
            return
        self.model.set_items(results)
        self.list_view.scrollToTop()
        if mode == "normal":
            if info_text:
                self.statusBar().showMessage(f"検索結果: {len(results):,} 件 ｜ {info_text}")
            else:
                self.statusBar().showMessage(f"検索結果: {len(results):,} 件")
        elif mode == "similar_prompt":
            self.statusBar().showMessage(
                f"類似プロンプト検索: 「{info_text}」に呪文が似た画像 {len(results):,} 件"
            )
        elif mode == "similar_visual":
            self.statusBar().showMessage(
                f"見た目類似検索 (dHash): 「{info_text}」に構図・配色が似た画像 {len(results):,} 件"
            )

    def _selected_rows(self) -> list[int]:
        indexes = self.list_view.selectionModel().selectedIndexes()
        return sorted({idx.row() for idx in indexes})

    def _update_detail_panel(self, item_summary: dict):
        path = item_summary["path"]
        detail = self.db.get_image_detail(path) or item_summary
        self._current_detail_row = detail

        model_str = detail.get("model") or "不明"
        loras_str = detail.get("loras") or "なし"
        rating = detail.get("rating") or 0
        rating_str = ("★" * rating) if rating > 0 else "未設定"

        self.meta_badge_label.setText(
            f"モデル: {model_str}  ｜  LoRA: {loras_str}  ｜  評価: {rating_str}"
        )
        self.path_label.setText(f"パス: {path}")
        self.pos_text.setPlainText(detail.get("positive") or "(プロンプトなし)")
        self.raw_text.setPlainText(detail.get("raw_meta") or "")

        if os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                scaled = pix.scaled(self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(scaled)
        else:
            self.preview_label.clear()
            self.preview_label.setText("ファイルが見つかりません")

    def on_selection_changed(self, selected, deselected):
        rows = self._selected_rows()
        if not rows:
            return
        self._update_detail_panel(self.model.items[rows[-1]])

    # --- 評価・コピー・ファイル操作 ---
    def apply_rating_to_selected(self, rating: int):
        rows = self._selected_rows()
        if not rows:
            return
        for r in rows:
            path = self.model.items[r]["path"]
            new_r = self.db.set_rating(path, rating)
            self.model.update_rating_at(r, new_r)
        self._update_detail_panel(self.model.items[rows[-1]])
        label = ("★" * rating) if rating > 0 else "評価なし"
        self.statusBar().showMessage(f"{len(rows)} 件の評価を「{label}」に設定しました")

    def on_rating_combo_changed(self, idx: int):
        val = self.combo_set_rating.currentData()
        if val is not None and val >= 0:
            self.apply_rating_to_selected(val)
            self.combo_set_rating.blockSignals(True)
            self.combo_set_rating.setCurrentIndex(0)
            self.combo_set_rating.blockSignals(False)

    def copy_positive(self):
        text = (
            self._current_detail_row.get("positive", "")
            if self._current_detail_row
            else self.pos_text.toPlainText()
        )
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("ポジティブプロンプトをクリップボードにコピーしました")

    def copy_negative(self):
        neg = (self._current_detail_row.get("negative") or "") if self._current_detail_row else ""
        if neg:
            QApplication.clipboard().setText(neg)
            self.statusBar().showMessage("ネガティブプロンプトをクリップボードにコピーしました")
        else:
            self.statusBar().showMessage("この画像にはネガティブプロンプトがありません")

    def copy_raw_meta(self):
        text = self.raw_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("全生成パラメータをクリップボードにコピーしました")

    def open_in_explorer(self):
        rows = self._selected_rows()
        if not rows:
            return
        path = os.path.normpath(self.model.items[rows[-1]]["path"])
        if os.path.exists(path):
            subprocess.run(["explorer", "/select,", path])

    def delete_selected_images(self):
        rows = self._selected_rows()
        if not rows:
            return
        # In duplicate view, refuse deletion of the preserved newest copy.
        if self._duplicate_mode:
            selected = [self.model.items[r]["path"] for r in rows]
            if any(path not in self._duplicate_keep_by_path for path in selected):
                QMessageBox.warning(self, "保護された画像", "各重複グループの最新画像は削除できません。古い重複のみ選択してください。")
                return
            for path in selected:
                keeper, size, digest = self._duplicate_keep_by_path[path]
                try:
                    if (not os.path.isfile(path) or not os.path.isfile(keeper) or
                            os.path.getsize(path) != size or os.path.getsize(keeper) != size or
                            sha256_file(path) != digest or sha256_file(keeper) != digest):
                        QMessageBox.warning(self, "変更を検出", "検索後にファイルが変更・移動されています。削除せず重複検索をやり直してください。")
                        return
                except OSError:
                    QMessageBox.warning(self, "ファイル確認エラー", "安全確認ができないため削除を中止しました。")
                    return
        reply = QMessageBox.question(
            self,
            "削除の確認",
            f"選択された {len(rows)} 枚の画像をWindowsのゴミ箱へ移動し、インデックスから削除しますか？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        deleted_paths = []
        for r in rows:
            raw_path = self.model.items[r]["path"]
            norm_path = os.path.normpath(raw_path)
            try:
                if os.path.exists(norm_path):
                    send2trash(norm_path)
                deleted_paths.append(raw_path)
            except Exception as e:
                QMessageBox.warning(self, "削除エラー", f"{norm_path} の削除に失敗しました:\n{e}")

        if deleted_paths:
            self.db.delete_paths(deleted_paths)
            self.model.remove_paths(set(deleted_paths))
            self._current_detail_row = None
            self.preview_label.clear()
            self.preview_label.setText("削除完了")
            self.statusBar().showMessage(f"{len(deleted_paths)} 件をゴミ箱へ移動しました")

    def show_context_menu(self, pos):
        if not self._selected_rows():
            return
        menu = QMenu(self)

        act_sim_p = QAction("類似プロンプト検索", self)
        act_sim_p.triggered.connect(self.search_similar_prompt)
        act_sim_v = QAction("見た目類似検索 (dHash)", self)
        act_sim_v.triggered.connect(self.search_similar_visual)

        rating_menu = menu.addMenu("評価を設定 (キー 0〜5)")
        for score in range(6):
            r_label = f"{'★' * score} ({score})" if score > 0 else "評価なし (0)"
            act_r = QAction(r_label, self)
            act_r.triggered.connect(lambda checked=False, s=score: self.apply_rating_to_selected(s))
            rating_menu.addAction(act_r)

        act_copy_pos = QAction("ポジティブプロンプトをコピー", self)
        act_copy_pos.triggered.connect(self.copy_positive)
        act_copy_neg = QAction("ネガティブプロンプトをコピー", self)
        act_copy_neg.triggered.connect(self.copy_negative)
        act_copy_all = QAction("全生成パラメータをコピー", self)
        act_copy_all.triggered.connect(self.copy_raw_meta)

        act_exp = QAction("エクスプローラーで場所を開く", self)
        act_exp.triggered.connect(self.open_in_explorer)
        act_del = QAction("ゴミ箱へ移動 (Delete)", self)
        act_del.triggered.connect(self.delete_selected_images)

        menu.addAction(act_sim_p)
        menu.addAction(act_sim_v)
        menu.addSeparator()
        menu.addAction(act_copy_pos)
        menu.addAction(act_copy_neg)
        menu.addAction(act_copy_all)
        menu.addSeparator()
        menu.addAction(act_exp)
        menu.addSeparator()
        menu.addAction(act_del)
        menu.exec(self.list_view.mapToGlobal(pos))


if __name__ == "__main__":
    # WindowsタスクバーでPythonのデフォルトアイコンと分離して独自アイコンを表示する設定
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PromptFinderPro.App.1.0")

    app = QApplication(sys.argv)
    app.setStyleSheet(APP_STYLESHEET)

    icon_file = resource_path("app_icon.ico")
    if os.path.exists(icon_file):
        app.setWindowIcon(QIcon(icon_file))

    window = PromptFinderWindow()
    window.show()
    sys.exit(app.exec())
