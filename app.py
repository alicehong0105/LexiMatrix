import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import plotly.graph_objects as go
import re
import base64

# ============================================================
# 1. 頁面設定
# ============================================================
st.set_page_config(page_title="Qurate Pro", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        [data-testid="stHeader"] { background: rgba(0,0,0,0); height: 3rem !important; }
        .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; }
        footer { visibility: hidden; }
        .main-title { color: #2d3436; font-weight: 800; font-size: 2.2rem; margin-bottom: 1rem; }
        .stButton > button { width: 100%; border-radius: 12px; height: 3.2rem; background: #2d3436; color: white; font-weight: bold; border: none; }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [aria-selected="true"] { background-color: #2d3436 !important; color: white !important; border-radius: 8px; }
        .auth-card {
            max-width: 420px;
            margin: 4rem auto;
            padding: 2.5rem;
            background: white;
            border-radius: 20px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
        }
        .auth-title {
            text-align: center;
            font-size: 1.8rem;
            font-weight: 800;
            color: #2d3436;
            margin-bottom: 0.3rem;
        }
        .auth-sub {
            text-align: center;
            color: #636e72;
            margin-bottom: 1.5rem;
            font-size: 0.95rem;
        }
        .tutorial-card {
            background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
            border-radius: 20px;
            padding: 2.5rem;
            color: white;
            text-align: center;
            margin: 1rem 0;
        }
        .hint-badge {
            background: #fdcb6e;
            color: #2d3436;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: bold;
            margin: 0.5rem 0;
        }
    </style>
""", unsafe_allow_html=True)


# ============================================================
# 2. API 設定
# ============================================================
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]

def get_headers(access_token=None):
    """根據是否有 access_token 回傳對應的 headers"""
    token = access_token or KEY
    return {
        "apikey": KEY,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }


# ============================================================
# 3. Auth 函式
# ============================================================
def sign_up(email, password):
    resp = httpx.post(
        f"{URL}/auth/v1/signup",
        json={"email": email, "password": password},
        headers={"apikey": KEY, "Content-Type": "application/json"}
    )
    return resp.json()

def sign_in(email, password):
    resp = httpx.post(
        f"{URL}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers={"apikey": KEY, "Content-Type": "application/json"}
    )
    return resp.json()

def sign_out(access_token):
    httpx.post(
        f"{URL}/auth/v1/logout",
        headers={"apikey": KEY, "Authorization": f"Bearer {access_token}"}
    )


# ============================================================
# 4. 工具函式
# ============================================================
def get_ebbinghaus_date(mastery):
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    days = curve.get(mastery, 1)
    return (date.today() + timedelta(days=days)).strftime('%Y-%m-%d')

def empty_to_none(v):
    return v if v and v.strip() else None

def parse_other_forms(raw):
    if isinstance(raw, list):
        parts = raw
    elif isinstance(raw, str) and raw:
        parts = [p.strip() for p in raw.replace('{', '').replace('}', '').split('/')]
    else:
        parts = []
    while len(parts) < 3:
        parts.append("")
    return parts[:3]

def calculate_new_mastery(current_mastery, penalty=2):
    if current_mastery < 2:
        return 0
    return current_mastery - penalty

def load_data(access_token):
    """載入目前登入用戶的單字（RLS 自動過濾）"""
    try:
        resp = httpx.get(
            f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc",
            headers=get_headers(access_token)
        )
        return resp.json()
    except Exception:
        return []

def update_mastery_in_db(word_id, new_mastery, access_token):
    httpx.patch(
        f"{URL}/rest/v1/vocabulary?id=eq.{word_id}",
        json={"mastery": new_mastery, "next_review": get_ebbinghaus_date(new_mastery)},
        headers=get_headers(access_token)
    )

def play_pronunciation(word: str):
    try:
        from gtts import gTTS
        tts = gTTS(text=word, lang='en', tld='co.uk')
        tts.save("/tmp/pronunciation.mp3")
        with open("/tmp/pronunciation.mp3", "rb") as f:
            audio_bytes = f.read()
        audio_b64 = base64.b64encode(audio_bytes).decode()
        audio_html = f"""
            <audio autoplay controls style="width:100%; margin-top:0.5rem;">
                <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)
    except Exception:
        st.link_button(
            f"🔊 Cambridge: {word}",
            f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{word.replace(' ', '-')}"
        )


# ============================================================
# 5. 登入／註冊頁面
# ============================================================
def show_auth_page():
    st.markdown("""
        <div class='auth-card'>
            <div class='auth-title'>⚡ Qurate Pro</div>
            <div class='auth-sub'>科學化語言學習管理系統</div>
        </div>
    """, unsafe_allow_html=True)

    # 置中顯示
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab_login, tab_signup = st.tabs(["🔑 登入", "📝 註冊"])

        with tab_login:
            email    = st.text_input("Email", key="login_email")
            password = st.text_input("密碼", type="password", key="login_pw")
            if st.button("登入", key="login_btn"):
                if email and password:
                    with st.spinner("驗證中..."):
                        result = sign_in(email, password)
                    if "access_token" in result:
                        st.session_state.access_token = result["access_token"]
                        st.session_state.user_id      = result["user"]["id"]
                        st.session_state.user_email   = result["user"]["email"]
                        st.rerun()
                    else:
                        err = result.get("error_description", "登入失敗，請確認帳號密碼")
                        st.error(err)
                else:
                    st.warning("請填寫 Email 和密碼")

        with tab_signup:
            new_email    = st.text_input("Email", key="signup_email")
            new_password = st.text_input("密碼（至少6位）", type="password", key="signup_pw")
            new_password2 = st.text_input("確認密碼", type="password", key="signup_pw2")
            if st.button("建立帳號", key="signup_btn"):
                if not new_email or not new_password:
                    st.warning("請填寫所有欄位")
                elif new_password != new_password2:
                    st.error("兩次密碼不一致")
                elif len(new_password) < 6:
                    st.error("密碼至少需要 6 個字元")
                else:
                    with st.spinner("建立帳號中..."):
                        result = sign_up(new_email, new_password)
                    if "id" in result.get("user", {}):
                        st.success("🎉 帳號建立成功！請去信箱確認驗證信，然後回來登入。")
                    else:
                        err = result.get("error_description", "註冊失敗")
                        st.error(err)


# ============================================================
# 6. 檢查登入狀態
# ============================================================
if "access_token" not in st.session_state:
    show_auth_page()
    st.stop()

# 取得目前用戶資訊
access_token = st.session_state.access_token
user_email   = st.session_state.get("user_email", "")
HEADERS      = get_headers(access_token)

# 載入資料
raw_data = load_data(access_token)
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
due_count = (
    len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()])
    if not df.empty else 0
)


