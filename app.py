import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import plotly.graph_objects as go

# --- 1. 極致視覺優化 (深碳黑風格 + 零多餘空白) ---
st.set_page_config(page_title="Qurate Pro", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        /* 消除頂部空白但保留側邊欄按鈕 */
        [data-testid="stHeader"] { background: rgba(0,0,0,0); height: 3rem !important; }
        .block-container { padding-top: 0rem !important; padding-bottom: 0rem !important; }
        footer { visibility: hidden; }
        
        /* 標題與字體：質感深碳黑 (#2d3436) */
        .main-title {
            color: #2d3436; 
            font-weight: 800; font-size: 2.2rem; 
            margin-bottom: 0.8rem; letter-spacing: -1px;
            padding-top: 0.5rem;
        }
        
        /* 按鈕風格 */
        .stButton > button {
            width: 100%; border-radius: 12px; height: 3.2rem;
            background: #2d3436; color: white; font-weight: bold; border: none;
        }
        
        /* 手機端適配 */
        input { font-size: 16px !important; }
        @media (max-width: 768px) {
            .main-title { font-size: 1.8rem; padding-top: 1rem; }
            .block-container { padding-top: 0rem !important; }
        }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心 API 與 艾賓浩斯演算法 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

def get_next_review_date(mastery):
    # 艾賓浩斯間隔：1, 3, 7, 14, 30天
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    return str(date.today() + timedelta(days=curve.get(mastery, 1)))

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 3. 系統狀態與通知處理 ---
if 'quiz_state' not in st.session_state: st.session_state.quiz_state = {'word': None}
if 'dup_word' not in st.session_state: st.session_state.dup_word = False
if 'force_quiz' not in st.session_state: st.session_state.force_quiz = False

raw_data = load_data()
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

# 檢查今日待辦 (紅點通知)
due_count = 0
if not df.empty:
    due_count = len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()])

# --- 4. 側邊導航 (紅點提醒) ---
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)
pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", pulse_label, "📅 Ebbing Log"])

# --- 5. 功能模組 ---

