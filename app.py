import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random

# --- 1. 頁面配置與高級感介面 ---
st.set_page_config(page_title="Qurate Pro", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        [data-testid="stHeader"] { visibility: hidden; }
        footer { visibility: hidden; }
        .main-title {
            background: linear-gradient(90deg, #007bff, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 800; font-size: 2.2rem; margin-bottom: 0.5rem;
        }
        .stButton > button {
            width: 100%; border-radius: 12px; height: 3.5rem;
            background: linear-gradient(135deg, #6e8efb, #a777e3);
            color: white; font-weight: bold; border: none;
        }
        input { font-size: 16px !important; }
        .mobile-hint { color: #888; font-size: 0.8rem; margin-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 核心功能與演算法 ---
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

# --- 3. 狀態初始化 ---
for key in ['quiz_state', 'duplicate_word', 'force_quiz_word']:
    if key not in st.session_state:
        st.session_state[key] = {'word': None} if key == 'quiz_state' else False

# --- 4. 側邊欄導航 ---
st.sidebar.markdown("<h1 style='color: #007bff;'>⚡ Qurate Pro</h1>", unsafe_allow_html=True)
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", "🎯 Flash Pulse", "📅 Ebbing Log"])
st.sidebar.caption("💡 手機端請點擊左上角 ☰ 切換功能")

# --- 5. 功能模組 ---

if choice == "📋 Matrix Core":
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    raw_data = load_data()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    t_add, t_view, t_edit = st.tabs(["➕ Initialize", "🔍 View Matrix", "📝 Modify Protocol"])

    # --- 增加模式 ---
    with t_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("Entry (單字)*")
            f_mean = c2.text_input("Definition (中文)*")
            
            st.write("---")
            st.caption("Morphology (動詞三態變化)")
            v1, v2, v3 = st.columns(3)
            f_v1 = v1.text_input("V1 (Base)")
            f_v2 = v2.text_input("V2 (Past)")
            f_v3 = v3.text_input("V3 (P.P.)")
            
            st.write("---")
            f_pos = st.multiselect("Class (詞性)", ["n.", "v.", "adj.", "adv.", "phr."])
            c3, c4 = st.columns(2)
            f_syn = c3.text_input("Synonyms (同義詞)")
            f_coll = c4.text_input("Collocations (搭配)")
            
            f_en = st.text_area("English Definition")
            f_ex = st.text_area("Context Sentence")
            
            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.duplicate_word = f_word.strip()
                        st.rerun()
                    else:
                        variants = f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else ""
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": ", ".join(f_pos),
                            "other_forms": variants, "synonyms": f_syn, "collocations": f_coll,
                            "meaning_en": f_en, "example": f_ex, "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json={k:v for k,v in payload.items() if v}, headers=HEADERS)
                        st.balloons(); st.rerun()

    # --- 檢視模式 ---
    with t_view:
        if not df.empty:
            v_f = st.radio("Display Protocol", ["Due Today", "All Nodes", "Mastered (L5)"], horizontal=True)
            search = st.text_input("🔍 Search Matrix...")
            d_df = df.copy()
            if v_f == "Due Today": d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "Mastered (L5)": d_df = d_df[d_df['mastery'] >= 5]
            if search: d_df = d_df[d_df['word'].str.contains(search, case=False)]
            st.dataframe(d_df[['word', 'meaning_zh', 'other_forms', 'mastery', 'next_review']], use_container_width=True)

    # --- 編輯模式 (補齊所有欄位) ---
    with t_edit:
        if not df.empty:
            target = st.selectbox("Select Node to Modify", options=df['word'].tolist())
            row = df[df['word'] == target].iloc[0]
            
            # 解析原本的三態
            v_list = row.get('other_forms', '').split(' / ') if row.get('other_forms') else ["", "", ""]
            while len(v_list) < 3: v_list.append("")

            # 劍橋發音
            st.link_button(f"🔊 Cambridge Pronunciation: {target}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target.replace(' ', '-')}")
            
            with st.form("edit_protocol_form"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry", value=row.get('word',''))
                u_mean = e2.text_input("Definition (中文)", value=row.get('meaning_zh',''))
                
                st.caption("Morphology (V1 / V2 / V3)")
                ev1, ev2, ev3 = st.columns(3)
                u_v1 = ev1.text_input("V1", value=v_list[0])
                u_v2 = ev2.text_input("V2", value=v_list[1])
                u_v3 = ev3.text_input("V3", value=v_list[2])
                
                st.write("---")
                e3, e4 = st.columns(2)
                u_syn = e3.text_input("Synonyms (同義詞)", value=row.get('synonyms',''))
                u_coll = e4.text_input("Collocations (搭配)", value=row.get('collocations',''))
                
                u_en = st.text_area("English Definition", value=row.get('meaning_en',''))
                u_ex = st.text_area("Context Sentence", value=row.get('example',''))
                
                if st.form_submit_button("✅ UPDATE MATRIX NODE"):
                    new_variants = f"{u_v1} / {u_v2} / {u_v3}" if u_v1 else ""
                    upd_payload = {
                        "word": u_word, "meaning_zh": u_mean, "other_forms": new_variants,
                        "synonyms": u_syn, "collocations": u_coll, 
                        "meaning_en": u_en, "example": u_ex
                    }
                    httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd_payload, headers=HEADERS)
                    st.success("Protocol Updated."); st.rerun()

    # 重複挑戰
    if st.session_state.duplicate_word:
        st.error(f"Duplicate Node: '{st.session_state.duplicate_word}' already exists.")
        if st.button("⚔️ Start Force Challenge"):
            st.session_state.force_quiz_word = st.session_state.duplicate_word
            st.session_state.duplicate_word = False; st.rerun()
    if st.session_state.force_quiz_word:
        q_ans = st.text_input(f"Verify Entry '{st.session_state.force_quiz_word}':")
        if st.button("VERIFY"):
            if q_ans.lower() == st.session_state.force_quiz_word.lower():
                st.success("Verification Success."); st.session_state.force_quiz_word = False; st.rerun()

elif choice == "🎯 Flash Pulse":
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)
    raw_data = load_data()
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    if due:
        q = random.choice(due)
        st.info(f"💡 Cue: {q['meaning_zh']}")
        ans = st.text_input("Input Entry:")
        if st.button("EXECUTE"):
            if ans.lower() == q['word'].lower():
                st.success("Correct!"); st.balloons()
                new_m = min(5, q['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{q['id']}", json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                st.rerun()
            else: st.error("Inconsistent Node.")
    else: st.success("Matrix Stable.")

elif choice == "📅 Ebbing Log":
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        st.subheader("📈 Retention Forecast (Line)")
        f_dates = [date.today() + timedelta(days=i) for i in range(8)]
        f_counts = [len(df[df['date'] <= d]) for d in f_dates]
        chart_data = pd.DataFrame({"Date": f_dates, "Cumulative Load": f_counts}).set_index("Date")
        st.line_chart(chart_data) # 純線型圖表
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Due Today", len(df[df['date'] <= date.today()]))
        c2.metric("Total Nodes", len(df))
        c3.metric("L5 Mastered", len(df[df['mastery'] == 5]))