# ============================================================
# 7. 側邊導航
# ============================================================
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)
st.sidebar.caption(f"👤 {user_email}")

if st.sidebar.button("🚪 登出"):
    sign_out(access_token)
    for key in ["access_token", "user_id", "user_email"]:
        st.session_state.pop(key, None)
    st.rerun()

pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio(
    "SYSTEM ACCESS",
    ["📋 Matrix Core", "🎴 Matrix Cards", pulse_label, "📅 Ebbing Log"]
)

if st.sidebar.button("🔄 Force Sync Matrix"):
    st.rerun()


# ============================================================
# 8. 頁面：Matrix Core
# ============================================================
if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize Node", "🔍 View Matrix", "📝 Modify Protocol"])

    with t_add:
        with st.form("add_matrix_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("Entry（單字）*")
            f_mean = c2.text_input("Definition（中文）*")

            st.write("---")
            st.caption("Morphology（動詞三態變化）")
            v1, v2, v3 = st.columns(3)
            f_v1 = v1.text_input("V1 (Base)")
            f_v2 = v2.text_input("V2 (Past)")
            f_v3 = v3.text_input("V3 (Participle)")

            st.write("---")
            f_pos = st.multiselect("Class（詞性）", ["n.", "v.", "adj.", "adv.", "phr.", "prep."])

            c3, c4 = st.columns(2)
            f_syn  = c3.text_input("Synonyms（同義詞）")
            f_coll = c4.text_input("Collocations（慣用搭配）")

            f_en = st.text_area("English Definition（英文定義）")
            f_ex = st.text_area("Context Example（例句）")

            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    payload = {
                        "word":        f_word.strip(),
                        "meaning_zh":  f_mean.strip(),
                        "pos":         f_pos if f_pos else [],
                        "other_forms": [f_v1, f_v2, f_v3] if f_v1 else [],
                        "synonyms":    empty_to_none(f_syn),
                        "collocations":empty_to_none(f_coll),
                        "meaning_en":  empty_to_none(f_en),
                        "example":     empty_to_none(f_ex),
                        "mastery":     1,
                        "next_review": get_ebbinghaus_date(1),
                        "user_id":     st.session_state.user_id
                    }
                    resp = httpx.post(
                        f"{URL}/rest/v1/vocabulary",
                        json=payload,
                        headers=HEADERS
                    )
                    if resp.status_code < 300:
                        st.success("🎉 新增成功！")
                        st.rerun()
                    else:
                        st.error(f"同步失敗：{resp.text}")
                else:
                    st.warning("請填寫單字與中文定義。")

    with t_view:
        if not df.empty:
            v_f = st.radio("Group Filter", ["Due Today", "All Nodes", "L5 Mastered"], horizontal=True)
            d_df = df.copy()
            if v_f == "Due Today":
                d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "L5 Mastered":
                d_df = d_df[d_df['mastery'] >= 5]
            st.dataframe(
                d_df[['word', 'meaning_zh', 'pos', 'mastery', 'next_review', 'other_forms']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Matrix is currently empty.")

    with t_edit:
        if not df.empty:
            target_word = st.selectbox("Select Target Node", options=df['word'].tolist())
            row = df[df['word'] == target_word].iloc[0]
            v_parts = parse_other_forms(row.get('other_forms'))

            col_pron, _ = st.columns([1, 2])
            with col_pron:
                if st.button(f"🔊 播放發音：{target_word}"):
                    play_pronunciation(target_word)

            with st.form("edit_matrix_form"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry（單字）*", value=row['word'])
                u_mean = e2.text_input("Definition（中文）*", value=row['meaning_zh'])

                dt_cur = datetime.strptime(str(row['next_review'])[:10], '%Y-%m-%d').date()
                u_date = st.date_input("Manual Schedule（複習日期）", value=dt_cur)

                st.write("---")
                st.caption("Morphology（動詞三態變化）")
                ev1, ev2, ev3 = st.columns(3)
                u_v1 = ev1.text_input("V1 (Base)",       value=v_parts[0])
                u_v2 = ev2.text_input("V2 (Past)",       value=v_parts[1])
                u_v3 = ev3.text_input("V3 (Participle)", value=v_parts[2])

                st.write("---")
                pos_options = ["n.", "v.", "adj.", "adv.", "phr.", "prep."]
                db_pos = row.get('pos', [])
                if isinstance(db_pos, str):
                    current_pos = [p.strip() for p in db_pos.strip('{}').split(',') if p in pos_options]
                elif isinstance(db_pos, list):
                    current_pos = [p for p in db_pos if p in pos_options]
                else:
                    current_pos = []

                u_pos  = st.multiselect("Class（詞性）", pos_options, default=current_pos)

                ec3, ec4 = st.columns(2)
                u_syn  = ec3.text_input("Synonyms",    value=row.get('synonyms', '') or '')
                u_coll = ec4.text_input("Collocations", value=row.get('collocations', '') or '')

                u_en = st.text_area("English Definition", value=row.get('meaning_en', '') or '')
                u_ex = st.text_area("Context Example",    value=row.get('example', '') or '')

                if st.form_submit_button("✅ UPDATE MATRIX"):
                    upd_payload = {
                        "word":         u_word,
                        "meaning_zh":   u_mean,
                        "pos":          u_pos if u_pos else [],
                        "next_review":  u_date.strftime('%Y-%m-%d'),
                        "other_forms":  [u_v1, u_v2, u_v3] if u_v1 else [],
                        "synonyms":     empty_to_none(u_syn),
                        "collocations": empty_to_none(u_coll),
                        "meaning_en":   empty_to_none(u_en),
                        "example":      empty_to_none(u_ex)
                    }
                    resp = httpx.patch(
                        f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}",
                        json=upd_payload,
                        headers=HEADERS
                    )
                    if resp.status_code < 300:
                        st.success("Node Synchronized!")
                        st.rerun()
                    else:
                        st.error(f"Update Failed: {resp.text}")
        else:
            st.info("Matrix is currently empty.")


# ============================================================
# 9. 頁面：Matrix Cards
# ============================================================
elif "Matrix Cards" in choice:
    st.markdown("<div class='main-title'>Matrix Cards</div>", unsafe_allow_html=True)

    FIELD_OPTIONS = {
        "🔤 英文單字":  "word",
        "🇹🇼 中文定義": "meaning_zh",
        "📖 英文定義":  "meaning_en",
        "📝 例句填空":  "example_blank",
        "📝 完整例句":  "example",
        "💡 詞性":      "pos",
        "📚 三態變化":  "other_forms",
        "🔗 同義詞":    "synonyms",
        "🎯 慣用搭配":  "collocations",
    }
    FIELD_LABELS = list(FIELD_OPTIONS.keys())

    TUTORIAL_STEPS = [
        {"icon": "🎴", "title": "歡迎使用 Matrix Cards！",
         "desc": "這裡是你的單字翻卡訓練區。\n開始之前，花 30 秒了解怎麼使用。"},
        {"icon": "📋", "title": "Step 1：選擇正面欄位",
         "desc": "正面是你的「提示」。\n建議放：中文定義 或 例句填空\n⚠️ 選擇的順序 = 卡片的排版順序！"},
        {"icon": "🔄", "title": "Step 2：選擇反面欄位",
         "desc": "反面是你的「答案」。\n建議放：英文單字 + 英文定義 + 完整例句"},
        {"icon": "📦", "title": "Step 3：選擇複習範圍",
         "desc": "今日到期 = 艾賓浩斯排程到期的單字\n全部單字 = 所有單字都會出現"},
        {"icon": "🚀", "title": "準備好了！",
         "desc": "點「套用設定」開始翻卡！\n翻完後去 Flash Pulse 做打字測驗更新熟練度。"},
    ]

    if "card_tutorial_done" not in st.session_state:
        st.session_state.card_tutorial_done = False
    if "card_tutorial_step" not in st.session_state:
        st.session_state.card_tutorial_step = 0

    if not st.session_state.card_tutorial_done:
        step = st.session_state.card_tutorial_step
        s = TUTORIAL_STEPS[step]
        st.markdown(f"""
            <div class="tutorial-card">
                <div style="font-size:4rem">{s['icon']}</div>
                <div style="font-size:1.6rem;font-weight:800;margin:0.5rem 0">{s['title']}</div>
                <div style="opacity:0.85;line-height:1.6">{s['desc'].replace(chr(10), '<br>')}</div>
            </div>
        """, unsafe_allow_html=True)
        st.progress((step + 1) / len(TUTORIAL_STEPS), text=f"{step + 1} / {len(TUTORIAL_STEPS)}")
        col_skip, col_prev, col_next = st.columns([2, 1, 1])
        with col_skip:
            if st.button("⏭️ 跳過教學"):
                st.session_state.card_tutorial_done = True
                st.rerun()
        with col_prev:
            if step > 0 and st.button("← 上一步"):
                st.session_state.card_tutorial_step -= 1
                st.rerun()
        with col_next:
            if step < len(TUTORIAL_STEPS) - 1:
                if st.button("下一步 →"):
                    st.session_state.card_tutorial_step += 1
                    st.rerun()
            else:
                if st.button("✅ 開始使用！"):
                    st.session_state.card_tutorial_done = True
                    st.rerun()
        st.stop()

    with st.expander("⚙️ 自訂卡片模式", expanded=("card_front_fields" not in st.session_state)):
        st.caption("⚠️ 選擇欄位的順序會影響卡片排版，第一個選的顯示在最上方")
        cfg1, cfg2 = st.columns(2)
        with cfg1:
            st.markdown("**正面（提示）**")
            front_choices = st.multiselect("正面", FIELD_LABELS,
                default=st.session_state.get("card_front_fields", ["🇹🇼 中文定義"]),
                key="front_select", label_visibility="collapsed")
        with cfg2:
            st.markdown("**反面（答案）**")
            back_choices = st.multiselect("反面", FIELD_LABELS,
                default=st.session_state.get("card_back_fields", ["🔤 英文單字", "📖 英文定義", "📝 完整例句"]),
                key="back_select", label_visibility="collapsed")
        col_scope, col_confirm = st.columns([2, 1])
        with col_scope:
            card_scope = st.radio("複習範圍", ["📅 今日到期", "📦 全部單字"], horizontal=True,
                index=0 if st.session_state.get("card_scope", "due") == "due" else 1)
        with col_confirm:
            st.write("")
            if st.button("✅ 套用設定", use_container_width=True):
                st.session_state.card_front_fields = front_choices
                st.session_state.card_back_fields  = back_choices
                st.session_state.card_scope        = "due" if "今日" in card_scope else "all"
                st.session_state.card_index        = 0
                st.session_state.is_flipped        = False
                st.rerun()
        if st.button("📖 重新觀看教學"):
            st.session_state.card_tutorial_done = False
            st.session_state.card_tutorial_step = 0
            st.rerun()

    if "card_front_fields" not in st.session_state:
        st.session_state.card_front_fields = ["🇹🇼 中文定義"]
    if "card_back_fields" not in st.session_state:
        st.session_state.card_back_fields  = ["🔤 英文單字", "📖 英文定義", "📝 完整例句"]
    if "card_scope" not in st.session_state:
        st.session_state.card_scope = "due"

    if st.session_state.card_scope == "due":
        due_cards = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    else:
        due_cards = list(raw_data)

    def render_fields(card, field_labels, is_front=False):
        for label in field_labels:
            field_key = FIELD_OPTIONS.get(label)
            if not field_key:
                continue
            if field_key == "word":
                st.markdown(
                    f"<h1 style='text-align:center;font-size:3.5rem;margin:0.5rem 0'>{card['word']}</h1>",
                    unsafe_allow_html=True)
                if st.button("🔊 播放發音", key=f"pron_{card.get('id','x')}_{is_front}"):
                    play_pronunciation(card['word'])
            elif field_key == "meaning_zh":
                val = card.get("meaning_zh", "")
                if val:
                    st.markdown(f"<h3 style='text-align:center;color:#2d3436'>{val}</h3>",
                                unsafe_allow_html=True)
            elif field_key == "meaning_en":
                st.markdown(f"**📖 英文定義：** {card.get('meaning_en', '') or '—'}")
            elif field_key == "example_blank":
                ex, word = card.get("example", ""), card.get("word", "")
                if ex and word:
                    blanked = re.sub(re.escape(word), "**____**", ex, flags=re.IGNORECASE)
                    st.markdown(f"**📝 例句填空：**\n> {blanked}")
                else:
                    st.markdown("**📝 例句填空：** —")
            elif field_key == "example":
                st.markdown(f"**📝 完整例句：**\n> {card.get('example', '') or '—'}")
            elif field_key == "pos":
                pos = card.get("pos", [])
                st.markdown(f"**💡 詞性：** {', '.join(pos) if isinstance(pos, list) else pos or '—'}")
            elif field_key == "other_forms":
                forms = parse_other_forms(card.get("other_forms"))
                st.markdown(f"**📚 三態變化：** {' / '.join(f for f in forms if f) or '—'}")
            elif field_key == "synonyms":
                st.markdown(f"**🔗 同義詞：** {card.get('synonyms', '') or '—'}")
            elif field_key == "collocations":
                st.markdown(f"**🎯 慣用搭配：** {card.get('collocations', '') or '—'}")

    if due_cards:
        if 'card_index' not in st.session_state:
            st.session_state.card_index = 0
        if 'is_flipped' not in st.session_state:
            st.session_state.is_flipped = False
        if st.session_state.card_index >= len(due_cards):
            st.session_state.card_index = 0

        current_card = due_cards[st.session_state.card_index]
        scope_label = "今日到期" if st.session_state.card_scope == "due" else "全部單字"
        st.caption(f"📦 {scope_label}｜正面：{' + '.join(st.session_state.card_front_fields)}｜反面：{' + '.join(st.session_state.card_back_fields)}")
        st.progress((st.session_state.card_index + 1) / len(due_cards),
                    text=f"{st.session_state.card_index + 1} / {len(due_cards)}")

        with st.container(border=True):
            if not st.session_state.is_flipped:
                render_fields(current_card, st.session_state.card_front_fields, is_front=True)
            else:
                st.markdown("---")
                render_fields(current_card, st.session_state.card_back_fields, is_front=False)

        st.write("")
        b1, b2, b3 = st.columns([1, 2, 1])
        with b1:
            if st.button("⬅️ 上一字") and st.session_state.card_index > 0:
                st.session_state.card_index -= 1
                st.session_state.is_flipped = False
                st.rerun()
        with b2:
            if st.button("🔄 翻到反面" if not st.session_state.is_flipped else "🔄 翻回正面"):
                st.session_state.is_flipped = not st.session_state.is_flipped
                st.rerun()
        with b3:
            if st.button("下一字 ➡️") and st.session_state.card_index < len(due_cards) - 1:
                st.session_state.card_index += 1
                st.session_state.is_flipped = False
                st.rerun()

        if st.session_state.card_index == len(due_cards) - 1 and st.session_state.is_flipped:
            st.success("🎉 這輪預習看完了！去 Flash Pulse 進行打字測驗吧！")
    else:
        st.success("✨ 目前沒有待複習的單字卡！")


# ============================================================
# 10. 頁面：Flash Pulse
# ============================================================
elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)

    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]

    if due:
        if "pulse_word" not in st.session_state or st.session_state.get("pulse_refresh", False):
            st.session_state.pulse_word    = random.choice(due)
            st.session_state.hint_level    = 0
            st.session_state.pulse_refresh = False

        q          = st.session_state.pulse_word
        hint_level = st.session_state.get("hint_level", 0)

        with st.container(border=True):
            st.markdown(f"### 💡 中文提示：**{q['meaning_zh']}**")
            if q.get('example'):
                st.caption(f"📝 Context: {q['example'].replace(q['word'], '____')}")

            if hint_level == 1:
                st.markdown(
                    f"<div class='hint-badge'>💡 字首提示：{q['word'][0].upper()}...</div>",
                    unsafe_allow_html=True)
            elif hint_level == 2:
                st.markdown(
                    f"<div class='hint-badge'>📖 英文定義：{q.get('meaning_en', '（無英文定義）')}</div>",
                    unsafe_allow_html=True)

            st.caption(f"目前熟練度：{'⭐' * int(q.get('mastery', 1))} L{q.get('mastery', 1)}")

        ans = st.text_input("Type the correct Entry（不分大小寫）:", key="pulse_input")
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            if st.button("EXECUTE VERIFICATION", use_container_width=True):
                if ans.strip().lower() == q['word'].lower():
                    st.success("✅ Correct! Matrix Evolved.")
                    st.balloons()
                    new_m = min(5, q['mastery'] + 1)
                    update_mastery_in_db(q['id'], new_m, access_token)
                    st.session_state.pulse_refresh = True
                    st.session_state.hint_level    = 0
                    st.rerun()
                else:
                    if hint_level < 2:
                        st.session_state.hint_level += 1
                        st.warning(f"❌ 答錯！給你提示 {st.session_state.hint_level}/2")
                        st.rerun()
                    else:
                        current_m = q.get('mastery', 1)
                        new_m = calculate_new_mastery(current_m)
                        update_mastery_in_db(q['id'], new_m, access_token)
                        st.error(f"💀 答案是：**{q['word']}**　熟練度 L{current_m} → L{new_m}")
                        st.session_state.pulse_refresh = True
                        st.session_state.hint_level    = 0

        with col2:
            if st.button("🔊 發音", use_container_width=True):
                play_pronunciation(q['word'])

        with col3:
            if st.button("⏭️ 跳過", use_container_width=True):
                st.session_state.pulse_refresh = True
                st.session_state.hint_level    = 0
                st.rerun()

        st.markdown("---")
        hint_status = {0: "🟢 無提示", 1: "🟡 字首已顯示", 2: "🔴 英文定義已顯示（再答不出將降級）"}
        st.caption(f"提示狀態：{hint_status[hint_level]}")
    else:
        st.success("Matrix Stable. No nodes due for review.")


# ============================================================
# 11. 頁面：Ebbing Log
# ============================================================
elif "Ebbing Log" in choice:
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)

    if not df.empty:
        selected_level = st.radio(
            "篩選 Level：", ["全部", 0, 1, 2, 3, 4, 5],
            horizontal=True, key="ebbing_level_filter"
        )

        level_counts = df.groupby("mastery").size().reset_index()
        level_counts.columns = ["Level", "數量"]
        all_levels = pd.DataFrame({"Level": [0, 1, 2, 3, 4, 5]})
        level_counts = all_levels.merge(level_counts, on="Level", how="left").fillna(0)
        level_counts["數量"] = level_counts["數量"].astype(int)

        fig_levels = go.Figure()
        fig_levels.add_trace(go.Scatter(
            x=level_counts["Level"],
            y=level_counts["數量"],
            mode="lines+markers+text",
            text=level_counts["數量"],
            textposition="top center",
            line=dict(color="#2d3436", width=3),
            marker=dict(size=12, color="#ff7675", line=dict(color="#2d3436", width=2)),
        ))
        fig_levels.update_layout(
            plot_bgcolor="white", height=280,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(
                tickvals=[0, 1, 2, 3, 4, 5],
                ticktext=["L0 遺忘", "L1 初學", "L2 認識", "L3 熟悉", "L4 精通", "L5 掌握"],
                showgrid=True, gridcolor="#f0f0f0"
            ),
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="單字數量"),
            showlegend=False,
        )
        st.plotly_chart(fig_levels, use_container_width=True)

        total = len(df)
        level_colors = ["#d63031", "#ff7675", "#fdcb6e", "#74b9ff", "#55efc4", "#6c5ce7"]
        cols = st.columns(6)
        for i, (col, color) in enumerate(zip(cols, level_colors)):
            count = int(level_counts[level_counts["Level"] == i]["數量"].values[0])
            pct = f"{count/total*100:.0f}%" if total > 0 else "0%"
            col.markdown(
                f"<div style='background:{color}20;border-left:4px solid {color};"
                f"padding:0.4rem 0.6rem;border-radius:8px;text-align:center'>"
                f"<b>L{i}</b><br>{count}<br><small>{pct}</small></div>",
                unsafe_allow_html=True
            )

        st.write("")
        st.divider()

        col_left, col_right = st.columns([3, 2])

        with col_left:
            if selected_level == "全部":
                filtered_df = df
                label_text = "全部單字"
            else:
                filtered_df = df[df["mastery"] == int(selected_level)]
                label_text = f"L{selected_level} 單字"

            st.markdown(f"**📋 {label_text}（{len(filtered_df)} 個）**")
            if not filtered_df.empty:
                st.dataframe(
                    filtered_df[["word", "meaning_zh", "mastery", "next_review"]].rename(columns={
                        "word": "單字", "meaning_zh": "中文定義",
                        "mastery": "Level", "next_review": "下次複習"
                    }),
                    use_container_width=True, hide_index=True, height=350,
                )
            else:
                st.info("此 Level 目前沒有單字。")

        with col_right:
            st.markdown("**⏰ 最近待複習（前 10 筆）**")
            upcoming = df.sort_values("next_review").head(10)
            for _, row in upcoming.iterrows():
                days_until = (pd.to_datetime(row["next_review"]).date() - date.today()).days
                badge = f"🔴 過期{abs(days_until)}天" if days_until < 0 else ("🟡 今日" if days_until == 0 else f"🟢 {days_until}天後")
                st.markdown(
                    f"<div style='padding:0.4rem 0.6rem;margin-bottom:0.4rem;"
                    f"background:#f8f9fa;border-radius:8px;font-size:0.88rem'>"
                    f"<b>{row['word']}</b> {badge}<br>"
                    f"<span style='color:#636e72'>{row['meaning_zh']} ｜ L{row['mastery']}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.divider()
        with st.expander("📈 複習負載預測圖"):
            v_d = st.select_slider("預測天數", options=[7, 14, 30, 90, 180, 365], value=30)
            df_copy = df.copy()
            df_copy["date"] = pd.to_datetime(df_copy["next_review"]).dt.date
            dates  = [date.today() + timedelta(days=i) for i in range(v_d + 1)]
            counts = [len(df_copy[df_copy["date"] <= d]) for d in dates]
            fig = go.Figure(go.Scatter(
                x=dates, y=counts, mode="lines+markers",
                line=dict(color="#2d3436", width=3),
                marker=dict(size=8, color="#ff7675"),
            ))
            fig.update_layout(
                plot_bgcolor="white", hovermode="x unified",
                margin=dict(l=0, r=0, t=10, b=0), height=300,
                xaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="日期"),
                yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="累計待複習單字數"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for log prediction.")
