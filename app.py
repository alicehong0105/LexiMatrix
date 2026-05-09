import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 頁面配置與 PWA 高級感介面注入 ---
st.set_page_config(page_title="Qurate Pro", page_icon="⚡", layout="wide")

# 修正：確保 CSS 放在正確的 markdown 容器內，並開啟 unsafe_allow_html
st.markdown("""
    <style>
        [data-testid="stHeader"] { visibility: hidden; }
        footer { visibility: hidden; }
        .main-title {
            background: linear-gradient(90deg, #007bff, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800; font-size: 2.8rem; margin-bottom: 0.5rem;
        }
        .stButton > button {
            width: 100%; border-radius: 12px; height: 3.5rem;
            background: linear-gradient(135deg, #6e8efb, #a777e3);
            color: white; font-weight: bold; border: none; transition: 0.3s;
        }
        .stButton > button:hover { transform: scale(1.02); box-shadow: 0 10px 20px rgba(110, 142, 251, 0.3); }
        input { font-size: 16px !important; }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1);
            padding: 1.2rem; border-radius: 20px; backdrop-filter: blur(5px);
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. 系統狀態初始化 ---
for key in ['quiz_state', 'show_balloons', 'duplicate_word', 'force_quiz_word']:
    if key not in st.session_state:
        st.session_state[key] = {'word': None} if key == 'quiz_state' else False

if st.session_state.show_balloons:
    st.balloons(); st.session_state.show_balloons = False

# --- 3. 核心 API 與艾賓浩斯演算法 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def get_next_review_date(mastery):
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    return str(date.today() + timedelta(days=curve.get(mastery, 1)))

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 4. 側邊欄導航 ---
st.sidebar.markdown("<h1 style='color: #007bff;'>⚡ Qurate Pro</h1>", unsafe_allow_html=True)
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", "🎯 Flash Pulse", "📅 Ebbing Log"])
st.sidebar.divider()
st.sidebar.caption("PWA Engine Active | High School Dev Edition")

# --- 5. 功能模組 ---

# 模組 A: Matrix Core
if choice == "📋 Matrix Core":
    st.markdown("<h1 class='main-title'>📋 Matrix Core</h1>", unsafe_allow_html=True)
    raw_data = load_data()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    t_add, t_edit, t_view = st.tabs(["➕ Initialize Node", "📝 Modify Protocol", "🔍 View Matrix"])

    with t_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("Entry (單字)*")
            f_mean = c2.text_input("Definition (中文)*")
            
            st.write("---")
            st.caption("Morphology (動詞三態/變化形態)")
            v1, v2, v3 = st.columns(3)
            f_v1 = v1.text_input("V1 (Base)", placeholder="eat")
            f_v2 = v2.text_input("V2 (Past)", placeholder="ate")
            f_v3 = v3.text_input("V3 (P.P.)", placeholder="eaten")
            
            st.write("---")
            f_pos = st.multiselect("Class (詞性)", ["n.", "v.", "adj.", "adv.", "phr.", "prep."])
            c3, c4 = st.columns(2)
            f_syn = c3.text_input("Synonyms (同義詞)")
            f_coll = c4.text_input("Collocations (常用搭配)")
            
            f_en_def = st.text_area("English Definition (英文定義)")
            f_ex = st.text_area("Context Sentence (例句)")
            
            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    # 重複檢查
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.duplicate_word = f_word.strip()
                        st.rerun()
                    else:
                        variants = f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else ""
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": ", ".join(f_pos),
                            "other_forms": variants, "synonyms": f_syn, "collocations": f_coll,
                            "meaning_en": f_en_def, "example": f_ex, "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json={k:v for k,v in payload.items() if v}, headers=HEADERS)
                        st.session_state.show_balloons = True; st.rerun()

    with t_edit:
        if not df.empty:
            target = st.selectbox("Select Node", options=df['word'].tolist())
            row = df[df['word'] == target].iloc[0]
            st.link_button(f"🔊 Cambridge Audio: {target}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target.replace(' ', '-')}")
            with st.form("modify_form"):
                u_word = st.text_input("Entry", value=row.get('word',''))
                u_mean = st.text_input("Definition", value=row.get('meaning_zh',''))
                u_ex = st.text_area("Context", value=row.get('example',''))
                if st.form_submit_button("UPDATE"):
                    httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json={"word": u_word, "meaning_zh": u_mean, "example": u_ex}, headers=HEADERS)
                    st.rerun()

    with t_view:
        if not df.empty:
            v_f = st.radio("Display Filter", ["All", "Due Today", "Mastered (L5)"], horizontal=True)
            search = st.text_input("🔍 Search Matrix...")
            d_df = df.copy()
            if v_f == "Due Today": d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "Mastered (L5)": d_df = d_df[d_df['mastery'] >= 5]
            if search: d_df = d_df[d_df['word'].str.contains(search, case=False)]
            st.dataframe(d_df[['word', 'meaning_zh', 'other_forms', 'mastery', 'next_review']], use_container_width=True)

    # 重複挑戰邏輯
    if st.session_state.duplicate_word:
        st.error(f"Collision: '{st.session_state.duplicate_word}' exists.")
        if st.button("⚔️ Force Challenge"):
            st.session_state.force_quiz_word = st.session_state.duplicate_word
            st.session_state.duplicate_word = False; st.rerun()
    if st.session_state.force_quiz_word:
        q_ans = st.text_input(f"Verify '{st.session_state.force_quiz_word}':")
        if st.button("CONFIRM"):
            if q_ans.lower() == st.session_state.force_quiz_word.lower():
                st.session_state.show_balloons = True; st.session_state.force_quiz_word = False; st.rerun()

# 模組 B: Flash Pulse
elif choice == "🎯 Flash Pulse":
    st.markdown("<h1 class='main-title'>🎯 Flash Pulse</h1>", unsafe_allow_html=True)
    raw_data = load_data()
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    
    if not st.session_state.quiz_state['word']:
        if due: st.session_state.quiz_state['word'] = random.choice(due)['word']
        else: st.success("✨ Matrix Stable."); st.stop()

    target = next((w for w in due if w['word'] == st.session_state.quiz_state['word']), None)
    if target:
        st.info(f"💡 Cue: {target['meaning_zh']}")
        st.markdown(f"[🔊 Listen](https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target['word'].replace(' ', '-')})")
        ans = st.text_input("Entry Input:")
        if st.button("EXECUTE"):
            if ans.strip().lower() == target['word'].lower():
                st.session_state.show_balloons = True
                new_m = min(5, target['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{target['id']}", json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                st.session_state.quiz_state['word'] = None; st.rerun()

# 模組 C: Ebbing Log
elif choice == "📅 Ebbing Log":
    st.markdown("<h1 class='main-title'>📅 Ebbing Log</h1>", unsafe_allow_html=True)
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        st.subheader("📈 Retention Projection (7-Day Forecast)")
        f_dates = [date.today() + timedelta(days=i) for i in range(8)]
        f_counts = [len(df[df['date'] <= d]) for d in f_dates]
        st.area_chart(pd.DataFrame({"Date": f_dates, "Load": f_counts}).set_index("Date"))
        c1, c2, c3 = st.columns(3)
        c1.metric("Due Today", len(df[df['date'] <= date.today()]))
        c2.metric("Total Nodes", len(df))
        c3.metric("Stability (L5)", f"{int(len(df[df['mastery']==5])/len(df)*100)}%")