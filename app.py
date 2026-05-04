import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 ---
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0, 'msg': None, 'msg_type': None}
if 'show_balloons' not in st.session_state: st.session_state.show_balloons = False
if 'duplicate_word' not in st.session_state: st.session_state.duplicate_word = None

if st.session_state.get('show_balloons'):
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. 連線資訊與常數 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
POS_OPTIONS = ["n. (名詞)", "v. (動詞)", "adj. (形容詞)", "adv. (副詞)", "phr. (慣用語)", "Term. (專業術語)"]
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}

# --- 4. 功能函式 ---
def get_next_review_date(mastery_level):
    days = INTERVALS.get(mastery_level, 0)
    return str(date.today() + timedelta(days=days))

def load_data():
    api_url = f"{URL}/rest/v1/vocabulary?select=*&order=id.desc"
    try:
        response = httpx.get(api_url, headers=HEADERS)
        return response.json()
    except: return []

def update_supabase(word_id, payload):
    api_url = f"{URL}/rest/v1/vocabulary?id=eq.{word_id}"
    try:
        response = httpx.patch(api_url, json=payload, headers=HEADERS)
        return response.status_code < 400
    except: return False

# --- 5. 側邊欄導航 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix")
    choice = st.radio("功能清單", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()

# --- 6. 頁面分流 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()

    # A. 新增單字 (略，保持不變)
    with st.expander("➕ 新增單字"):
        # ... (這裡維持之前的 Form 代碼，確保有 submit_button)
        st.write("新增單字表單...")

    # B. 編輯區
    if raw_data:
        st.divider()
        search_list = [w.get('word', 'Unknown') for w in raw_data]
        search_word = st.selectbox("🔍 選擇單字進行修改：", search_list)
        target_w = next((w for w in raw_data if w.get('word') == search_word), None)
        
        if target_w:
            with st.container(border=True):
                edit_mode = st.toggle("✏️ 修改資料內容")
                if edit_mode:
                    # 修復問題：確保 form 結構完整
                    with st.form(key=f"edit_form_{target_w['id']}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            u_word = st.text_input("單字", value=target_w.get('word',''))
                            # 強化：防止 pos 字串切割報錯
                            old_pos = target_w.get('pos') or ""
                            d_pos = [p.strip() for p in old_pos.split(',')] if isinstance(old_pos, str) else []
                            u_pos = st.multiselect("詞性", POS_OPTIONS, default=[p for p in d_pos if p in POS_OPTIONS])
                            u_cat = st.text_input("類別", value=target_w.get('category',''))
                            u_mas = st.number_input("等級", 0, 5, value=int(target_w.get('mastery', 0)))
                        with c2:
                            u_mean = st.text_input("中文", value=target_w.get('meaning_zh',''))
                            u_syn = st.text_input("同義詞", value=target_w.get('synonyms',''))
                            u_coll = st.text_input("搭配", value=target_w.get('collocations',''))
                            u_forms = st.text_input("三態變化", value=target_w.get('other_forms',''))
                        
                        u_def = st.text_area("定義", value=target_w.get('meaning_en',''))
                        u_ex = st.text_area("例句", value=target_w.get('example',''))
                        
                        # 關鍵：Submit Button 必須在 form 縮排內
                        submitted = st.form_submit_button("💾 儲存修改")
                        if submitted:
                            up_payload = {
                                "word": u_word, "pos": ", ".join(u_pos), "meaning_zh": u_mean,
                                "category": u_cat, "mastery": u_mas, "synonyms": u_syn,
                                "collocations": u_coll, "other_forms": u_forms,
                                "meaning_en": u_def, "example": u_ex
                            }
                            if update_supabase(target_w['id'], up_payload):
                                st.success("✅ 更新成功！")
                                st.rerun()
                else:
                    st.subheader(f"🔤 {target_w.get('word')}")
                    st.write(f"**中文：** {target_w.get('meaning_zh')}")

elif choice == "🎯 訓練模式":
    st.title("🎯 深度訓練模式")
    raw_data = load_data()
    today_str = str(date.today())
    
    # 🔥 修正點：安全篩選 target_list，處理 None 值
    target_list = []
    for w in raw_data:
        nr = w.get('next_review')
        # 如果 next_review 是空的，我們把它當作今天需要複習
        if nr is None or str(nr) <= today_str:
            target_list.append(w)

    if target_list:
        # (這裡接你之前的訓練測驗邏輯...)
        st.write(f"今天有 {len(target_list)} 個單字待複習")
        # ...
    else:
        st.success("🎉 今日複習已全數完成！")