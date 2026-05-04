import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random

# --- 1. 網頁基本設定 (全域唯一) ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 (保留你原本的邏輯) ---
if 'show_balloons' not in st.session_state: st.session_state.show_balloons = False
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0, 'msg': None, 'msg_type': None}

if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. Supabase 連線設定 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
headers = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# --- 4. 功能函式 (遺忘曲線與資料處理) ---
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}

def load_data_from_supabase():
    api_url = f"{URL}/rest/v1/vocabulary?select=*&order=id.desc"
    try:
        response = httpx.get(api_url, headers=headers)
        return response.json()
    except: return []

def add_word_to_supabase(payload):
    api_url = f"{URL}/rest/v1/vocabulary"
    response = httpx.post(api_url, json=payload, headers=headers)
    return response.status_code == 201

# --- 5. 側邊欄導航 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix 導航")
    choice = st.radio("功能切換：", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()

# --- 6. 頁面邏輯分流 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫總表")
    
    # 這裡顯示資料庫清單
    data = load_data_from_supabase()
    if data:
        st.dataframe(pd.DataFrame(data), use_container_width=True)
    
    st.divider()
    
    # 這裡放唯一的「新增單字」區塊
    with st.expander("➕ 新增單字至矩陣"):
        c1, c2 = st.columns(2)
        with c1:
            w = st.text_input("英文單字*", key="new_w")
            p = st.multiselect("詞性", ["n.", "v.", "adj.", "adv.", "phr.", "Term."], key="new_p")
        with c2:
            z = st.text_input("中文解釋*", key="new_z")
            cat = st.text_input("類別", value="未分類", key="new_cat")
        
        ex = st.text_area("例句內容", key="new_ex")
        
        if st.button("🚀 確認儲存"):
            if w and z:
                payload = {
                    "word": w, "pos": ", ".join(p), "meaning_zh": z,
                    "example": ex, "category": cat, "mastery": 1,
                    "next_review": str(date.today() + timedelta(days=1))
                }
                if add_word_to_supabase(payload):
                    st.session_state.show_balloons = True
                    st.success("存入成功！")
                    st.rerun()

elif choice == "🎯 訓練模式":
    st.title("🎯 單字訓練模式")
    # 這裡放你原本寫在 quiz_state 裡的邏輯
    st.write("🏃 測驗功能載入中...")
    if st.button("開始隨機測驗"):
        data = load_data_from_supabase()
        if data:
            target = random.choice(data)
            st.write(f"請回答這個單字的意思：**{target['word']}**")
            # 這裡可以接你原本的輸入與檢查邏輯

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程")
    st.write("根據 INTERVALS 計算的複習清單...")