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

        /* Tutorial card style */
        .tutorial-card {
            background: linear-gradient(135deg, #2d3436 0%, #636e72 100%);
            border-radius: 20px;
            padding: 2.5rem;
            color: white;
            text-align: center;
            margin: 1rem 0;
        }
        .tutorial-icon { font-size: 4rem; margin-bottom: 1rem; }
        .tutorial-title { font-size: 1.6rem; font-weight: 800; margin-bottom: 0.5rem; }
        .tutorial-desc { font-size: 1rem; opacity: 0.85; line-height: 1.6; }

        /* Hint badge */
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
# 2. API 設定 & 工具函式
# ============================================================
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

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

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except Exception:
        return []

def calculate_new_mastery(current_mastery, penalty=2):
    """降級邏輯：小於2直接歸零，否則減2"""
    if current_mastery < 2:
        return 0
    return current_mastery - penalty

def update_mastery_in_db(word_id, new_mastery):
    httpx.patch(
        f"{URL}/rest/v1/vocabulary?id=eq.{word_id}",
        json={"mastery": new_mastery, "next_review": get_ebbinghaus_date(new_mastery)},
        headers=HEADERS
    )

# ── 發音函式（gTTS） ──────────────────────────────────────────
def play_pronunciation(word: str):
    """使用 gTTS 生成並直接播放發音"""
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
    except ImportError:
        # 如果 gTTS 未安裝，fallback 到劍橋連結
        st.link_button(
            f"🔊 Cambridge Pronunciation: {word}",
            f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{word.replace(' ', '-')}"
        )
    except Exception as e:
        st.warning(f"發音載入失敗：{e}")


# ============================================================
# 3. 資料初始化
# ============================================================
raw_data = load_data()
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
due_count = (
    len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()])
    if not df.empty else 0
)


# ============================================================
# 4. 側邊導航
# ============================================================
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)

pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio(
    "SYSTEM ACCESS",
    ["📋 Matrix Core", "🎴 Matrix Cards", pulse_label, "📅 Ebbing Log"]
)

if st.sidebar.button("🔄 Force Sync Matrix"):
    st.rerun()


