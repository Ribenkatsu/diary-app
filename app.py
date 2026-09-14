import streamlit as st
import sqlite3
import re
from html import unescape
from datetime import date, datetime
from streamlit_calendar import calendar


# =========================================
# 基本設定
# =========================================

DB_FILE = "diary.db"

DEFAULT_MAIN_COLOR = "#5861F8"
DEFAULT_BACKGROUND_COLOR = "#F5F5F5"

PREVIEW_LENGTH_OPTIONS = [16, 18, 22]
DEFAULT_PREVIEW_LENGTH = 16


# =========================================
# データベース
# =========================================

def init_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS diaries (
            diary_date TEXT PRIMARY KEY,
            content TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_diary(diary_date):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT content FROM diaries WHERE diary_date = ?",
        (diary_date,)
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else ""


def get_all_diaries():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT diary_date, content
        FROM diaries
        ORDER BY diary_date
    """)

    results = cursor.fetchall()
    conn.close()

    return results


def save_diary(diary_date, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO diaries (diary_date, content)
        VALUES (?, ?)
        ON CONFLICT(diary_date)
        DO UPDATE SET content = excluded.content
    """, (diary_date, content))

    conn.commit()
    conn.close()


def delete_diary(diary_date):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM diaries WHERE diary_date = ?",
        (diary_date,)
    )

    conn.commit()
    conn.close()


def search_diaries(keyword):
    if not keyword:
        return []

    escaped_keyword = (
        keyword
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT diary_date, content
        FROM diaries
        WHERE content LIKE ? ESCAPE '\\'
        ORDER BY diary_date DESC
        """,
        (f"%{escaped_keyword}%",)
    )

    results = cursor.fetchall()
    conn.close()

    return results


def get_setting(setting_key, default_value=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT setting_value FROM settings WHERE setting_key = ?",
        (setting_key,)
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else default_value


def save_setting(setting_key, setting_value):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO settings (setting_key, setting_value)
        VALUES (?, ?)
        ON CONFLICT(setting_key)
        DO UPDATE SET setting_value = excluded.setting_value
    """, (setting_key, setting_value))

    conn.commit()
    conn.close()


# =========================================
# 色関連
# =========================================

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")

    return tuple(
        int(hex_color[i:i + 2], 16)
        for i in (0, 2, 4)
    )


def text_color_for_background(hex_color):
    r, g, b = hex_to_rgb(hex_color)

    brightness = (
        r * 299 +
        g * 587 +
        b * 114
    ) / 1000

    return "#111111" if brightness > 160 else "#FFFFFF"


def rgba_from_hex(hex_color, alpha):
    r, g, b = hex_to_rgb(hex_color)

    return f"rgba({r}, {g}, {b}, {alpha})"


# =========================================
# 日記本文・プレビュー
# =========================================

