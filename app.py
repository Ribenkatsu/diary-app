import json
import re
from html import unescape
from datetime import date, datetime, timezone

import streamlit as st
from streamlit_calendar import calendar
from supabase import create_client


# =========================================
# 基本設定
# =========================================

APP_URL = "https://ribenkatsudiary.streamlit.app"

DEFAULT_MAIN_COLOR = "#5861F8"
DEFAULT_BACKGROUND_COLOR = "#F5F5F5"
PREVIEW_LENGTH_OPTIONS = [16, 18, 22]
DEFAULT_PREVIEW_LENGTH = 16

st.set_page_config(
    page_title="日記アプリ",
    page_icon="📖",
    layout="centered",
)


# =========================================
# Supabase接続
# =========================================

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_PUBLISHABLE_KEY = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
except KeyError:
    st.error(
        "Supabaseの接続情報が見つかりません。"
        " `.streamlit/secrets.toml` または Streamlit Cloud の Secrets を確認してください。"
    )
    st.stop()


def create_supabase_client():
    return create_client(
        SUPABASE_URL,
        SUPABASE_PUBLISHABLE_KEY,
    )


def get_session_from_response(response):
    if response is None:
        return None

    session = getattr(response, "session", None)
    if session is not None:
        return session

    if hasattr(response, "access_token") and hasattr(response, "refresh_token"):
        return response

    return None


def save_auth_session(session):
    if session is None:
        return

    access_token = getattr(session, "access_token", None)
    refresh_token = getattr(session, "refresh_token", None)

    if access_token and refresh_token:
        st.session_state["sb_access_token"] = access_token
        st.session_state["sb_refresh_token"] = refresh_token


def clear_auth_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]


def restore_logged_in_user(client):
    access_token = st.session_state.get("sb_access_token")
    refresh_token = st.session_state.get("sb_refresh_token")

    if not access_token or not refresh_token:
        return None

    try:
        response = client.auth.set_session(
            access_token,
            refresh_token,
        )

        refreshed_session = get_session_from_response(response)
        save_auth_session(refreshed_session)

        user_response = client.auth.get_user()
        return getattr(user_response, "user", None)

    except Exception:
        st.session_state.pop("sb_access_token", None)
        st.session_state.pop("sb_refresh_token", None)
        return None


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
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    return "#111111" if brightness > 160 else "#FFFFFF"


def rgba_from_hex(hex_color, alpha):
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


# =========================================
# 本文処理
# =========================================


