import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import plotly.graph_objects as go

# --- 1. 核心視覺配置 ---
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
    </style>
""", unsafe_allow_html=True)

# --- 2. API 與 艾賓浩斯演算法 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}

def get_ebbinghaus_date(mastery):
    # 艾賓浩斯階段：0(當天), 1(1天), 2(3天), 3(7天), 4(14天), 5(30天)
    curve = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    days = curve.get(mastery, 1)
    return (date.today() + timedelta(days=days)).strftime('%Y-%m-%d')

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=next_review.asc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 3. 數據初始化 ---
raw_data = load_data()
df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()
due_count = len(df[pd.to_datetime(df['next_review']).dt.date <= date.today()]) if not df.empty else 0

# --- 4. 側邊導航 ---
st.sidebar.markdown("<h2 style='color: #2d3436;'>⚡ Qurate Pro</h2>", unsafe_allow_html=True)
pulse_label = f"🎯 Flash Pulse {'🔴' if due_count > 0 else ''}"
choice = st.sidebar.radio("SYSTEM ACCESS", ["📋 Matrix Core", pulse_label, "📅 Ebbing Log"])
if st.sidebar.button("🔄 Force Sync Matrix"):
    st.cache_data.clear() # 如果你有用 @st.cache_data 的話
    st.rerun()
# --- 5. 核心模組 ---

if "Matrix Core" in choice:
    st.markdown("<div class='main-title'>Matrix Core</div>", unsafe_allow_html=True)
    t_add, t_view, t_edit = st.tabs(["➕ Initialize Node", "🔍 View Matrix", "📝 Modify Protocol"])
# [A] 新增模式
    with t_add:
        with st.form("add_matrix_form", clear_on_submit=True):
        # ... 你的輸入欄位 ...
            f_word = st.text_input("Entry (單字)*")
            f_mean = st.text_input("Definition (中文)*")
        # ... 其他欄位 ...
        
        if st.form_submit_button("🚀 SYNC TO CORE"):
            if f_word.strip() and f_mean.strip():
                payload = {
                    "word": f_word.strip(),
                    "meaning_zh": f_mean.strip(),
                    "pos": f_pos if f_pos else [], 
                    "mastery": 1,
                    "next_review": get_ebbinghaus_date(1)
                    # ... 其他欄位 ...
                }
                
                # 發送請求
                resp = httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                
                if resp.status_code < 300:
                    st.success("🎉 新增成功！正在更新矩陣...")
                    
                    # --- 關鍵：強制重新執行 ---
                    st.rerun() 
                else:
                    st.error(f"同步失敗：{resp.text}")
    # --- [B] 分區檢視 (具備篩選邏輯) ---
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
                use_container_width=True, hide_index=True
            )
        else:
            st.info("Matrix is currently empty.")

    # --- [C] 修改模式 (完全對等新增模式的欄位) ---
    with t_edit:
        if not df.empty:
            target_word = st.selectbox("Select Target Node", options=df['word'].tolist())
            row = df[df['word'] == target_word].iloc[0]
            
            # 解析現有三態
            v_parts = row.get('other_forms', '').split(' / ') if row.get('other_forms') else ["", "", ""]
            while len(v_parts) < 3: v_parts.append("")
            
            # 劍橋發音與外部連結
            st.link_button(f"🔊 Cambridge Pronunciation: {target_word}", f"https://dictionary.cambridge.org/dictionary/english-chinese-traditional/{target_word.replace(' ', '-')}")
            
            with st.form("edit_matrix_form"):
                e1, e2 = st.columns(2)
                u_word = e1.text_input("Entry (單字)*", value=row['word'])
                u_mean = e2.text_input("Definition (中文)*", value=row['meaning_zh'])
                
                # 艾賓浩斯手動日期調整
                dt_cur = datetime.strptime(str(row['next_review'])[:10], '%Y-%m-%d').date()
                u_date = st.date_input("Manual Schedule (複習日期)", value=dt_cur)
                
                st.write("---")
                st.caption("Morphology (動詞三態變化)")
                ev1, ev2, ev3 = st.columns(3)
                u_v1 = ev1.text_input("V1 (Base)", value=v_parts[0])
                u_v2 = ev2.text_input("V2 (Past)", value=v_parts[1])
                u_v3 = ev3.text_input("V3 (Participle)", value=v_parts[2])
                
                st.write("---")
                # 解決 st.multiselect 報錯的防禦性解析
                pos_options = ["n.", "v.", "adj.", "adv.", "phr.", "prep."]
                db_pos = row.get('pos', [])
                if isinstance(db_pos, str):
                    current_pos = [p.strip() for p in db_pos.strip('{}').split(',') if p in pos_options]
                elif isinstance(db_pos, list):
                    current_pos = [p for p in db_pos if p in pos_options]
                else:
                    current_pos = []
                
                u_pos = st.multiselect("Class (詞性)", pos_options, default=current_pos)
                
                ec3, ec4 = st.columns(2)
                u_syn = ec3.text_input("Synonyms (同義詞)", value=row.get('synonyms', ''))
                u_coll = ec4.text_input("Collocations (慣用搭配)", value=row.get('collocations', ''))
                
                u_en = st.text_area("English Definition", value=row.get('meaning_en', ''))
                u_ex = st.text_area("Context Example", value=row.get('example', ''))
                
                if st.form_submit_button("✅ UPDATE MATRIX"):
                    def empty_to_none(v):
                        return v if v and v.strip() else None
                    upd_payload = {
                        "word": u_word, "meaning_zh": u_mean, 
                        "pos": u_pos if u_pos else [],
                        "next_review": u_date.strftime('%Y-%m-%d'),
                        "other_forms": f"{u_v1} / {u_v2} / {u_v3}" if u_v1 else None,
                        "synonyms": empty_to_none(u_syn),
                        "collocations": empty_to_none(u_coll),
                        "meaning_en": empty_to_none(u_en),
                        "example": empty_to_none(u_ex)
                    }
                    payload = {
                        "word": f_word.strip(), "meaning_zh": f_mean.strip(), 
                        "pos": f_pos if f_pos else [],
                        "other_forms": f"{f_v1} / {f_v2} / {f_v3}" if f_v1 else None,
                        "synonyms": f_syn if f_syn.strip() else None,  # 加這個
                        "collocations": f_coll if f_coll.strip() else None,  # 加這個
                        "meaning_en": f_en if f_en.strip() else None,  # 加這個
                        "example": f_ex if f_ex.strip() else None,  # 加這個
                        "mastery": 1, "next_review": get_ebbinghaus_date(1)
                    }
                    resp = httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd_payload, headers=HEADERS)
                    if resp.status_code < 300:
                        st.success("Node Synchronized!"); st.rerun()
                    else:
                        st.error(f"Update Failed: {resp.text}")

# --- 6. 重複挑戰 (Flash Pulse) ---
elif "Flash Pulse" in choice:
    st.markdown("<div class='main-title'>Flash Pulse</div>", unsafe_allow_html=True)
    # 篩選今天到期的單字
    due = [w for w in raw_data if str(w.get('next_review'))[:10] <= str(date.today())]
    
    if due:
        q = random.choice(due)
        st.info(f"💡 Cue: {q['meaning_zh']}")
        if q.get('example'): st.caption(f"Context: {q['example'].replace(q['word'], '____')}")
        
        ans = st.text_input("Type the correct Entry (不分大小寫):")
        if st.button("EXECUTE VERIFICATION"):
            if ans.strip().lower() == q['word'].lower():
                st.success("Correct! Matrix Evolved.")
                st.balloons()
                new_m = min(5, q['mastery'] + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{q['id']}", 
                            json={"mastery": new_m, "next_review": get_ebbinghaus_date(new_m)}, headers=HEADERS)
                st.rerun()
            else:
                st.error("Verification Failed. Try again.")
    else:
        st.success("Matrix Stable. No nodes due for review.")

# --- 7. 線型預測圖表 (Ebbing Log) ---
elif "Ebbing Log" in choice:
    st.markdown("<div class='main-title'>Ebbing Log</div>", unsafe_allow_html=True)
    if not df.empty:
        v_d = st.select_slider("Forecast Horizon (Days)", options=[7, 14, 30, 90, 180, 365], value=30)
        df['date'] = pd.to_datetime(df['next_review']).dt.date
        
        # 建立預測數列
        dates = [date.today() + timedelta(days=i) for i in range(v_d + 1)]
        counts = [len(df[df['date'] <= d]) for d in dates]
        
        # 純線型圖 (無填充面積)
        fig = go.Figure(go.Scatter(
            x=dates, y=counts, 
            mode='lines+markers', 
            line=dict(color='#2d3436', width=3),
            marker=dict(size=8, color='#ff7675'),
            name="Cumulative Due"
        ))
        
        fig.update_layout(
            plot_bgcolor='white',
            hovermode='x unified',
            margin=dict(l=0, r=0, t=20, b=0),
            height=450,
            xaxis=dict(showgrid=True, gridcolor='#f0f0f0', title="Review Date"),
            yaxis=dict(showgrid=True, gridcolor='#f0f0f0', title="Total Words Due")
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for log prediction.")