def strip_html_tags(text):
    text = re.sub(
        r"<br\s*/?>",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"</p>",
        " ",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = unescape(text)
    text = text.replace("\xa0", " ")
    text = " ".join(text.split())

    return text.strip()


def make_diary_preview(content, max_length):
    text = strip_html_tags(content)

    if not text:
        return "日記"

    if len(text) > max_length:
        return text[:max_length - 1] + "…"

    return text


def make_search_excerpt(content, keyword, max_length=70):
    text = strip_html_tags(content)

    if not text:
        return "本文なし"

    if len(text) <= max_length:
        return text

    index = text.lower().find(
        keyword.lower()
    )

    if index == -1:
        return text[:max_length - 1] + "…"

    half = max_length // 2

    start = max(
        0,
        index - half
    )

    end = min(
        len(text),
        start + max_length
    )

    if end - start < max_length:
        start = max(
            0,
            end - max_length
        )

    excerpt = text[start:end]

    if start > 0:
        excerpt = "…" + excerpt

    if end < len(text):
        excerpt = excerpt + "…"

    return excerpt


def preview_style(length_value):
    if length_value == 16:
        return {
            "font_size": 10,
            "height": 40
        }

    if length_value == 18:
        return {
            "font_size": 9.5,
            "height": 42
        }

    return {
        "font_size": 8.5,
        "height": 44
    }


# =========================================
# 表示用パーツ
# =========================================

def render_page_hero(icon, title):
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-hero-title">
                {icon} {title}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_section_tag(text):
    st.markdown(
        f"""
        <div class="section-tag">
            {text}
        </div>
        """,
        unsafe_allow_html=True
    )


def render_date_chip(text):
    st.markdown(
        f"""
        <div class="date-chip">
            {text}
        </div>
        """,
        unsafe_allow_html=True
    )


def format_japanese_date(date_string):
    return datetime.strptime(
        date_string,
        "%Y-%m-%d"
    ).strftime(
        "%Y年%m月%d日"
    )


# =========================================
# リッチテキストエディタ
# =========================================

EDITOR_HTML = """
<div class="editor-wrapper">

    <div id="toolbar">

        <select class="ql-size">
            <option value="10px">10</option>
            <option value="12px">12</option>
            <option value="14px">14</option>
            <option value="16px" selected>16</option>
            <option value="18px">18</option>
            <option value="20px">20</option>
            <option value="24px">24</option>
            <option value="28px">28</option>
            <option value="32px">32</option>
            <option value="36px">36</option>
        </select>

        <select class="ql-font">
            <option value="noto-sans-jp" selected>Noto Sans JP</option>
            <option value="noto-serif-jp">Noto Serif JP</option>
            <option value="yu-gothic">游ゴシック</option>
            <option value="meiryo">メイリオ</option>
        </select>

        <button class="ql-bold"></button>
        <button class="ql-italic"></button>
        <button class="ql-underline"></button>
        <button class="ql-strike"></button>

        <select class="ql-color"></select>
        <select class="ql-background"></select>

        <button class="ql-list" value="ordered"></button>
        <button class="ql-list" value="bullet"></button>

        <select class="ql-align"></select>

        <button class="ql-clean"></button>

    </div>

    <div id="editor"></div>

</div>
"""


def build_editor_css(main_color):
    light_main = rgba_from_hex(
        main_color,
        0.12
    )

    medium_main = rgba_from_hex(
        main_color,
        0.28
    )

    return f"""
@import url('https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.snow.css');
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&family=Noto+Serif+JP:wght@400;700&display=swap');


.editor-wrapper {{
    width: 100%;
    height: 100%;

    background: #FFFFFF;

    border:
        3px solid
        {main_color};

    border-radius:
        16px;

    overflow:
        hidden;

    box-sizing:
        border-box;

    box-shadow:
        0 8px 18px
        rgba(0, 0, 0, 0.08);
}}


#toolbar {{
    background-color:
        {light_main};

    border:
        none !important;

    border-bottom:
        2px solid
        {medium_main}
        !important;
}}


#editor {{
    min-height:
        340px;

    background:
        #FFFFFF;

    border:
        none !important;
}}


.ql-editor {{
    min-height:
        340px;

    padding:
        18px;

    font-size:
        16px;

    color:
        #222222;

    font-family:
        "Noto Sans JP",
        sans-serif;
}}


.ql-toolbar button.ql-active {{
    color:
        {main_color};
}}


.ql-toolbar button.ql-active .ql-stroke {{
    stroke:
        {main_color};
}}


.ql-picker.ql-size {{
    width:
        70px;
}}


.ql-picker.ql-font {{
    width:
        145px;
}}


.ql-font-noto-sans-jp {{
    font-family:
        "Noto Sans JP",
        sans-serif;
}}


.ql-font-noto-serif-jp {{
    font-family:
        "Noto Serif JP",
        serif;
}}


.ql-font-yu-gothic {{
    font-family:
        "Yu Gothic",
        "YuGothic",
        sans-serif;
}}


.ql-font-meiryo {{
    font-family:
        "Meiryo",
        sans-serif;
}}


.ql-picker.ql-size
.ql-picker-label::before,

.ql-picker.ql-size
.ql-picker-item::before {{
    content:
        attr(data-value);
}}


.ql-picker.ql-size .ql-picker-label[data-value="10px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="10px"]::before {{
    content: "10";
}}


.ql-picker.ql-size .ql-picker-label[data-value="12px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="12px"]::before {{
    content: "12";
}}


.ql-picker.ql-size .ql-picker-label[data-value="14px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="14px"]::before {{
    content: "14";
}}


.ql-picker.ql-size .ql-picker-label[data-value="16px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="16px"]::before {{
    content: "16";
}}


.ql-picker.ql-size .ql-picker-label[data-value="18px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="18px"]::before {{
    content: "18";
}}


.ql-picker.ql-size .ql-picker-label[data-value="20px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="20px"]::before {{
    content: "20";
}}


.ql-picker.ql-size .ql-picker-label[data-value="24px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="24px"]::before {{
    content: "24";
}}


.ql-picker.ql-size .ql-picker-label[data-value="28px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="28px"]::before {{
    content: "28";
}}


.ql-picker.ql-size .ql-picker-label[data-value="32px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="32px"]::before {{
    content: "32";
}}


.ql-picker.ql-size .ql-picker-label[data-value="36px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="36px"]::before {{
    content: "36";
}}


.ql-picker.ql-font
.ql-picker-label[data-value="noto-sans-jp"]::before,

.ql-picker.ql-font
.ql-picker-item[data-value="noto-sans-jp"]::before {{
    content:
        "Noto Sans JP";
}}


.ql-picker.ql-font
.ql-picker-label[data-value="noto-serif-jp"]::before,

.ql-picker.ql-font
.ql-picker-item[data-value="noto-serif-jp"]::before {{
    content:
        "Noto Serif JP";
}}


.ql-picker.ql-font
.ql-picker-label[data-value="yu-gothic"]::before,

.ql-picker.ql-font
.ql-picker-item[data-value="yu-gothic"]::before {{
    content:
        "游ゴシック";
}}


.ql-picker.ql-font
.ql-picker-label[data-value="meiryo"]::before,

.ql-picker.ql-font
.ql-picker-item[data-value="meiryo"]::before {{
    content:
        "メイリオ";
}}
"""


EDITOR_JS = """
export default async function(component) {

    const {
        parentElement,
        data,
        setStateValue
    } = component;


    if (!window.Quill) {

        await new Promise((resolve, reject) => {

            const script =
                document.createElement("script");

            script.src =
                "https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.js";

            script.onload = resolve;
            script.onerror = reject;

            document.head.appendChild(script);
        });
    }


    const Quill = window.Quill;


    const SizeStyle =
        Quill.import("attributors/style/size");


    SizeStyle.whitelist = [
        "10px",
        "12px",
        "14px",
        "16px",
        "18px",
        "20px",
        "24px",
        "28px",
        "32px",
        "36px"
    ];


    Quill.register(
        SizeStyle,
        true
    );


    const FontClass =
        Quill.import("attributors/class/font");


    FontClass.whitelist = [
        "noto-sans-jp",
        "noto-serif-jp",
        "yu-gothic",
        "meiryo"
    ];


    Quill.register(
        FontClass,
        true
    );


    const editorElement =
        parentElement.querySelector(
            "#editor"
        );


    if (!editorElement.__quill) {

        const quill =
            new Quill(
                editorElement,
                {
                    theme: "snow",

                    modules: {
                        toolbar:
                            parentElement.querySelector(
                                "#toolbar"
                            )
                    }
                }
            );


        editorElement.__quill =
            quill;


        const initialValue =
            data?.value ?? "";


        if (initialValue) {

            quill.clipboard
                .dangerouslyPasteHTML(
                    initialValue
                );
        }


        quill.on(
            "text-change",

            function () {

                const html =
                    quill.root.innerHTML;

                setStateValue(
                    "value",
                    html
                );
            }
        );

    } else {

        const quill =
            editorElement.__quill;


        const newValue =
            data?.value ?? "";


        if (
            document.activeElement !== quill.root
            &&
            quill.root.innerHTML !== newValue
        ) {

            quill.clipboard
                .dangerouslyPasteHTML(
                    newValue
                );
        }
    }
}
"""


def build_rich_editor(main_color):
    editor_css = build_editor_css(
        main_color
    )

    return st.components.v2.component(
        "diary_rich_editor",
        html=EDITOR_HTML,
        css=editor_css,
        js=EDITOR_JS,
    )


def rich_editor(
    component_factory,
    value="",
    key=None
):

    state = st.session_state.get(
        key,
        {}
    )

    current_value = state.get(
        "value",
        value
    )

    result = component_factory(
        data={
            "value": current_value
        },

        default={
            "value": current_value
        },

        key=key,

        on_value_change=
            lambda: None,

        height=450,

        width="stretch"
    )

    return result.value


# =========================================
# 初期化
# =========================================

init_database()

st.set_page_config(
    page_title="日記アプリ",
    page_icon="📖",
    layout="centered"
)


# =========================================
# 設定読み込み
# =========================================

main_color = get_setting(
    "main_color",
    DEFAULT_MAIN_COLOR
)

background_color = get_setting(
    "background_color",
    DEFAULT_BACKGROUND_COLOR
)

preview_length_raw = get_setting(
    "preview_length",
    str(DEFAULT_PREVIEW_LENGTH)
)


try:

    preview_length = int(
        preview_length_raw
    )

except ValueError:

    preview_length = (
        DEFAULT_PREVIEW_LENGTH
    )


if (
    preview_length
    not in PREVIEW_LENGTH_OPTIONS
):

    preview_length = (
        DEFAULT_PREVIEW_LENGTH
    )


preview_ui = preview_style(
    preview_length
)


main_text_color = (
    text_color_for_background(
        main_color
    )
)

background_text_color = (
    text_color_for_background(
        background_color
    )
)

light_main_color = (
    rgba_from_hex(
        main_color,
        0.12
    )
)

medium_main_color = (
    rgba_from_hex(
        main_color,
        0.28
    )
)

strong_main_color = (
    rgba_from_hex(
        main_color,
        0.82
    )
)


# =========================================
# アプリ全体CSS
# =========================================

st.markdown(
    f"""
    <style>

    html,
    body {{
        background-color:
            {background_color};
    }}


    [data-testid="stAppViewContainer"] {{
        background-color:
            {background_color};
    }}


    .block-container {{
        max-width:
            980px;

        padding-top:
            2.7rem;

        padding-bottom:
            4rem;
    }}


    .block-container,
    .block-container p,
    .block-container label,
    .block-container h1,
    .block-container h2,
    .block-container h3 {{
        color:
            {background_text_color};
    }}


    /* サイドバー */

    section[data-testid="stSidebar"] {{
        background-color:
            {background_color};

        border-right:
            2px solid
            {medium_main_color};
    }}


    section[data-testid="stSidebar"] h1 {{
        border-left:
            5px solid
            {main_color};

        padding-left:
            10px;

        color:
            {background_text_color};
    }}


    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label {{
        color:
            {background_text_color};
    }}


    section[data-testid="stSidebar"]
    div[role="radiogroup"] label {{
        padding:
            0.52rem 0.65rem;

        border-radius:
            10px;
    }}


    section[data-testid="stSidebar"]
    div[role="radiogroup"]
    label:has(input:checked) {{
        background-color:
            {main_color};
    }}


    section[data-testid="stSidebar"]
    div[role="radiogroup"]
    label:has(input:checked) p {{
        color:
            {main_text_color}
            !important;

        font-weight:
            700;
    }}


    /* ページタイトル */

    .page-hero {{
        background:
            linear-gradient(
                135deg,
                {main_color},
                {strong_main_color}
            );

        color:
            {main_text_color};

        padding:
            26px 28px;

        border-radius:
            20px;

        margin-bottom:
            18px;

        box-shadow:
            0 12px 28px
            rgba(0, 0, 0, 0.10);
    }}


    .page-hero-title {{
        font-size:
            42px;

        font-weight:
            800;

        line-height:
            1.2;

        color:
            {main_text_color};
    }}


    /* 日付 */

    .date-chip {{
        display:
            inline-block;

        background-color:
            #FFFFFF;

        color:
            {main_color};

        border:
            2px solid
            {medium_main_color};

        padding:
            9px 15px;

        border-radius:
            999px;

        font-weight:
            700;

        margin:
            2px 0 16px 0;
    }}


    /* セクションタグ */

    .section-tag {{
        display:
            inline-block;

        background-color:
            {main_color};

        color:
            {main_text_color};

        padding:
            8px 15px;

        border-radius:
            999px;

        font-weight:
            700;

        font-size:
            15px;

        margin:
            5px 0 10px 0;
    }}


    .selected-diary-title {{
        font-size:
            34px;

        font-weight:
            800;

        color:
            {background_text_color};

        margin:
            8px 0 12px 0;
    }}


    /* =====================================
       メイン操作ボタン
    ===================================== */

    div[data-testid="stButton"]
    button[kind="primary"] {{

        background-color:
            {main_color}
            !important;

        border:
            3px solid
            {main_color}
            !important;

        color:
            {main_text_color}
            !important;

        border-radius:
            15px
            !important;

        min-height:
            60px
            !important;

        padding:
            10px 22px
            !important;

        font-size:
            18px
            !important;

        font-weight:
            900
            !important;

        box-shadow:
            0 6px 15px
            rgba(0, 0, 0, 0.12);
    }}


    div[data-testid="stButton"]
    button[kind="primary"] p {{

        color:
            {main_text_color}
            !important;

        font-size:
            18px
            !important;

        font-weight:
            900
            !important;
    }}


    div[data-testid="stButton"]
    button[kind="primary"]:hover {{

        background-color:
            {main_color}
            !important;

        border-color:
            {main_color}
            !important;

        color:
            {main_text_color}
            !important;

        opacity:
            0.86;
    }}


    /* =====================================
       Enter検索用
       formの検索ボタン
    ===================================== */

    div[data-testid="stFormSubmitButton"]
    button[kind="primary"] {{

        background-color:
            {main_color}
            !important;

        border:
            3px solid
            {main_color}
            !important;

        color:
            {main_text_color}
            !important;

        border-radius:
            15px
            !important;

        min-height:
            60px
            !important;

        padding:
            10px 22px
            !important;

        font-size:
            18px
            !important;

        font-weight:
            900
            !important;

        box-shadow:
            0 6px 15px
            rgba(0, 0, 0, 0.12);
    }}


    div[data-testid="stFormSubmitButton"]
    button[kind="primary"] p {{

        color:
            {main_text_color}
            !important;

        font-size:
            18px
            !important;

        font-weight:
            900
            !important;
    }}


    div[data-testid="stFormSubmitButton"]
    button[kind="primary"]:hover {{

        background-color:
            {main_color}
            !important;

        border-color:
            {main_color}
            !important;

        color:
            {main_text_color}
            !important;

        opacity:
            0.86;
    }}


    /* 白ボタン */

    div[data-testid="stButton"]
    button[kind="secondary"] {{

        background-color:
            #FFFFFF
            !important;

        border:
            2px solid
            #D0D0D0
            !important;

        color:
            #222222
            !important;

        border-radius:
            14px
            !important;

        min-height:
            52px
            !important;

        font-size:
            16px
            !important;

        font-weight:
            800
            !important;
    }}


    div[data-testid="stButton"]
    button[kind="secondary"] p {{

        color:
            #222222
            !important;

        font-weight:
            800
            !important;
    }}


    /* 本当に削除 */

    div[data-testid="stButton"]
    button[kind="tertiary"] {{

        background-color:
            #D93025
            !important;

        border:
            3px solid
            #D93025
            !important;

        color:
            #FFFFFF
            !important;

        border-radius:
            15px
            !important;

        min-height:
            58px
            !important;

        font-size:
            17px
            !important;

        font-weight:
            900
            !important;
    }}


    div[data-testid="stButton"]
    button[kind="tertiary"] p {{

        color:
            #FFFFFF
            !important;

        font-weight:
            900
            !important;
    }}


    /* カード */

    div[data-testid="stVerticalBlockBorderWrapper"] {{

        border:
            2px solid
            {medium_main_color}
            !important;

        border-radius:
            16px
            !important;

        background-color:
            rgba(
                255,
                255,
                255,
                0.85
            )
            !important;

        box-shadow:
            0 6px 16px
            rgba(0, 0, 0, 0.05);
    }}


    div[data-testid="stVerticalBlockBorderWrapper"] p,
    div[data-testid="stVerticalBlockBorderWrapper"] label,
    div[data-testid="stVerticalBlockBorderWrapper"] h2,
    div[data-testid="stVerticalBlockBorderWrapper"] h3 {{

        color:
            #222222
            !important;
    }}


    hr {{
        border-color:
            {medium_main_color};
    }}

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================
# エディタ生成
# =========================================

rich_editor_component = (
    build_rich_editor(
        main_color
    )
)


# =========================================
# サイドバー
# =========================================

st.sidebar.title(
    "📖 日記アプリ"
)


page = st.sidebar.radio(
    "画面を選択",
    [
        "✏️ 今日の日記",
        "📅 日記を見る",
        "🔍 日記を検索",
        "⚙️ 設定"
    ]
)


# =========================================
# 今日の日記
# =========================================

if page == "✏️ 今日の日記":

    today = date.today().isoformat()


    render_page_hero(
        "✏️",
        "今日の日記"
    )


    render_date_chip(
        f"📅 "
        f"{datetime.today().strftime('%Y年%m月%d日')}"
    )


    render_section_tag(
        "✍️ 今日の記録"
    )


    current_diary = get_diary(
        today
    )


    content = rich_editor(
        rich_editor_component,
        value=current_diary,
        key="today_editor"
    )


    st.write("")


    if st.button(
        "保存する",
        type="primary",
        use_container_width=True
    ):

        if strip_html_tags(content):

            save_diary(
                today,
                content
            )

            st.success(
                "日記を保存しました！"
            )

        else:

            st.warning(
                "日記が入力されていません。"
            )


# =========================================
# 日記を見る
# =========================================

elif page == "📅 日記を見る":

    render_page_hero(
        "📅",
        "日記を見る"
    )


    render_section_tag(
        "🗓️ カレンダー"
    )


    diaries = get_all_diaries()

    events = []


    for diary_date, diary_content in diaries:

        preview = make_diary_preview(
            diary_content,
            preview_length
        )


        events.append({
            "title":
                preview,

            "start":
                diary_date,

            "allDay":
                True,

            "backgroundColor":
                main_color,

            "borderColor":
                main_color,

            "textColor":
                main_text_color
        })


    calendar_options = {

        "initialView":
            "dayGridMonth",

        "headerToolbar": {

            "left":
                "prev,next today",

            "center":
                "title",

            "right":
                ""
        },

        "locale":
            "ja",

        "height":
            620
    }


    calendar_custom_css = f"""

    .fc {{

        background:
            #FFFFFF;

        border:
            3px solid
            {main_color};

        border-radius:
            16px;

        padding:
            12px;

        box-sizing:
            border-box;

        font-size:
            14px;
    }}


    .fc .fc-toolbar.fc-header-toolbar {{

        background:
            {light_main_color};

        border:
            1px solid
            {medium_main_color};

        border-radius:
            12px;

        padding:
            10px 12px;

        margin-bottom:
            12px;
    }}


    .fc .fc-toolbar-title {{

        color:
            #111111;

        font-size:
            26px
            !important;

        font-weight:
            900;
    }}


    .fc .fc-button-primary {{

        background-color:
            {main_color}
            !important;

        border-color:
            {main_color}
            !important;

        color:
            {main_text_color}
            !important;

        border-radius:
            7px
            !important;
    }}


    .fc .fc-button-primary:hover {{

        opacity:
            0.86;
    }}


    .fc .fc-button {{

        font-size:
            14px
            !important;

        font-weight:
            800
            !important;

        padding:
            7px 11px
            !important;
    }}


    .fc .fc-col-header-cell {{

        background:
            {light_main_color};
    }}


    .fc .fc-col-header-cell-cushion {{

        font-size:
            15px;

        font-weight:
            800;

        padding:
            8px 0;
    }}


    .fc .fc-daygrid-day-number {{

        font-size:
            16px;

        font-weight:
            900;

        padding:
            6px 7px;
    }}


    /* 日曜日 */

    .fc .fc-col-header-cell.fc-day-sun {{

        background-color:
            #FFEAEA
            !important;
    }}


    .fc .fc-col-header-cell.fc-day-sun
    .fc-col-header-cell-cushion {{

        color:
            #D93025
            !important;
    }}


    .fc .fc-daygrid-day.fc-day-sun {{

        background-color:
            #FFF5F5
            !important;
    }}


    .fc .fc-daygrid-day.fc-day-sun
    .fc-daygrid-day-number {{

        color:
            #D93025
            !important;
    }}


    /* 土曜日 */

    .fc .fc-col-header-cell.fc-day-sat {{

        background-color:
            #EAF3FF
            !important;
    }}


    .fc .fc-col-header-cell.fc-day-sat
    .fc-col-header-cell-cushion {{

        color:
            #1A73E8
            !important;
    }}


    .fc .fc-daygrid-day.fc-day-sat {{

        background-color:
            #F3F8FF
            !important;
    }}


    .fc .fc-daygrid-day.fc-day-sat
    .fc-daygrid-day-number {{

        color:
            #1A73E8
            !important;
    }}


    /* 今日 */

    .fc .fc-day-today {{

        box-shadow:
            inset 0 0 0 2px
            {main_color};

        position:
            relative;
    }}


    /* 日記ラベル */

    .fc .fc-daygrid-event {{

        width:
            calc(100% - 4px)
            !important;

        max-width:
            calc(100% - 4px)
            !important;

        margin-left:
            2px
            !important;

        margin-right:
            2px
            !important;

        margin-top:
            2px
            !important;

        height:
            {preview_ui["height"]}px;

        min-height:
            {preview_ui["height"]}px;

        max-height:
            {preview_ui["height"]}px;

        border-radius:
            7px;

        overflow:
            hidden
            !important;

        box-sizing:
            border-box;
    }}


    .fc .fc-event-main,
    .fc .fc-event-main-frame,
    .fc .fc-event-title-container {{

        width:
            100%;

        height:
            100%;

        overflow:
            hidden
            !important;
    }}


    .fc .fc-event-title {{

        display:
            -webkit-box
            !important;

        width:
            100%;

        max-width:
            100%;

        box-sizing:
            border-box;

        padding:
            3px 4px;

        font-size:
            {preview_ui["font_size"]}px
            !important;

        font-weight:
            700;

        line-height:
            1.3;

        white-space:
            normal
            !important;

        overflow:
            hidden
            !important;

        word-break:
            break-all;

        overflow-wrap:
            anywhere;

        -webkit-box-orient:
            vertical;

        -webkit-line-clamp:
            2;

        line-clamp:
            2;
    }}


    .fc-theme-standard td,
    .fc-theme-standard th {{

        border-color:
            {medium_main_color};
    }}

    """


    calendar_left, calendar_center, calendar_right = (
        st.columns(
            [0.08, 0.84, 0.08],
            gap="small"
        )
    )


    with calendar_center:

        calendar_result = calendar(
            events=events,
            options=calendar_options,
            custom_css=calendar_custom_css,

            key=(
                f"diary_calendar_"
                f"{preview_length}_"
                f"{main_color}"
            )
        )


    if (
        calendar_result
        and
        calendar_result.get(
            "eventClick"
        )
    ):

        clicked_event = (
            calendar_result[
                "eventClick"
            ]
        )

        clicked_date = (
            clicked_event[
                "event"
            ][
                "start"
            ]
        )


        st.session_state[
            "selected_date"
        ] = clicked_date


        st.session_state.pop(
            "delete_confirm_date",
            None
        )


    if (
        "selected_date"
        in st.session_state
    ):

        selected_date = (
            st.session_state[
                "selected_date"
            ]
        )


        selected_diary = get_diary(
            selected_date
        )


        st.divider()


        render_section_tag(
            "📖 選択した日記"
        )


        st.markdown(
            f"""
            <div class="selected-diary-title">
                {format_japanese_date(selected_date)}
            </div>
            """,
            unsafe_allow_html=True
        )


        if selected_diary:

            edit_content = rich_editor(
                rich_editor_component,
                value=selected_diary,
                key=f"edit_{selected_date}"
            )


            st.write("")


            update_column, delete_column = (
                st.columns(
                    [1, 1],
                    gap="medium"
                )
            )


            with update_column:

                if st.button(
                    "更新する",
                    type="primary",
                    use_container_width=True,
                    key=f"update_{selected_date}"
                ):

                    save_diary(
                        selected_date,
                        edit_content
                    )

                    st.success(
                        "日記を更新しました！"
                    )


            with delete_column:

                if st.button(
                    "削除する",
                    type="primary",
                    use_container_width=True,
                    key=f"delete_{selected_date}"
                ):

                    st.session_state[
                        "delete_confirm_date"
                    ] = selected_date


            if (
                st.session_state.get(
                    "delete_confirm_date"
                )
                == selected_date
            ):

                st.warning(
                    "この日記を削除します。削除後は元に戻せません。"
                )


                confirm_column, cancel_column = (
                    st.columns(
                        [1, 1],
                        gap="medium"
                    )
                )


                with confirm_column:

                    if st.button(
                        "本当に削除する",
                        type="tertiary",
                        use_container_width=True,
                        key=f"confirm_delete_{selected_date}"
                    ):

                        delete_diary(
                            selected_date
                        )


                        st.session_state.pop(
                            "selected_date",
                            None
                        )


                        st.session_state.pop(
                            "delete_confirm_date",
                            None
                        )


                        st.session_state.pop(
                            f"edit_{selected_date}",
                            None
                        )


                        st.rerun()


                with cancel_column:

                    if st.button(
                        "キャンセル",
                        type="secondary",
                        use_container_width=True,
                        key=f"cancel_delete_{selected_date}"
                    ):

                        st.session_state.pop(
                            "delete_confirm_date",
                            None
                        )

                        st.rerun()


        else:

            st.info(
                "この日には日記がありません。"
            )


# =========================================
# 日記検索
# =========================================

elif page == "🔍 日記を検索":

    render_page_hero(
        "🔍",
        "日記を検索"
    )


    render_section_tag(
        "🔎 キーワード検索"
    )


    # =====================================
    # 検索フォーム
    #
    # 入力欄でEnterを押しても検索できる
    # =====================================

    with st.form(
        "diary_search_form",
        clear_on_submit=False
    ):

        search_keyword = st.text_input(
            "検索する言葉",
            placeholder=
                "例：旅行、仕事、嬉しかったこと",
            key="diary_search_keyword"
        )


        st.write("")


        search_submitted = (
            st.form_submit_button(
                "検索する",
                type="primary",
                use_container_width=True
            )
        )


    # =====================================
    # 検索実行
    # =====================================

    if search_submitted:

        cleaned_keyword = (
            search_keyword.strip()
        )


        if cleaned_keyword:

            previous_query = (
                st.session_state.get(
                    "active_search_query",
                    ""
                )
            )


            st.session_state[
                "active_search_query"
            ] = cleaned_keyword


            if (
                previous_query
                != cleaned_keyword
            ):

                st.session_state.pop(
                    "search_selected_date",
                    None
                )


                st.session_state.pop(
                    "search_delete_confirm_date",
                    None
                )


        else:

            st.session_state.pop(
                "active_search_query",
                None
            )


            st.session_state.pop(
                "search_selected_date",
                None
            )


            st.warning(
                "検索する言葉を入力してください。"
            )


    # =====================================
    # 検索結果
    # =====================================

    active_search_query = (
        st.session_state.get(
            "active_search_query",
            ""
        )
    )


    if active_search_query:

        search_results = search_diaries(
            active_search_query
        )


        st.write("")


        render_section_tag(
            f"📚 検索結果 "
            f"{len(search_results)}件"
        )


        if search_results:

            for (
                diary_date,
                diary_content
            ) in search_results:


                with st.container(
                    border=True
                ):

                    st.subheader(
                        format_japanese_date(
                            diary_date
                        )
                    )


                    st.write(
                        make_search_excerpt(
                            diary_content,
                            active_search_query,
                            70
                        )
                    )


                    if st.button(
                        "この日記を開く",
                        type="secondary",
                        use_container_width=True,

                        key=(
                            f"open_search_"
                            f"{diary_date}"
                        )
                    ):

                        st.session_state[
                            "search_selected_date"
                        ] = diary_date


                        st.session_state.pop(
                            "search_delete_confirm_date",
                            None
                        )


        else:

            st.info(
                f'「{active_search_query}」を'
                f'含む日記は見つかりませんでした。'
            )


    # =====================================
    # 検索結果の日記を開く
    # =====================================

    if (
        "search_selected_date"
        in st.session_state
    ):

        search_selected_date = (
            st.session_state[
                "search_selected_date"
            ]
        )


        search_selected_diary = (
            get_diary(
                search_selected_date
            )
        )


        if search_selected_diary:

            st.divider()


            render_section_tag(
                "📖 検索した日記"
            )


            st.markdown(
                f"""
                <div class="selected-diary-title">
                    {format_japanese_date(search_selected_date)}
                </div>
                """,
                unsafe_allow_html=True
            )


            search_edit_content = (
                rich_editor(
                    rich_editor_component,

                    value=
                        search_selected_diary,

                    key=(
                        f"search_edit_"
                        f"{search_selected_date}"
                    )
                )
            )


            st.write("")


            (
                search_update_column,
                search_delete_column
            ) = st.columns(
                [1, 1],
                gap="medium"
            )


            # 更新

            with search_update_column:

                if st.button(
                    "更新する",
                    type="primary",
                    use_container_width=True,

                    key=(
                        f"search_update_"
                        f"{search_selected_date}"
                    )
                ):

                    save_diary(
                        search_selected_date,
                        search_edit_content
                    )


                    st.success(
                        "日記を更新しました！"
                    )


            # 削除

            with search_delete_column:

                if st.button(
                    "削除する",
                    type="primary",
                    use_container_width=True,

                    key=(
                        f"search_delete_"
                        f"{search_selected_date}"
                    )
                ):

                    st.session_state[
                        "search_delete_confirm_date"
                    ] = search_selected_date


            # 削除確認

            if (
                st.session_state.get(
                    "search_delete_confirm_date"
                )
                == search_selected_date
            ):

                st.warning(
                    "この日記を削除します。"
                    "削除後は元に戻せません。"
                )


                (
                    search_confirm_column,
                    search_cancel_column
                ) = st.columns(
                    [1, 1],
                    gap="medium"
                )


                with search_confirm_column:

                    if st.button(
                        "本当に削除する",
                        type="tertiary",
                        use_container_width=True,

                        key=(
                            f"search_confirm_delete_"
                            f"{search_selected_date}"
                        )
                    ):

                        delete_diary(
                            search_selected_date
                        )


                        st.session_state.pop(
                            "search_selected_date",
                            None
                        )


                        st.session_state.pop(
                            "search_delete_confirm_date",
                            None
                        )


                        st.session_state.pop(
                            f"search_edit_"
                            f"{search_selected_date}",
                            None
                        )


                        st.rerun()


                with search_cancel_column:

                    if st.button(
                        "キャンセル",
                        type="secondary",
                        use_container_width=True,

                        key=(
                            f"search_cancel_delete_"
                            f"{search_selected_date}"
                        )
                    ):

                        st.session_state.pop(
                            "search_delete_confirm_date",
                            None
                        )


                        st.rerun()


        else:

            st.session_state.pop(
                "search_selected_date",
                None
            )


# =========================================
# 設定
# =========================================

elif page == "⚙️ 設定":

    render_page_hero(
        "⚙️",
        "設定"
    )


    render_section_tag(
        "🎨 カラー設定"
    )


    # =====================================
    # メインカラー
    # =====================================

    with st.container(
        border=True
    ):

        st.subheader(
            "メインカラー"
        )


        selected_main_color = (
            st.color_picker(
                "メインカラーを選択",
                value=main_color,
                key="main_color_picker"
            )
        )


    st.write("")


    # =====================================
    # 背景カラー
    # =====================================

    with st.container(
        border=True
    ):

        st.subheader(
            "背景カラー"
        )


        selected_background_color = (
            st.color_picker(
                "背景カラーを選択",
                value=background_color,
                key="background_color_picker"
            )
        )


    st.write("")


    # =====================================
    # カレンダー設定
    # =====================================

    render_section_tag(
        "🗓️ カレンダー設定"
    )


    with st.container(
        border=True
    ):

        st.subheader(
            "日記プレビュー"
        )


        current_preview_index = (
            PREVIEW_LENGTH_OPTIONS.index(
                preview_length
            )
        )


        selected_preview_length = (
            st.selectbox(
                "カレンダーに表示する文章の長さ",

                options=
                    PREVIEW_LENGTH_OPTIONS,

                index=
                    current_preview_index,

                format_func=
                    lambda value:
                    f"{value}文字",

                key=
                    "preview_length_select"
            )
        )


        example_text = (
            "今日はアプリ開発をして"
            "カレンダーを改善した。"
        )


        preview_example = (
            make_diary_preview(
                example_text,
                selected_preview_length
            )
        )


        st.caption(
            f"表示例："
            f"{preview_example}"
        )


    st.write("")


    # =====================================
    # 設定保存
    # =====================================

    if st.button(
        "設定を保存する",
        type="primary",
        use_container_width=True
    ):

        save_setting(
            "main_color",
            selected_main_color
        )


        save_setting(
            "background_color",
            selected_background_color
        )


        save_setting(
            "preview_length",
            str(
                selected_preview_length
            )
        )


        st.success(
            "設定を保存しました！"
        )


        st.rerun()