# ============================================================
# 5. 頁面：Matrix Core
# ============================================================
if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize Node", "🔍 View Matrix", "📝 Modify Protocol"])

    # --- [A] 新增單字 ---
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
                        "next_review": get_ebbinghaus_date(1)
                    }
                    resp = httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                    if resp.status_code < 300:
                        st.success("🎉 新增成功！正在更新矩陣...")
                        st.rerun()
                    else:
                        st.error(f"同步失敗：{resp.text}")
                else:
                    st.warning("請填寫單字與中文定義。")

    # --- [B] 檢視單字庫 ---
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

    # --- [C] 修改單字 ---
    with t_edit:
        if not df.empty:
            target_word = st.selectbox("Select Target Node", options=df['word'].tolist())
            row = df[df['word'] == target_word].iloc[0]
            v_parts = parse_other_forms(row.get('other_forms'))

            # 發音按鈕（直接播放）
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
                u_v1 = ev1.text_input("V1 (Base)",        value=v_parts[0])
                u_v2 = ev2.text_input("V2 (Past)",        value=v_parts[1])
                u_v3 = ev3.text_input("V3 (Participle)",  value=v_parts[2])

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
                u_syn  = ec3.text_input("Synonyms（同義詞）",      value=row.get('synonyms', '') or '')
                u_coll = ec4.text_input("Collocations（慣用搭配）", value=row.get('collocations', '') or '')

                u_en = st.text_area("English Definition", value=row.get('meaning_en', '') or '')
                u_ex = st.text_area("Context Example",   value=row.get('example', '') or '')

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
# 6. 頁面：Matrix Cards
# ============================================================
elif "Matrix Cards" in choice:
    st.markdown("<div class='main-title'>Matrix Cards</div>", unsafe_allow_html=True)

    FIELD_OPTIONS = {
        "🔤 英文單字":   "word",
        "🇹🇼 中文定義":  "meaning_zh",
        "📖 英文定義":   "meaning_en",
        "📝 例句填空":   "example_blank",
        "📝 完整例句":   "example",
        "💡 詞性":       "pos",
        "📚 三態變化":   "other_forms",
        "🔗 同義詞":     "synonyms",
        "🎯 慣用搭配":   "collocations",
    }
    FIELD_LABELS = list(FIELD_OPTIONS.keys())

    # ── 遊戲式教學介面 ────────────────────────────────────────
    TUTORIAL_STEPS = [
        {
            "icon": "🎴",
            "title": "歡迎使用 Matrix Cards！",
            "desc": "這裡是你的單字翻卡訓練區。\n開始之前，花 30 秒了解怎麼使用。"
        },
        {
            "icon": "📋",
            "title": "Step 1：選擇正面欄位",
            "desc": "正面是你的「提示」。\n建議放：中文定義 或 例句填空\n⚠️ 選擇的順序 = 卡片的排版順序，第一個選的會顯示在最上方！"
        },
        {
            "icon": "🔄",
            "title": "Step 2：選擇反面欄位",
            "desc": "反面是你的「答案」。\n建議放：英文單字 + 英文定義 + 完整例句\n翻牌後會依序顯示你選的所有欄位。"
        },
        {
            "icon": "📦",
            "title": "Step 3：選擇複習範圍",
            "desc": "「今日到期」= 只練艾賓浩斯排程到期的單字\n「全部單字」= 所有單字都會出現\n建議平常用今日到期，考試前用全部。"
        },
        {
            "icon": "🚀",
            "title": "準備好了！",
            "desc": "點「套用設定」開始翻卡！\n記得：翻完卡片後去 Flash Pulse 做打字測驗，才會更新熟練度喔。"
        },
    ]

    # 初始化 tutorial session state
    if "card_tutorial_done" not in st.session_state:
        st.session_state.card_tutorial_done = False
    if "card_tutorial_step" not in st.session_state:
        st.session_state.card_tutorial_step = 0

    # 顯示教學（未完成時）
    if not st.session_state.card_tutorial_done:
        step = st.session_state.card_tutorial_step
        s = TUTORIAL_STEPS[step]

        st.markdown(f"""
            <div class="tutorial-card">
                <div class="tutorial-icon">{s['icon']}</div>
                <div class="tutorial-title">{s['title']}</div>
                <div class="tutorial-desc">{s['desc'].replace(chr(10), '<br>')}</div>
            </div>
        """, unsafe_allow_html=True)

        st.progress((step + 1) / len(TUTORIAL_STEPS), text=f"{step + 1} / {len(TUTORIAL_STEPS)}")

        col_skip, col_prev, col_next = st.columns([2, 1, 1])

        with col_skip:
            if st.button("⏭️ 跳過教學，直接開始"):
                st.session_state.card_tutorial_done = True
                st.rerun()

        with col_prev:
            if step > 0:
                if st.button("← 上一步"):
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

    # ── 卡片模式設定面板 ──────────────────────────────────────
    with st.expander("⚙️ 自訂卡片模式", expanded=("card_front_fields" not in st.session_state)):
        st.caption("⚠️ 選擇欄位的順序會影響卡片排版，第一個選的顯示在最上方")

        cfg1, cfg2 = st.columns(2)
        with cfg1:
            st.markdown("**正面（提示）**")
            front_choices = st.multiselect(
                "正面顯示欄位",
                FIELD_LABELS,
                default=st.session_state.get("card_front_fields", ["🇹🇼 中文定義"]),
                key="front_select",
                label_visibility="collapsed"
            )
        with cfg2:
            st.markdown("**反面（答案）**")
            back_choices = st.multiselect(
                "反面顯示欄位",
                FIELD_LABELS,
                default=st.session_state.get("card_back_fields", ["🔤 英文單字", "📖 英文定義", "📝 完整例句"]),
                key="back_select",
                label_visibility="collapsed"
            )

        col_scope, col_confirm = st.columns([2, 1])
        with col_scope:
            card_scope = st.radio(
                "複習範圍",
                ["📅 今日到期", "📦 全部單字"],
                horizontal=True,
                index=0 if st.session_state.get("card_scope", "due") == "due" else 1
            )
        with col_confirm:
            st.write("")
            if st.button("✅ 套用設定", use_container_width=True):
                st.session_state.card_front_fields = front_choices
                st.session_state.card_back_fields  = back_choices
                st.session_state.card_scope        = "due" if "今日" in card_scope else "all"
                st.session_state.card_index        = 0
                st.session_state.is_flipped        = False
                st.rerun()

        # 重新觀看教學
        if st.button("📖 重新觀看操作教學"):
            st.session_state.card_tutorial_done = False
            st.session_state.card_tutorial_step = 0
            st.rerun()

    # 套用預設值
    if "card_front_fields" not in st.session_state:
        st.session_state.card_front_fields = ["🇹🇼 中文定義"]
    if "card_back_fields" not in st.session_state:
        st.session_state.card_back_fields  = ["🔤 英文單字", "📖 英文定義", "📝 完整例句"]
    if "card_scope" not in st.session_state:
        st.session_state.card_scope = "due"

    # ── 篩選卡片池 ────────────────────────────────────────────
    if st.session_state.card_scope == "due":
        due_cards = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    else:
        due_cards = list(raw_data)

    # ── 渲染欄位 ──────────────────────────────────────────────
    def render_fields(card, field_labels, is_front=False):
        for label in field_labels:
            field_key = FIELD_OPTIONS.get(label)
            if not field_key:
                continue

            if field_key == "word":
                st.markdown(
                    f"<h1 style='text-align:center; font-size:3.5rem; margin:0.5rem 0;'>{card['word']}</h1>",
                    unsafe_allow_html=True
                )
                # 直接播放發音按鈕
                if st.button(f"🔊 播放發音", key=f"pron_{card.get('id','x')}_{is_front}"):
                    play_pronunciation(card['word'])

            elif field_key == "meaning_zh":
                val = card.get("meaning_zh", "")
                if val:
                    st.markdown(
                        f"<h3 style='text-align:center; color:#2d3436;'>{val}</h3>",
                        unsafe_allow_html=True
                    )

            elif field_key == "meaning_en":
                val = card.get("meaning_en", "")
                st.markdown(f"**📖 英文定義：** {val or '—'}")

            elif field_key == "example_blank":
                ex = card.get("example", "")
                word = card.get("word", "")
                if ex and word:
                    blanked = re.sub(re.escape(word), "**____**", ex, flags=re.IGNORECASE)
                    st.markdown(f"**📝 例句填空：**")
                    st.markdown(f"> {blanked}")
                else:
                    st.markdown("**📝 例句填空：** —")

            elif field_key == "example":
                val = card.get("example", "")
                st.markdown(f"**📝 完整例句：**")
                st.markdown(f"> {val or '—'}")

            elif field_key == "pos":
                pos = card.get("pos", [])
                pos_str = ", ".join(pos) if isinstance(pos, list) else str(pos)
                st.markdown(f"**💡 詞性：** {pos_str or '—'}")

            elif field_key == "other_forms":
                forms = parse_other_forms(card.get("other_forms"))
                forms_str = " / ".join(f for f in forms if f) or "—"
                st.markdown(f"**📚 三態變化：** {forms_str}")

            elif field_key == "synonyms":
                val = card.get("synonyms", "")
                st.markdown(f"**🔗 同義詞：** {val or '—'}")

            elif field_key == "collocations":
                val = card.get("collocations", "")
                st.markdown(f"**🎯 慣用搭配：** {val or '—'}")

    # ── 卡片主體 ──────────────────────────────────────────────
    if due_cards:
        if 'card_index' not in st.session_state:
            st.session_state.card_index = 0
        if 'is_flipped' not in st.session_state:
            st.session_state.is_flipped = False

        if st.session_state.card_index >= len(due_cards):
            st.session_state.card_index = 0

        current_card = due_cards[st.session_state.card_index]

        scope_label = "今日到期" if st.session_state.card_scope == "due" else "全部單字"
        front_summary = " + ".join(st.session_state.card_front_fields)
        back_summary  = " + ".join(st.session_state.card_back_fields)
        st.caption(f"📦 {scope_label}｜正面：{front_summary}｜反面：{back_summary}")
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
            if st.button("⬅️ 上一字"):
                if st.session_state.card_index > 0:
                    st.session_state.card_index -= 1
                    st.session_state.is_flipped = False
                    st.rerun()

        with b2:
            flip_label = "🔄 翻到反面" if not st.session_state.is_flipped else "🔄 翻回正面"
            if st.button(flip_label):
                st.session_state.is_flipped = not st.session_state.is_flipped
                st.rerun()

        with b3:
            if st.button("下一字 ➡️"):
                if st.session_state.card_index < len(due_cards) - 1:
                    st.session_state.card_index += 1
                    st.session_state.is_flipped = False
                    st.rerun()

        if st.session_state.card_index == len(due_cards) - 1 and st.session_state.is_flipped:
            st.success("🎉 這輪預習看完了！立刻去左側進入『Flash Pulse』進行打字複習測驗吧！")

    else:
        st.success("✨ 目前沒有待複習的單字卡，矩陣狀態安全！")