def strip_html_tags(text):
    if not text:
        return ""

    text = re.sub(
        r"<br\s*/?>",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"</p>",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text,
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

    index = text.lower().find(keyword.lower())

    if index == -1:
        return text[:max_length - 1] + "…"

    half = max_length // 2
    start = max(0, index - half)
    end = min(len(text), start + max_length)

    if end - start < max_length:
        start = max(0, end - max_length)

    excerpt = text[start:end]

    if start > 0:
        excerpt = "…" + excerpt

    if end < len(text):
        excerpt += "…"

    return excerpt


def preview_style(length_value):
    if length_value == 16:
        return {"font_size": 10, "height": 40}

    if length_value == 18:
        return {"font_size": 9.5, "height": 42}

    return {"font_size": 8.5, "height": 44}


def format_japanese_date(date_string):
    return datetime.strptime(
        date_string,
        "%Y-%m-%d",
    ).strftime("%Y年%m月%d日")


# =========================================
# Supabase 日記データ
# =========================================


def get_diary(client, user_id, diary_date):
    response = (
        client.table("diaries")
        .select("content")
        .eq("user_id", user_id)
        .eq("diary_date", diary_date)
        .limit(1)
        .execute()
    )

    if response.data:
        return response.data[0]["content"]

    return ""


def get_all_diaries(client, user_id):
    response = (
        client.table("diaries")
        .select("diary_date, content")
        .eq("user_id", user_id)
        .order("diary_date", desc=False)
        .execute()
    )

    return response.data or []


def save_diary(client, user_id, diary_date, content):
    existing = (
        client.table("diaries")
        .select("id")
        .eq("user_id", user_id)
        .eq("diary_date", diary_date)
        .limit(1)
        .execute()
    )

    now = datetime.now(timezone.utc).isoformat()

    if existing.data:
        diary_id = existing.data[0]["id"]

        (
            client.table("diaries")
            .update({
                "content": content,
                "updated_at": now,
            })
            .eq("id", diary_id)
            .execute()
        )

    else:
        (
            client.table("diaries")
            .insert({
                "user_id": user_id,
                "diary_date": diary_date,
                "content": content,
                "updated_at": now,
            })
            .execute()
        )


def delete_diary(client, user_id, diary_date):
    (
        client.table("diaries")
        .delete()
        .eq("user_id", user_id)
        .eq("diary_date", diary_date)
        .execute()
    )


def search_diaries(client, user_id, keyword):
    if not keyword:
        return []

    response = (
        client.table("diaries")
        .select("diary_date, content")
        .eq("user_id", user_id)
        .ilike("content", f"%{keyword}%")
        .order("diary_date", desc=True)
        .limit(100)
        .execute()
    )

    return response.data or []


# =========================================
# Supabase ユーザー設定
# =========================================


def get_user_settings(client, user_id):
    defaults = {
        "main_color": DEFAULT_MAIN_COLOR,
        "background_color": DEFAULT_BACKGROUND_COLOR,
        "preview_length": DEFAULT_PREVIEW_LENGTH,
    }

    response = (
        client.table("user_settings")
        .select("main_color, background_color, preview_length")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return defaults

    row = response.data[0]

    try:
        preview_length = int(row.get("preview_length", DEFAULT_PREVIEW_LENGTH))
    except (TypeError, ValueError):
        preview_length = DEFAULT_PREVIEW_LENGTH

    if preview_length not in PREVIEW_LENGTH_OPTIONS:
        preview_length = DEFAULT_PREVIEW_LENGTH

    return {
        "main_color": row.get("main_color") or DEFAULT_MAIN_COLOR,
        "background_color": row.get("background_color") or DEFAULT_BACKGROUND_COLOR,
        "preview_length": preview_length,
    }


def save_user_settings(
    client,
    user_id,
    main_color,
    background_color,
    preview_length,
):
    (
        client.table("user_settings")
        .upsert({
            "user_id": user_id,
            "main_color": main_color,
            "background_color": background_color,
            "preview_length": int(preview_length),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .execute()
    )


# =========================================
# 表示用パーツ
# =========================================


def render_page_hero(icon, title):
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-hero-title">{icon} {title}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_tag(text):
    st.markdown(
        f'<div class="section-tag">{text}</div>',
        unsafe_allow_html=True,
    )


def render_date_chip(text):
    st.markdown(
        f'<div class="date-chip">{text}</div>',
        unsafe_allow_html=True,
    )


# =========================================
# 共通CSS
# =========================================


def inject_app_css(main_color, background_color):
    main_text_color = text_color_for_background(main_color)
    background_text_color = text_color_for_background(background_color)
    light_main_color = rgba_from_hex(main_color, 0.12)
    medium_main_color = rgba_from_hex(main_color, 0.28)
    strong_main_color = rgba_from_hex(main_color, 0.82)

    st.markdown(
        f"""
        <style>
        html, body {{
            background-color: {background_color};
        }}

        [data-testid="stAppViewContainer"] {{
            background-color: {background_color};
        }}

        .block-container {{
            max-width: 980px;
            padding-top: 2.7rem;
            padding-bottom: 4rem;
        }}

        .block-container,
        .block-container p,
        .block-container label,
        .block-container h1,
        .block-container h2,
        .block-container h3 {{
            color: {background_text_color};
        }}

        section[data-testid="stSidebar"] {{
            background-color: {background_color};
            border-right: 2px solid {medium_main_color};
        }}

        section[data-testid="stSidebar"] h1 {{
            border-left: 5px solid {main_color};
            padding-left: 10px;
            color: {background_text_color};
        }}

        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] label {{
            color: {background_text_color};
        }}

        section[data-testid="stSidebar"]
        div[role="radiogroup"] label {{
            padding: 0.52rem 0.65rem;
            border-radius: 10px;
        }}

        section[data-testid="stSidebar"]
        div[role="radiogroup"]
        label:has(input:checked) {{
            background-color: {main_color};
        }}

        section[data-testid="stSidebar"]
        div[role="radiogroup"]
        label:has(input:checked) p {{
            color: {main_text_color} !important;
            font-weight: 700;
        }}

        .page-hero {{
            background: linear-gradient(135deg, {main_color}, {strong_main_color});
            color: {main_text_color};
            padding: 26px 28px;
            border-radius: 20px;
            margin-bottom: 18px;
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.10);
        }}

        .page-hero-title {{
            font-size: 42px;
            font-weight: 800;
            line-height: 1.2;
            color: {main_text_color};
        }}

        .date-chip {{
            display: inline-block;
            background-color: #FFFFFF;
            color: {main_color};
            border: 2px solid {medium_main_color};
            padding: 9px 15px;
            border-radius: 999px;
            font-weight: 700;
            margin: 2px 0 16px 0;
        }}

        .section-tag {{
            display: inline-block;
            background-color: {main_color};
            color: {main_text_color};
            padding: 8px 15px;
            border-radius: 999px;
            font-weight: 700;
            font-size: 15px;
            margin: 5px 0 10px 0;
        }}

        .selected-diary-title {{
            font-size: 34px;
            font-weight: 800;
            color: {background_text_color};
            margin: 8px 0 12px 0;
        }}

        div[data-testid="stButton"] button[kind="primary"],
        div[data-testid="stFormSubmitButton"] button[kind="primary"] {{
            background-color: {main_color} !important;
            border: 3px solid {main_color} !important;
            color: {main_text_color} !important;
            border-radius: 15px !important;
            min-height: 60px !important;
            padding: 10px 22px !important;
            font-size: 18px !important;
            font-weight: 900 !important;
            box-shadow: 0 6px 15px rgba(0, 0, 0, 0.12);
        }}

        div[data-testid="stButton"] button[kind="primary"] p,
        div[data-testid="stFormSubmitButton"] button[kind="primary"] p {{
            color: {main_text_color} !important;
            font-size: 18px !important;
            font-weight: 900 !important;
        }}

        div[data-testid="stButton"] button[kind="primary"]:hover,
        div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {{
            background-color: {main_color} !important;
            border-color: {main_color} !important;
            color: {main_text_color} !important;
            opacity: 0.86;
        }}

        div[data-testid="stButton"] button[kind="secondary"] {{
            background-color: #FFFFFF !important;
            border: 2px solid #D0D0D0 !important;
            color: #222222 !important;
            border-radius: 14px !important;
            min-height: 52px !important;
            font-size: 16px !important;
            font-weight: 800 !important;
        }}

        div[data-testid="stButton"] button[kind="secondary"] p {{
            color: #222222 !important;
            font-weight: 800 !important;
        }}

        div[data-testid="stButton"] button[kind="tertiary"] {{
            background-color: #D93025 !important;
            border: 3px solid #D93025 !important;
            color: #FFFFFF !important;
            border-radius: 15px !important;
            min-height: 58px !important;
            font-size: 17px !important;
            font-weight: 900 !important;
        }}

        div[data-testid="stButton"] button[kind="tertiary"] p {{
            color: #FFFFFF !important;
            font-weight: 900 !important;
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] {{
            border: 2px solid {medium_main_color} !important;
            border-radius: 16px !important;
            background-color: rgba(255, 255, 255, 0.88) !important;
            box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
        }}

        div[data-testid="stVerticalBlockBorderWrapper"] p,
        div[data-testid="stVerticalBlockBorderWrapper"] label,
        div[data-testid="stVerticalBlockBorderWrapper"] h2,
        div[data-testid="stVerticalBlockBorderWrapper"] h3 {{
            color: #222222 !important;
        }}

        hr {{
            border-color: {medium_main_color};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    return {
        "main_text_color": main_text_color,
        "background_text_color": background_text_color,
        "light_main_color": light_main_color,
        "medium_main_color": medium_main_color,
        "strong_main_color": strong_main_color,
    }


# =========================================
# ログイン画面
# =========================================


def friendly_auth_error(error):
    message = str(error)
    lowered = message.lower()

    if "invalid login credentials" in lowered:
        return "メールアドレスまたはパスワードが違います。"

    if "email not confirmed" in lowered:
        return "メール確認がまだ完了していません。確認メールのリンクを開いてください。"

    if "user already registered" in lowered:
        return "このメールアドレスはすでに登録されています。"

    if "password" in lowered and "least" in lowered:
        return "パスワードが短すぎます。6文字以上で設定してください。"

    if "rate limit" in lowered:
        return "短時間に操作が集中しています。少し時間をおいてから試してください。"

    return f"処理に失敗しました。\n\n{message}"


def render_auth_page(client):
    inject_app_css(
        DEFAULT_MAIN_COLOR,
        DEFAULT_BACKGROUND_COLOR,
    )

    render_page_hero("📖", "日記アプリ")
    render_section_tag("🔐 ログイン")

    login_tab, signup_tab = st.tabs([
        "ログイン",
        "新規登録",
    ])

    with login_tab:
        with st.form("login_form"):
            login_email = st.text_input(
                "メールアドレス",
                placeholder="example@email.com",
                key="login_email",
            )

            login_password = st.text_input(
                "パスワード",
                type="password",
                key="login_password",
            )

            login_submitted = st.form_submit_button(
                "ログイン",
                type="primary",
                use_container_width=True,
            )

        if login_submitted:
            if not login_email.strip() or not login_password:
                st.warning("メールアドレスとパスワードを入力してください。")
            else:
                try:
                    response = client.auth.sign_in_with_password({
                        "email": login_email.strip(),
                        "password": login_password,
                    })

                    session = get_session_from_response(response)

                    if session is None:
                        st.error("ログイン情報を取得できませんでした。")
                    else:
                        save_auth_session(session)
                        st.rerun()

                except Exception as error:
                    st.error(friendly_auth_error(error))

    with signup_tab:
        with st.form("signup_form"):
            signup_email = st.text_input(
                "メールアドレス",
                placeholder="example@email.com",
                key="signup_email",
            )

            signup_password = st.text_input(
                "パスワード",
                type="password",
                help="6文字以上で設定してください。",
                key="signup_password",
            )

            signup_password_confirm = st.text_input(
                "パスワードをもう一度入力",
                type="password",
                key="signup_password_confirm",
            )

            signup_submitted = st.form_submit_button(
                "新規登録する",
                type="primary",
                use_container_width=True,
            )

        if signup_submitted:
            email = signup_email.strip()

            if not email or not signup_password:
                st.warning("メールアドレスとパスワードを入力してください。")

            elif len(signup_password) < 6:
                st.warning("パスワードは6文字以上にしてください。")

            elif signup_password != signup_password_confirm:
                st.warning("2つのパスワードが一致していません。")

            else:
                try:
                    response = client.auth.sign_up({
                        "email": email,
                        "password": signup_password,
                        "options": {
                            "email_redirect_to": APP_URL,
                        },
                    })

                    session = get_session_from_response(response)

                    if session is not None:
                        save_auth_session(session)
                        st.success("新規登録が完了しました。")
                        st.rerun()
                    else:
                        st.success(
                            "確認メールを送信しました。"
                            "メール内の確認リンクを開いたあと、この画面からログインしてください。"
                        )

                except Exception as error:
                    st.error(friendly_auth_error(error))

    st.caption(
        "日記はログインしたユーザーごとに分けて保存されます。"
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

    <div class="editor-submit-area">
        <button id="editor-submit" type="button" class="editor-submit-button">
            保存する
        </button>
    </div>
</div>
"""


def build_editor_css(main_color):
    light_main = rgba_from_hex(main_color, 0.12)
    medium_main = rgba_from_hex(main_color, 0.28)

    return f"""
@import url('https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.snow.css');
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;700&family=Noto+Serif+JP:wght@400;700&display=swap');

.editor-wrapper {{
    width: 100%;
    height: 100%;
    background: #FFFFFF;
    border: 3px solid {main_color};
    border-radius: 16px;
    overflow: hidden;
    box-sizing: border-box;
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
}}

#toolbar {{
    background-color: {light_main};
    border: none !important;
    border-bottom: 2px solid {medium_main} !important;
}}

#editor {{
    min-height: 340px;
    background: #FFFFFF;
    border: none !important;
}}

.ql-editor {{
    min-height: 340px;
    padding: 18px;
    font-size: 16px;
    color: #222222;
    font-family: "Noto Sans JP", sans-serif;
}}

.ql-toolbar button.ql-active {{
    color: {main_color};
}}

.ql-toolbar button.ql-active .ql-stroke {{
    stroke: {main_color};
}}

.ql-picker.ql-size {{ width: 70px; }}
.ql-picker.ql-font {{ width: 145px; }}

.ql-font-noto-sans-jp {{ font-family: "Noto Sans JP", sans-serif; }}
.ql-font-noto-serif-jp {{ font-family: "Noto Serif JP", serif; }}
.ql-font-yu-gothic {{ font-family: "Yu Gothic", "YuGothic", sans-serif; }}
.ql-font-meiryo {{ font-family: "Meiryo", sans-serif; }}

.ql-picker.ql-size .ql-picker-label::before,
.ql-picker.ql-size .ql-picker-item::before {{
    content: attr(data-value);
}}

.ql-picker.ql-size .ql-picker-label[data-value="10px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="10px"]::before {{ content: "10"; }}
.ql-picker.ql-size .ql-picker-label[data-value="12px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="12px"]::before {{ content: "12"; }}
.ql-picker.ql-size .ql-picker-label[data-value="14px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="14px"]::before {{ content: "14"; }}
.ql-picker.ql-size .ql-picker-label[data-value="16px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="16px"]::before {{ content: "16"; }}
.ql-picker.ql-size .ql-picker-label[data-value="18px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="18px"]::before {{ content: "18"; }}
.ql-picker.ql-size .ql-picker-label[data-value="20px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="20px"]::before {{ content: "20"; }}
.ql-picker.ql-size .ql-picker-label[data-value="24px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="24px"]::before {{ content: "24"; }}
.ql-picker.ql-size .ql-picker-label[data-value="28px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="28px"]::before {{ content: "28"; }}
.ql-picker.ql-size .ql-picker-label[data-value="32px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="32px"]::before {{ content: "32"; }}
.ql-picker.ql-size .ql-picker-label[data-value="36px"]::before,
.ql-picker.ql-size .ql-picker-item[data-value="36px"]::before {{ content: "36"; }}

.ql-picker.ql-font .ql-picker-label[data-value="noto-sans-jp"]::before,
.ql-picker.ql-font .ql-picker-item[data-value="noto-sans-jp"]::before {{ content: "Noto Sans JP"; }}
.ql-picker.ql-font .ql-picker-label[data-value="noto-serif-jp"]::before,
.ql-picker.ql-font .ql-picker-item[data-value="noto-serif-jp"]::before {{ content: "Noto Serif JP"; }}
.ql-picker.ql-font .ql-picker-label[data-value="yu-gothic"]::before,
.ql-picker.ql-font .ql-picker-item[data-value="yu-gothic"]::before {{ content: "游ゴシック"; }}
.ql-picker.ql-font .ql-picker-label[data-value="meiryo"]::before,
.ql-picker.ql-font .ql-picker-item[data-value="meiryo"]::before {{ content: "メイリオ"; }}

.editor-submit-area {{
    padding: 14px 0 0 0;
    background: transparent;
}}

.editor-submit-button {{
    width: 100%;
    min-height: 58px;
    border: 3px solid {main_color};
    border-radius: 15px;
    background: {main_color};
    color: {text_color_for_background(main_color)};
    font-size: 18px;
    font-weight: 900;
    cursor: pointer;
    box-shadow: 0 6px 15px rgba(0, 0, 0, 0.12);
}}

.editor-submit-button:hover {{
    opacity: 0.86;
}}

.editor-submit-button:disabled {{
    cursor: wait;
    opacity: 0.72;
}}
"""


EDITOR_JS = """
export default async function(component) {
    const { parentElement, data, setTriggerValue } = component;

    if (!window.Quill) {
        await new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://cdn.jsdelivr.net/npm/quill@2.0.3/dist/quill.js";
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    const Quill = window.Quill;

    const SizeStyle = Quill.import("attributors/style/size");
    SizeStyle.whitelist = [
        "10px", "12px", "14px", "16px", "18px",
        "20px", "24px", "28px", "32px", "36px"
    ];
    Quill.register(SizeStyle, true);

    const FontClass = Quill.import("attributors/class/font");
    FontClass.whitelist = [
        "noto-sans-jp", "noto-serif-jp", "yu-gothic", "meiryo"
    ];
    Quill.register(FontClass, true);

    const editorElement = parentElement.querySelector("#editor");
    const submitButton = parentElement.querySelector("#editor-submit");
    const buttonLabel = data?.buttonLabel ?? "保存する";

    submitButton.textContent = buttonLabel;
    submitButton.disabled = false;

    if (!editorElement.__quill) {
        const quill = new Quill(editorElement, {
            theme: "snow",
            modules: {
                toolbar: parentElement.querySelector("#toolbar")
            }
        });

        editorElement.__quill = quill;

        const initialValue = data?.value ?? "";
        if (initialValue) {
            quill.clipboard.dangerouslyPasteHTML(initialValue);
        }

        submitButton.addEventListener("click", function () {
            const html = quill.root.innerHTML;
            const submissionId = `${Date.now()}-${Math.random()}`;

            submitButton.disabled = true;
            submitButton.textContent = "保存中...";

            setTriggerValue(
                "submission",
                JSON.stringify({
                    id: submissionId,
                    value: html
                })
            );
        });

    } else {
        const quill = editorElement.__quill;
        const newValue = data?.value ?? "";

        if (
            document.activeElement !== quill.root &&
            quill.root.innerHTML !== newValue &&
            !editorElement.__hasUnsavedChanges
        ) {
            quill.clipboard.dangerouslyPasteHTML(newValue);
        }
    }

    const quill = editorElement.__quill;

    if (!editorElement.__changeTrackingAttached) {
        quill.on("text-change", function () {
            editorElement.__hasUnsavedChanges = true;
        });
        editorElement.__changeTrackingAttached = true;
    }

}
"""


def build_rich_editor(main_color):
    return st.components.v2.component(
        "diary_rich_editor_manual_save_v2",
        html=EDITOR_HTML,
        css=build_editor_css(main_color),
        js=EDITOR_JS,
    )


def rich_editor(
    component_factory,
    value="",
    key=None,
    button_label="保存する",
):
    result = component_factory(
        data={
            "value": value,
            "buttonLabel": button_label,
        },
        on_submission_change=lambda: None,
        key=key,
        height=530,
        width="stretch",
    )

    submission_raw = getattr(result, "submission", "") or ""

    if not submission_raw:
        return None

    try:
        payload = json.loads(submission_raw)
    except (TypeError, json.JSONDecodeError):
        return None

    submission_id = str(payload.get("id", ""))
    submitted_value = payload.get("value", "")

    if not submission_id:
        return None

    processed_key = f"{key}_processed_submission"

    if st.session_state.get(processed_key) == submission_id:
        return None

    st.session_state[processed_key] = submission_id
    return submitted_value



# =========================================
# Supabaseクライアントとログイン状態
# =========================================

supabase = create_supabase_client()
current_user = restore_logged_in_user(supabase)

if current_user is None:
    render_auth_page(supabase)
    st.stop()

user_id = str(current_user.id)
user_email = getattr(current_user, "email", "") or ""


# =========================================
# ユーザー設定読み込み
# =========================================

try:
    settings = get_user_settings(
        supabase,
        user_id,
    )
except Exception as error:
    st.error(
        "Supabaseから設定を読み込めませんでした。"
        "テーブル・RLS・API権限を確認してください。"
    )
    st.code(str(error))
    st.stop()

main_color = settings["main_color"]
background_color = settings["background_color"]
preview_length = settings["preview_length"]
preview_ui = preview_style(preview_length)

colors = inject_app_css(
    main_color,
    background_color,
)

main_text_color = colors["main_text_color"]
light_main_color = colors["light_main_color"]
medium_main_color = colors["medium_main_color"]

rich_editor_component = build_rich_editor(main_color)


# =========================================
# サイドバー
# =========================================

st.sidebar.title("📖 日記アプリ")

if user_email:
    st.sidebar.caption(f"👤 {user_email}")

page = st.sidebar.radio(
    "画面を選択",
    [
        "✏️ 今日の日記",
        "📅 日記を見る",
        "🔍 日記を検索",
        "⚙️ 設定",
    ],
)

st.sidebar.divider()

if st.sidebar.button(
    "ログアウト",
    type="secondary",
    use_container_width=True,
):
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    clear_auth_state()
    st.rerun()


# =========================================
# 今日の日記
# =========================================

if page == "✏️ 今日の日記":
    today = date.today().isoformat()

    render_page_hero("✏️", "今日の日記")
    render_date_chip(
        f"📅 {datetime.today().strftime('%Y年%m月%d日')}"
    )
    render_section_tag("✍️ 今日の記録")

    try:
        current_diary = get_diary(
            supabase,
            user_id,
            today,
        )
    except Exception as error:
        st.error("日記を読み込めませんでした。")
        st.code(str(error))
        st.stop()

    submitted_content = rich_editor(
        rich_editor_component,
        value=current_diary,
        key=f"today_editor_{user_id}_{today}",
        button_label="保存する",
    )

    if submitted_content is not None:
        if not strip_html_tags(submitted_content):
            st.warning("日記が入力されていません。")
        else:
            try:
                save_diary(
                    supabase,
                    user_id,
                    today,
                    submitted_content,
                )
                st.success("日記を保存しました！")
            except Exception as error:
                st.error("日記の保存に失敗しました。")
                st.code(str(error))


# =========================================
# 日記を見る
# =========================================

elif page == "📅 日記を見る":
    render_page_hero("📅", "日記を見る")
    render_section_tag("🗓️ カレンダー")

    try:
        diaries = get_all_diaries(
            supabase,
            user_id,
        )
    except Exception as error:
        st.error("日記一覧を読み込めませんでした。")
        st.code(str(error))
        st.stop()

    events = []

    for diary_row in diaries:
        diary_date = diary_row["diary_date"]
        diary_content = diary_row["content"]

        events.append({
            "title": make_diary_preview(
                diary_content,
                preview_length,
            ),
            "start": diary_date,
            "allDay": True,
            "backgroundColor": main_color,
            "borderColor": main_color,
            "textColor": main_text_color,
        })

    calendar_options = {
        "initialView": "dayGridMonth",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "",
        },
        "locale": "ja",
        "height": 620,
    }

    calendar_custom_css = f"""
    .fc {{
        background: #FFFFFF;
        border: 3px solid {main_color};
        border-radius: 16px;
        padding: 12px;
        box-sizing: border-box;
        font-size: 14px;
    }}

    .fc .fc-toolbar.fc-header-toolbar {{
        background: {light_main_color};
        border: 1px solid {medium_main_color};
        border-radius: 12px;
        padding: 10px 12px;
        margin-bottom: 12px;
    }}

    .fc .fc-toolbar-title {{
        color: #111111;
        font-size: 26px !important;
        font-weight: 900;
    }}

    .fc .fc-button-primary {{
        background-color: {main_color} !important;
        border-color: {main_color} !important;
        color: {main_text_color} !important;
        border-radius: 7px !important;
    }}

    .fc .fc-button-primary:hover {{
        opacity: 0.86;
    }}

    .fc .fc-button {{
        font-size: 14px !important;
        font-weight: 800 !important;
        padding: 7px 11px !important;
    }}

    .fc .fc-col-header-cell {{
        background: {light_main_color};
    }}

    .fc .fc-col-header-cell-cushion {{
        font-size: 15px;
        font-weight: 800;
        padding: 8px 0;
    }}

    .fc .fc-daygrid-day-number {{
        font-size: 16px;
        font-weight: 900;
        padding: 6px 7px;
    }}

    .fc .fc-col-header-cell.fc-day-sun {{
        background-color: #FFEAEA !important;
    }}

    .fc .fc-col-header-cell.fc-day-sun .fc-col-header-cell-cushion {{
        color: #D93025 !important;
    }}

    .fc .fc-daygrid-day.fc-day-sun {{
        background-color: #FFF5F5 !important;
    }}

    .fc .fc-daygrid-day.fc-day-sun .fc-daygrid-day-number {{
        color: #D93025 !important;
    }}

    .fc .fc-col-header-cell.fc-day-sat {{
        background-color: #EAF3FF !important;
    }}

    .fc .fc-col-header-cell.fc-day-sat .fc-col-header-cell-cushion {{
        color: #1A73E8 !important;
    }}

    .fc .fc-daygrid-day.fc-day-sat {{
        background-color: #F3F8FF !important;
    }}

    .fc .fc-daygrid-day.fc-day-sat .fc-daygrid-day-number {{
        color: #1A73E8 !important;
    }}

    .fc .fc-day-today {{
        box-shadow: inset 0 0 0 2px {main_color};
        position: relative;
    }}

    .fc .fc-daygrid-event {{
        width: calc(100% - 4px) !important;
        max-width: calc(100% - 4px) !important;
        margin-left: 2px !important;
        margin-right: 2px !important;
        margin-top: 2px !important;
        height: {preview_ui['height']}px;
        min-height: {preview_ui['height']}px;
        max-height: {preview_ui['height']}px;
        border-radius: 7px;
        overflow: hidden !important;
        box-sizing: border-box;
    }}

    .fc .fc-event-main,
    .fc .fc-event-main-frame,
    .fc .fc-event-title-container {{
        width: 100%;
        height: 100%;
        overflow: hidden !important;
    }}

    .fc .fc-event-title {{
        display: -webkit-box !important;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        padding: 3px 4px;
        font-size: {preview_ui['font_size']}px !important;
        font-weight: 700;
        line-height: 1.3;
        white-space: normal !important;
        overflow: hidden !important;
        word-break: break-all;
        overflow-wrap: anywhere;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
        line-clamp: 2;
    }}

    .fc-theme-standard td,
    .fc-theme-standard th {{
        border-color: {medium_main_color};
    }}
    """

    calendar_left, calendar_center, calendar_right = st.columns(
        [0.08, 0.84, 0.08],
        gap="small",
    )

    with calendar_center:
        calendar_result = calendar(
            events=events,
            options=calendar_options,
            custom_css=calendar_custom_css,
            key=(
                f"diary_calendar_{user_id}_"
                f"{preview_length}_{main_color}"
            ),
        )

    if calendar_result and calendar_result.get("eventClick"):
        clicked_event = calendar_result["eventClick"]
        clicked_date = clicked_event["event"]["start"]

        st.session_state["selected_date"] = clicked_date
        st.session_state.pop("delete_confirm_date", None)

    if "selected_date" in st.session_state:
        selected_date = st.session_state["selected_date"]

        try:
            selected_diary = get_diary(
                supabase,
                user_id,
                selected_date,
            )
        except Exception as error:
            st.error("選択した日記を読み込めませんでした。")
            st.code(str(error))
            st.stop()

        st.divider()
        render_section_tag("📖 選択した日記")

        st.markdown(
            f"""
            <div class="selected-diary-title">
                {format_japanese_date(selected_date)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if selected_diary:
            submitted_edit_content = rich_editor(
                rich_editor_component,
                value=selected_diary,
                key=f"edit_{user_id}_{selected_date}",
                button_label="更新する",
            )

            if submitted_edit_content is not None:
                if not strip_html_tags(submitted_edit_content):
                    st.warning("日記が入力されていません。")
                else:
                    try:
                        save_diary(
                            supabase,
                            user_id,
                            selected_date,
                            submitted_edit_content,
                        )
                        st.success("日記を更新しました！")
                    except Exception as error:
                        st.error("日記の更新に失敗しました。")
                        st.code(str(error))

            st.write("")

            if st.button(
                "削除する",
                type="primary",
                use_container_width=True,
                key=f"delete_{selected_date}",
            ):
                st.session_state["delete_confirm_date"] = selected_date

            if st.session_state.get("delete_confirm_date") == selected_date:
                st.warning(
                    "この日記を削除します。削除後は元に戻せません。"
                )

                confirm_column, cancel_column = st.columns(
                    [1, 1],
                    gap="medium",
                )

                with confirm_column:
                    if st.button(
                        "本当に削除する",
                        type="tertiary",
                        use_container_width=True,
                        key=f"confirm_delete_{selected_date}",
                    ):
                        try:
                            delete_diary(
                                supabase,
                                user_id,
                                selected_date,
                            )

                            st.session_state.pop("selected_date", None)
                            st.session_state.pop("delete_confirm_date", None)
                            st.session_state.pop(
                                f"edit_{user_id}_{selected_date}",
                                None,
                            )
                            st.rerun()

                        except Exception as error:
                            st.error("日記の削除に失敗しました。")
                            st.code(str(error))

                with cancel_column:
                    if st.button(
                        "キャンセル",
                        type="secondary",
                        use_container_width=True,
                        key=f"cancel_delete_{selected_date}",
                    ):
                        st.session_state.pop("delete_confirm_date", None)
                        st.rerun()

        else:
            st.info("この日には日記がありません。")


# =========================================
# 日記検索
# =========================================

elif page == "🔍 日記を検索":
    render_page_hero("🔍", "日記を検索")
    render_section_tag("🔎 キーワード検索")

    with st.form(
        "diary_search_form",
        clear_on_submit=False,
    ):
        search_keyword = st.text_input(
            "検索する言葉",
            placeholder="例：旅行、仕事、嬉しかったこと",
            key="diary_search_keyword",
        )

        st.write("")

        search_submitted = st.form_submit_button(
            "検索する",
            type="primary",
            use_container_width=True,
        )

    if search_submitted:
        cleaned_keyword = search_keyword.strip()

        if cleaned_keyword:
            previous_query = st.session_state.get(
                "active_search_query",
                "",
            )

            st.session_state["active_search_query"] = cleaned_keyword

            if previous_query != cleaned_keyword:
                st.session_state.pop("search_selected_date", None)
                st.session_state.pop("search_delete_confirm_date", None)
        else:
            st.session_state.pop("active_search_query", None)
            st.session_state.pop("search_selected_date", None)
            st.warning("検索する言葉を入力してください。")

    active_search_query = st.session_state.get(
        "active_search_query",
        "",
    )

    if active_search_query:
        try:
            search_results = search_diaries(
                supabase,
                user_id,
                active_search_query,
            )
        except Exception as error:
            st.error("検索に失敗しました。")
            st.code(str(error))
            search_results = []

        st.write("")
        render_section_tag(
            f"📚 検索結果 {len(search_results)}件"
        )

        if search_results:
            for result in search_results:
                diary_date = result["diary_date"]
                diary_content = result["content"]

                with st.container(border=True):
                    st.subheader(
                        format_japanese_date(diary_date)
                    )

                    st.write(
                        make_search_excerpt(
                            diary_content,
                            active_search_query,
                            70,
                        )
                    )

                    if st.button(
                        "この日記を開く",
                        type="secondary",
                        use_container_width=True,
                        key=f"open_search_{diary_date}",
                    ):
                        st.session_state["search_selected_date"] = diary_date
                        st.session_state.pop(
                            "search_delete_confirm_date",
                            None,
                        )
        else:
            st.info(
                f"「{active_search_query}」を含む日記は見つかりませんでした。"
            )

    if "search_selected_date" in st.session_state:
        search_selected_date = st.session_state["search_selected_date"]

        try:
            search_selected_diary = get_diary(
                supabase,
                user_id,
                search_selected_date,
            )
        except Exception as error:
            st.error("日記を読み込めませんでした。")
            st.code(str(error))
            search_selected_diary = ""

        if search_selected_diary:
            st.divider()
            render_section_tag("📖 検索した日記")

            st.markdown(
                f"""
                <div class="selected-diary-title">
                    {format_japanese_date(search_selected_date)}
                </div>
                """,
                unsafe_allow_html=True,
            )

            submitted_search_edit_content = rich_editor(
                rich_editor_component,
                value=search_selected_diary,
                key=f"search_edit_{user_id}_{search_selected_date}",
                button_label="更新する",
            )

            if submitted_search_edit_content is not None:
                if not strip_html_tags(submitted_search_edit_content):
                    st.warning("日記が入力されていません。")
                else:
                    try:
                        save_diary(
                            supabase,
                            user_id,
                            search_selected_date,
                            submitted_search_edit_content,
                        )
                        st.success("日記を更新しました！")
                    except Exception as error:
                        st.error("日記の更新に失敗しました。")
                        st.code(str(error))

            st.write("")

            if st.button(
                "削除する",
                type="primary",
                use_container_width=True,
                key=f"search_delete_{search_selected_date}",
            ):
                st.session_state[
                    "search_delete_confirm_date"
                ] = search_selected_date

            if (
                st.session_state.get("search_delete_confirm_date")
                == search_selected_date
            ):
                st.warning(
                    "この日記を削除します。削除後は元に戻せません。"
                )

                search_confirm_column, search_cancel_column = st.columns(
                    [1, 1],
                    gap="medium",
                )

                with search_confirm_column:
                    if st.button(
                        "本当に削除する",
                        type="tertiary",
                        use_container_width=True,
                        key=f"search_confirm_delete_{search_selected_date}",
                    ):
                        try:
                            delete_diary(
                                supabase,
                                user_id,
                                search_selected_date,
                            )

                            st.session_state.pop("search_selected_date", None)
                            st.session_state.pop(
                                "search_delete_confirm_date",
                                None,
                            )
                            st.session_state.pop(
                                f"search_edit_{user_id}_{search_selected_date}",
                                None,
                            )
                            st.rerun()

                        except Exception as error:
                            st.error("日記の削除に失敗しました。")
                            st.code(str(error))

                with search_cancel_column:
                    if st.button(
                        "キャンセル",
                        type="secondary",
                        use_container_width=True,
                        key=f"search_cancel_delete_{search_selected_date}",
                    ):
                        st.session_state.pop(
                            "search_delete_confirm_date",
                            None,
                        )
                        st.rerun()
        else:
            st.session_state.pop("search_selected_date", None)


# =========================================
# 設定
# =========================================

elif page == "⚙️ 設定":
    render_page_hero("⚙️", "設定")
    render_section_tag("🎨 カラー設定")

    with st.container(border=True):
        st.subheader("メインカラー")
        selected_main_color = st.color_picker(
            "メインカラーを選択",
            value=main_color,
            key="main_color_picker",
        )

    st.write("")

    with st.container(border=True):
        st.subheader("背景カラー")
        selected_background_color = st.color_picker(
            "背景カラーを選択",
            value=background_color,
            key="background_color_picker",
        )

    st.write("")
    render_section_tag("🗓️ カレンダー設定")

    with st.container(border=True):
        st.subheader("日記プレビュー")

        current_preview_index = PREVIEW_LENGTH_OPTIONS.index(
            preview_length
        )

        selected_preview_length = st.selectbox(
            "カレンダーに表示する文章の長さ",
            options=PREVIEW_LENGTH_OPTIONS,
            index=current_preview_index,
            format_func=lambda value: f"{value}文字",
            key="preview_length_select",
        )

        example_text = (
            "今日はアプリ開発をしてカレンダーを改善した。"
        )

        st.caption(
            "表示例："
            + make_diary_preview(
                example_text,
                selected_preview_length,
            )
        )

    st.write("")

    if st.button(
        "設定を保存する",
        type="primary",
        use_container_width=True,
    ):
        try:
            save_user_settings(
                supabase,
                user_id,
                selected_main_color,
                selected_background_color,
                selected_preview_length,
            )

            st.success("設定を保存しました！")
            st.rerun()

        except Exception as error:
            st.error("設定の保存に失敗しました。")
            st.code(str(error))
