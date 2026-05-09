import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import plotly.graph_objects as go

# --- 1. UI 與 視覺配置 ---
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

# --- 2. 核心 API 與 艾賓浩斯邏輯 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {
    "apikey": KEY, 
    "Authorization": f"Bearer {KEY}", 
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def get_next_date(mastery):
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    return (date.today() + timedelta(days=curve.get(mastery, 1))).strftime('%Y-%m-%d')

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 3. 數據初始化 ---
raw_data = load_data()
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
due_count = 0
if not df.empty:
    due_count = len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()])

# --- 4. 側邊導航 ---
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)
pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", pulse_label, "📅 Ebbing Log"])

# --- 5. 核心模組 ---
if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize Node", "🔍 View Matrix", "📝 Modify Protocol"])

    # --- [A] 新增模式 (全欄位) ---
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
            f_coll = st.text_input("Collocations (慣用搭配)")
            f_en = st.text_area("English Definition")
            f_ex = st.text_area("Context Sentence")
            
            if st.form_submit_button("🚀 SYNC TO CORE"):
                if f_word.strip() and f_mean.strip():
                    payload = {
                        "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": f_pos, # 傳送 List
                        "other_forms": f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else "",
                        "synonyms": f_syn, "collocations": f_coll, "meaning_en": f_en, "example": f_ex,
                        "mastery": 1, "next_review": get_next_date(1)
                    }
                    httpx.post(f"{URL}/rest/v1/vocabulary", json={k:v for k,v in payload.items() if v}, headers=HEADERS)
                    st.rerun()

    # --- [B] 分區檢視 (具備 L5 篩選) ---
    with t_view:
        if not df.empty:
            v_f = st.radio("Filter", ["Due Today", "All Nodes", "L5 Mastered"], horizontal=True)
            d_df = df.copy()
            if v_f == "Due Today": d_df = d_df[pd.to_datetime(d_df['next_review']).dt.date <= date.today()]
            elif v_f == "L5 Mastered": d_df = d_df[d_df['mastery'] >= 5]
            st.dataframe(d_df[['word', 'meaning_zh', 'mastery', 'next_review', 'other_forms']], use_container_width=True)

    # --- [C] 修改模式 (全欄位對等 + 深度修正 Array 錯誤) ---
    with t_edit:
        if not df.empty:
            target = st.selectbox("Select Word to Modify", options=df['word'].tolist())
            row = df[df['word'] == target].iloc[0]
            
            # 三態解析
            v_parts = row.get('other_forms', '').split(' / ') if row.get('other_forms') else ["", "", ""]
            while len(v_parts) < 3: v_parts.append("")
            
            # 劍橋發音
            st.link_button(f"🔊 Cambridge Audio: {target}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target.replace(' ', '-')}")
            
            with st.form("edit_protocol_final"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry", value=row['word'])
                u_mean = e2.text_input("Definition", value=row['meaning_zh'])
                
                # 日期解析
                dt_val = datetime.strptime(str(row['next_review'])[:10], '%Y-%m-%d').date()
                u_date = st.date_input("Manual Review Date", value=dt_val)
                
                st.write("---")
                ev1, ev2, ev3 = st.columns(3)
                u_v1, u_v2, u_v3 = ev1.text_input("V1", v_parts[0]), ev2.text_input("V2", v_parts[1]), ev3.text_input("V3", v_parts[2])
                
                # 詞性 (解決 22P02 的關鍵：確保預設值也是 List)
                raw_pos = row.get('pos', [])
                if isinstance(raw_pos, str): 
                    current_pos = [p.strip() for p in raw_pos.strip('{}').split(',') if p]
                else: 
                    current_pos = raw_pos if raw_pos else []
                
                u_pos = st.multiselect("Class", ["n.", "v.", "adj.", "adv.", "phr.", "prep."], default=current_pos)
                
                u_syn = st.text_input("Synonyms", value=row.get('synonyms',''))
                u_coll = st.text_input("Collocations", value=row.get('collocations',''))
                u_en = st.text_area("English Def", value=row.get('meaning_en',''))
                u_ex = st.text_area("Example Sentence", value=row.get('example',''))
                
                if st.form_submit_button("✅ UPDATE NODE"):
                    # 這是最關鍵的一步：確保 pos 不管怎樣都是 List，即使使用者沒選也是 []
                    upd = {
                        "word": u_word, "meaning_zh": u_mean, 
                        "pos": u_pos if u_pos is not None else [], 
                        "next_review": u_date.strftime('%Y-%m-%d'),
                        "other_forms": f"{u_v1} / {u_v2} / {u_v3}" if u_v1 else "",
                        "synonyms": u_syn, "collocations": u_coll, "meaning_en": u_en, "example": u_ex
                    }
                    resp = httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd, headers=HEADERS)
                    if resp.status_code < 300:
                        st.success(f"Synchronized!"); st.rerun()
                    else:
                        st.error(f"Sync Failed: {resp.text}")

elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    if due:
        q = random.choice(due)
        st.info(f"💡 Cue: {q['meaning_zh']}")
        ans = st.text_input("Verify Entry:")
        if st.button("EXECUTE"):
            if ans.lower() == q['word'].lower():
                st.success("Correct!"); st.balloons()
                new_m = min(5, q['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{q['id']}", json={"mastery": new_m, "next_review": get_next_date(new_m)}, headers=HEADERS)
                st.rerun()
    else: st.success("Matrix Stable.")

elif "Ebbing Log" in choice:
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)
    if not df.empty:
        v_d = st.select_slider("Forecast Dimension", options=[7, 30, 90, 180, 365], value=30)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        dates = [date.today() + timedelta(days=i) for i in range(v_d + 1)]
        counts = [len(df[df['date'] <= d]) for d in dates]
        fig = go.Figure(go.Scatter(x=dates, y=counts, mode='lines+markers', line=dict(color='#2d3436')))
        fig.update_layout(plot_bgcolor='white', margin=dict(l=0, r=0, t=10, b=0), height=400)
        st.plotly_chart(fig, use_container_width=True)