# ============================================================
# 7. 頁面：Flash Pulse（打字測驗 + 提示系統）
# ============================================================
elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)

    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]

    if due:
        # 初始化當前題目（只在第一次或答對後重新抽題）
        if "pulse_word" not in st.session_state or st.session_state.get("pulse_refresh", False):
            st.session_state.pulse_word = random.choice(due)
            st.session_state.hint_level = 0   # 0=無提示 1=字首 2=英文定義
            st.session_state.pulse_refresh = False

        q = st.session_state.pulse_word
        hint_level = st.session_state.get("hint_level", 0)

        # ── 題目顯示 ──────────────────────────────────────────
        with st.container(border=True):
            st.markdown(f"### 💡 中文提示：**{q['meaning_zh']}**")

            if q.get('example'):
                blanked_ex = q['example'].replace(q['word'], '____')
                st.caption(f"📝 Context: {blanked_ex}")

            # 提示顯示
            if hint_level == 1:
                st.markdown(
                    f"<div class='hint-badge'>💡 字首提示：{q['word'][0].upper()}...</div>",
                    unsafe_allow_html=True
                )
            elif hint_level == 2:
                en_def = q.get('meaning_en', '（無英文定義）')
                st.markdown(
                    f"<div class='hint-badge'>📖 英文定義：{en_def}</div>",
                    unsafe_allow_html=True
                )

            # 熟練度顯示
            st.caption(f"目前熟練度：{'⭐' * int(q.get('mastery', 1))} L{q.get('mastery', 1)}")

        # ── 輸入與驗證 ────────────────────────────────────────
        ans = st.text_input("Type the correct Entry（不分大小寫）:", key="pulse_input")

        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            if st.button("EXECUTE VERIFICATION", use_container_width=True):
                if ans.strip().lower() == q['word'].lower():
                    # 答對
                    st.success("✅ Correct! Matrix Evolved.")
                    st.balloons()
                    new_m = min(5, q['mastery'] + 1)
                    update_mastery_in_db(q['id'], new_m)
                    st.session_state.pulse_refresh = True
                    st.session_state.hint_level = 0
                    st.rerun()
                else:
                    if hint_level < 2:
                        # 還有提示可用
                        st.session_state.hint_level += 1
                        hint_names = {1: "字首提示", 2: "英文定義"}
                        st.warning(f"❌ 答錯！給你一個提示：{hint_names[st.session_state.hint_level]}")
                        st.rerun()
                    else:
                        # 提示用完還答不出來 → 降級
                        current_m = q.get('mastery', 1)
                        new_m = calculate_new_mastery(current_m)
                        update_mastery_in_db(q['id'], new_m)
                        st.error(f"💀 提示用盡，答案是：**{q['word']}**\n\n熟練度降級：L{current_m} → L{new_m}")
                        st.session_state.pulse_refresh = True
                        st.session_state.hint_level = 0

        with col2:
            # 直接播放發音
            if st.button("🔊 發音", use_container_width=True):
                play_pronunciation(q['word'])

        with col3:
            if st.button("⏭️ 跳過", use_container_width=True):
                st.session_state.pulse_refresh = True
                st.session_state.hint_level = 0
                st.rerun()

        # 提示進度指示
        st.markdown("---")
        hint_status = {0: "🟢 無提示", 1: "🟡 字首已顯示", 2: "🔴 英文定義已顯示（再答不出將降級）"}
        st.caption(f"提示狀態：{hint_status[hint_level]}")

    else:
        st.success("Matrix Stable. No nodes due for review.")


