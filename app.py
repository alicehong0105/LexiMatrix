import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import plotly.graph_objects as go

# --- 1. UI 風格與視覺優化 ---
st.set_page_config(page_title="Qurate Pro", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        [data-testid="stHeader"] { background: rgba(0,0,0,0); height: 3.5rem !important; }
        .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; }
        footer { visibility: hidden; }
        .main-title { color: #2d3436; font-weight: 800; font-size: 2.2rem; margin-bottom: 0.8rem; padding-top: 0.5rem; }
        .stButton > button { width: 100%; border-radius: 12px; height: 3.2rem; background: #2d3436; color: white; font-weight: bold; border: none; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心 API 與 艾賓浩斯演算法 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {
    "apikey": KEY, 
    "Authorization": f"Bearer {KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def get_next_review_date(mastery):
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    return (date.today() + timedelta(days=curve.get(mastery, 1))).strftime('%Y-%m-%d')

def load_data():
    try:
        # 強制刷新快取，解決「改了沒變」的問題
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 3. 初始化數據與通知 ---
raw_data = load_data()
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
due_count = 0
if not df.empty:
    due_count = len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()])

if 'dup_word' not in st.session_state: st.session_state.dup_word = False
if 'force_quiz' not in st.session_state: st.session_state.force_quiz = False

# --- 4. 側邊欄 (紅點通知) ---
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)
pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", pulse_label, "📅 Ebbing Log"])

# --- 5. 功能模組 ---

if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize Node", "🔍 View Matrix", "📝 Modify Protocol"])

    # [A] 新增模式
    with t_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("Entry (單字)*")
            f_mean = c2.text_input("Definition (中文)*")
            st.caption("Morphology (V1 / V2 / V3)")
            v1, v2, v3 = st.columns(3)
            f_v1, f_v2, f_v3 = v1.text_input("V1"), v2.text_input("V2"), v3.text_input("V3")
            f_pos = st.multiselect("Class", ["n.", "v.", "adj.", "adv.", "phr.", "prep."])
            f_syn = st.text_input("Synonyms (同義詞)")
            f_coll = st.text_input("Collocations (搭配)")
            f_en = st.text_area("English Definition")
            f_ex = st.text_area("Context Sentence")
            
            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    if any(w['word'].lower() == f_word.strip().lower() for w in raw_data):
                        st.session_state.dup_word = f_word.strip(); st.rerun()
                    else:
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": f_pos, # List 傳送
                            "other_forms": f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else "",
                            "synonyms": f_syn, "collocations": f_coll, "meaning_en": f_en, "example": f_ex,
                            "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json={k:v for k,v in payload.items() if v}, headers=HEADERS)
                        st.rerun()

    # [B] 分區檢視 (支援 L5 篩選)
    with t_view:
        if not df.empty:
            v_f = st.radio("Display Group", ["Due Today", "All Nodes", "L5 Mastered"], horizontal=True)
            d_df = df.copy()
            if v_f == "Due Today": d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "L5 Mastered": d_df = d_df[d_df['mastery'] >= 5]
            st.dataframe(d_df[['word', 'meaning_zh', 'mastery', 'next_review', 'other_forms']], use_container_width=True)

    # [C] 編輯模式 (全欄位對等 + 陣列格式修復)
    with t_edit:
        if not df.empty:
            target = st.selectbox("Select Word", options=df['word'].tolist())
            row = df[df['word'] == target].iloc[0]
            v_parts = row.get('other_forms', '').split(' / ') if row.get('other_forms') else ["", "", ""]
            while len(v_parts) < 3: v_parts.append("")
            
            st.link_button(f"🔊 Cambridge: {target}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target.replace(' ', '-')}")
            
            with st.form("edit_form_final"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry", value=row['word'])
                u_mean = e2.text_input("Definition", value=row['meaning_zh'])
                
                # 修復日期修改無效的問題
                dt_cur = datetime.strptime(str(row['next_review'])[:10], '%Y-%m-%d').date()
                u_date = st.date_input("Manual Next Review", value=dt_cur)
                
                st.write("---")
                ev1, ev2, ev3 = st.columns(3)
                u_v1, u_v2, u_v3 = ev1.text_input("V1", v_parts[0]), ev2.text_input("V2", v_parts[1]), ev3.text_input("V3", v_parts[2])
                
                # 修復 22P02 Array 錯誤
                cur_pos = row.get('pos', [])
                if isinstance(cur_pos, str): cur_pos = [p.strip() for p in cur_pos.split(",")]
                u_pos = st.multiselect("Class", ["n.", "v.", "adj.", "adv.", "phr.", "prep."], default=cur_pos)
                
                u_syn = st.text_input("Synonyms", value=row.get('synonyms',''))
                u_coll = st.text_input("Collocations", value=row.get('collocations',''))
                u_en = st.text_area("English Def", value=row.get('meaning_en',''))
                u_ex = st.text_area("Context", value=row.get('example',''))
                
                if st.form_submit_button("✅ UPDATE NODE"):
                    upd = {
                        "word": u_word, "meaning_zh": u_mean, "pos": u_pos, # 確保為 List
                        "next_review": u_date.strftime('%Y-%m-%d'),
                        "other_forms": f"{u_v1} / {u_v2} / {u_v3}" if u_v1 else "",
                        "synonyms": u_syn, "collocations": u_coll, "meaning_en": u_en, "example": u_ex
                    }
                    resp = httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd, headers=HEADERS)
                    if resp.status_code < 300:
                        st.success(f"Synchronized to {u_date}"); st.rerun()
                    else:
                        st.error(f"Error {resp.status_code}: {resp.text}")

    # 重複挑戰
    if st.session_state.dup_word:
        st.error(f"Duplicate Node: '{st.session_state.dup_word}'")
        if st.button("⚔️ Force Challenge"):
            st.session_state.force_quiz = st.session_state.dup_word
            st.session_state.dup_word = False; st.rerun()
    if st.session_state.force_quiz:
        ans = st.text_input(f"Verify Spelling '{st.session_state.force_quiz}':")
        if st.button("CONFIRM"):
            if ans.lower() == st.session_state.force_quiz.lower():
                st.success("Verified."); st.session_state.force_quiz = False; st.rerun()

elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    if due:
        q = random.choice(due)
        st.info(f"💡 Cue: {q['meaning_zh']}")
        ans = st.text_input("Type Entry:")
        if st.button("EXECUTE"):
            if ans.lower() == q['word'].lower():
                st.success("Correct!"); st.balloons()
                new_m = min(5, q['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{q['id']}", json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                st.rerun()
    else: st.success("Matrix Stable.")

elif "Ebbing Log" in choice:
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)
    if not df.empty:
        v_d = st.select_slider("Forecast Dimension", options=[7, 30, 90, 180, 365], value=30)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        dates = [date.today() + timedelta(days=i) for i in range(v_d + 1)]
        counts = [len(df[df['date'] <= d]) for d in dates]
        fig = go.Figure(go.Scatter(x=dates, y=counts, mode='lines+markers', line=dict(color='#2d3436', width=3)))
        fig.update_layout(plot_bgcolor='white', margin=dict(l=0, r=0, t=10, b=0), height=400, xaxis=dict(showgrid=True, gridcolor='#f0f0f0'))
        st.plotly_chart(fig, use_container_width=True)