if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize", "🔍 View Matrix", "📝 Modify Protocol"])

    # --- [新增模式] ---
    with t_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("Entry (單字)*")
            f_mean = c2.text_input("Definition (中文)*")
            st.write("---")
            st.caption("Morphology (V1 / V2 / V3)")
            v1, v2, v3 = st.columns(3)
            f_v1, f_v2, f_v3 = v1.text_input("V1"), v2.text_input("V2"), v3.text_input("V3")
            st.write("---")
            f_pos = st.multiselect("Class", ["n.", "v.", "adj.", "adv.", "phr.", "prep."])
            c3, c4 = st.columns(2)
            f_syn = c3.text_input("Synonyms (同義詞)")
            f_coll = c4.text_input("Collocations (搭配)")
            f_en = st.text_area("English Definition")
            f_ex = st.text_area("Context Sentence")
            
            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    # 重複檢查
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.dup_word = f_word.strip()
                        st.rerun()
                    else:
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": ", ".join(f_pos),
                            "other_forms": f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else "",
                            "synonyms": f_syn, "collocations": f_coll, "meaning_en": f_en, "example": f_ex,
                            "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json={k:v for k,v in payload.items() if v}, headers=HEADERS)
                        st.balloons(); st.rerun()

    # --- [檢視模式] ---
    with t_view:
        if not df.empty:
            v_f = st.radio("Filter", ["Due Today", "All Nodes", "L5 Mastered"], horizontal=True)
            d_df = df.copy()
            if v_f == "Due Today": d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "L5 Mastered": d_df = d_df[d_df['mastery'] >= 5]
            st.dataframe(d_df[['word', 'meaning_zh', 'other_forms', 'mastery', 'next_review']], use_container_width=True)

    # --- [編輯模式：全欄位對等] ---
    with t_edit:
        if not df.empty:
            target = st.selectbox("Select Node", options=df['word'].tolist())
            row = df[df['word'] == target].iloc[0]
            v_parts = row.get('other_forms', '').split(' / ') if row.get('other_forms') else ["", "", ""]
            while len(v_parts) < 3: v_parts.append("")
            
            st.link_button(f"🔊 Cambridge Audio: {target}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target.replace(' ', '-')}")
            
            with st.form("full_edit_form"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry", value=row.get('word',''))
                u_mean = e2.text_input("Definition", value=row.get('meaning_zh',''))
                
                # 手動調整日期
                current_nr = datetime.strptime(str(row['next_review'])[:10], '%Y-%m-%d').date()
                u_date = st.date_input("Manual Next Review (自訂複習日)", value=current_nr)
                
                st.write("---")
                ev1, ev2, ev3 = st.columns(3)
                u_v1, u_v2, u_v3 = ev1.text_input("V1", v_parts[0]), ev2.text_input("V2", v_parts[1]), ev3.text_input("V3", v_parts[2])
                
                st.write("---")
                u_syn = st.text_input("Synonyms", value=row.get('synonyms',''))
                u_coll = st.text_input("Collocations", value=row.get('collocations',''))
                u_en = st.text_area("English Def", value=row.get('meaning_en',''))
                u_ex = st.text_area("Context", value=row.get('example', ''))
                
                if st.form_submit_button("✅ UPDATE MATRIX NODE"):
                    upd = {
                        "word": u_word, "meaning_zh": u_mean, "next_review": str(u_date),
                        "other_forms": f"{u_v1} / {u_v2} / {u_v3}" if u_v1 else "",
                        "synonyms": u_syn, "collocations": u_coll, "meaning_en": u_en, "example": u_ex
                    }
                    httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd, headers=HEADERS)
                    st.success("Synchronized."); st.rerun()

    # 重複錄入挑戰
    if st.session_state.dup_word:
        st.error(f"Collision: '{st.session_state.dup_word}' exists.")
        if st.button("⚔️ Force Challenge"):
            st.session_state.force_quiz = st.session_state.dup_word
            st.session_state.dup_word = False; st.rerun()
    if st.session_state.force_quiz:
        ans = st.text_input(f"Verify '{st.session_state.force_quiz}':")
        if st.button("CONFIRM"):
            if ans.lower() == st.session_state.force_quiz.lower():
                st.success("Verified."); st.session_state.force_quiz = False; st.rerun()

# --- 模組：Flash Pulse ---
elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    if due:
        q = random.choice(due)
        st.warning(f"🎯 Pending Tasks: {len(due)}")
        st.info(f"💡 Cue: {q['meaning_zh']}")
        ans = st.text_input("Input Entry:")
        if st.button("EXECUTE"):
            if ans.lower() == q['word'].lower():
                st.success("Correct!"); st.balloons()
                new_m = min(5, q['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{q['id']}", json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                st.rerun()
            else: st.error("Verification failed.")
    else: st.success("Matrix Stable. All nodes synchronized.")

# --- 模組：Ebbing Log (互動圖表) ---
elif choice == "📅 Ebbing Log":
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)
    if not df.empty:
        # 互動式預測觀測
        view_days = st.select_slider("Forecast Dimension", options=[7, 30, 90, 180, 365], value=30)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        dates = [date.today() + timedelta(days=i) for i in range(view_days + 1)]
        counts = [len(df[df['date'] <= d]) for d in dates]
        
        # Plotly 互動線型圖 (去面積陰影)
        fig = go.Figure(go.Scatter(
            x=dates, y=counts, 
            mode='lines+markers', 
            line=dict(color='#2d3436', width=3),
            name='Load'
        ))
        fig.update_layout(
            plot_bgcolor='white', 
            margin=dict(l=0, r=0, t=10, b=0), 
            height=400,
            xaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
            yaxis=dict(showgrid=True, gridcolor='#f0f0f0')
        )
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Due Today (🔴)", due_count)