# ============================================================
# 8. 頁面：Ebbing Log
# ============================================================
elif "Ebbing Log" in choice:
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)

    if not df.empty:

        # ── Level 切換 ────────────────────────────────────────
        selected_level = st.radio(
            "篩選 Level：",
            ["全部", 0, 1, 2, 3, 4, 5],
            horizontal=True,
            key="ebbing_level_filter"
        )

        # ── 計算各 Level 數量（含 Level 0）────────────────────
        level_counts = df.groupby("mastery").size().reset_index()
        level_counts.columns = ["Level", "數量"]
        all_levels = pd.DataFrame({"Level": [0, 1, 2, 3, 4, 5]})
        level_counts = all_levels.merge(level_counts, on="Level", how="left").fillna(0)
        level_counts["數量"] = level_counts["數量"].astype(int)

        # ── 折線圖 ────────────────────────────────────────────
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
            plot_bgcolor="white",
            height=280,
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(
                tickvals=[0, 1, 2, 3, 4, 5],
                ticktext=["L0 遺忘", "L1 初學", "L2 認識", "L3 熟悉", "L4 精通", "L5 掌握"],
                showgrid=True, gridcolor="#f0f0f0",
            ),
            yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="單字數量"),
            showlegend=False,
        )
        st.plotly_chart(fig_levels, use_container_width=True)

        # ── Level 統計卡片（單行 7 格）────────────────────────
        total = len(df)
        level_colors = ["#d63031", "#ff7675", "#fdcb6e", "#74b9ff", "#55efc4", "#6c5ce7"]
        level_labels = ["L0", "L1", "L2", "L3", "L4", "L5"]
        cols = st.columns(6)
        for i, (col, color, label) in enumerate(zip(cols, level_colors, level_labels)):
            count = int(level_counts[level_counts["Level"] == i]["數量"].values[0])
            pct = f"{count/total*100:.0f}%" if total > 0 else "0%"
            col.markdown(
                f"<div style='background:{color}20; border-left:4px solid {color}; "
                f"padding:0.4rem 0.6rem; border-radius:8px; text-align:center;'>"
                f"<b>{label}</b><br>{count}<br><small>{pct}</small></div>",
                unsafe_allow_html=True
            )

        st.write("")
        st.divider()

        # ── 兩欄佈局：左=單字列表，右=待複習 ─────────────────
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
                        "word": "單字",
                        "meaning_zh": "中文定義",
                        "mastery": "Level",
                        "next_review": "下次複習"
                    }),
                    use_container_width=True,
                    hide_index=True,
                    height=350,
                )
            else:
                st.info("此 Level 目前沒有單字。")

        with col_right:
            st.markdown("**⏰ 最近待複習（前 10 筆）**")
            upcoming = df.sort_values("next_review").head(10)
            for _, row in upcoming.iterrows():
                days_until = (pd.to_datetime(row["next_review"]).date() - date.today()).days
                if days_until < 0:
                    badge = f"🔴 過期 {abs(days_until)}天"
                elif days_until == 0:
                    badge = "🟡 今日"
                else:
                    badge = f"🟢 {days_until}天後"
                st.markdown(
                    f"<div style='padding:0.4rem 0.6rem; margin-bottom:0.4rem; "
                    f"background:#f8f9fa; border-radius:8px; font-size:0.88rem;'>"
                    f"<b>{row['word']}</b> {badge}<br>"
                    f"<span style='color:#636e72;'>{row['meaning_zh']} ｜ L{row['mastery']}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        st.divider()

        # ── 複習負載預測圖（收折）────────────────────────────
        with st.expander("📈 複習負載預測圖"):
            v_d = st.select_slider(
                "預測天數",
                options=[7, 14, 30, 90, 180, 365],
                value=30
            )
            df_copy = df.copy()
            df_copy["date"] = pd.to_datetime(df_copy["next_review"]).dt.date
            dates  = [date.today() + timedelta(days=i) for i in range(v_d + 1)]
            counts = [len(df_copy[df_copy["date"] <= d]) for d in dates]

            fig = go.Figure(go.Scatter(
                x=dates, y=counts,
                mode="lines+markers",
                line=dict(color="#2d3436", width=3),
                marker=dict(size=8, color="#ff7675"),
            ))
            fig.update_layout(
                plot_bgcolor="white",
                hovermode="x unified",
                margin=dict(l=0, r=0, t=10, b=0),
                height=300,
                xaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="日期"),
                yaxis=dict(showgrid=True, gridcolor="#f0f0f0", title="累計待複習單字數"),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("Insufficient data for log prediction.")
