import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random

# --- 1. 網頁基本設定 (必須在最前面) ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 (解決 AttributeError 的關鍵) ---
state_defaults = {
    'quiz_state': {'word': None, 'meaning': None, 'attempts': 0},
    'sudden_quiz_state': {'attempts': 0, 'msg': None, 'msg_type': None},
    'duplicate_word': None,
    'force_quiz_word': None,
    'show_balloons': False
}

for key, value in state_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. 連線資訊與常數 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
POS_OPTIONS = ["n.", "v.", "adj.", "adv.", "phr.", "Term."]
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}

# --- 4. 功能函式庫 ---
def get_next_review_date(mastery_level):
    days = INTERVALS.get(mastery_level, 0)
    return str(date.today() + timedelta(days=days))

def load_data():
    api_url = f"{URL}/rest/v1/vocabulary?select=*&order=id.desc"
    try:
        response = httpx.get(api_url, headers=HEADERS)
        return response.json()
    except: return []

# --- 5. 側邊欄導航 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix")
    choice = st.radio("功能清單", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()
    if st.button("♻️ 重新整理頁面"):
        st.rerun()

# --- 6. 頁面分流邏輯 ---

# --- A. 管理矩陣頁面 ---
if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()

    # --- 功能 1：新增單字 (收納在 expander) ---
    with st.expander("➕ 新增單字至雲端", expanded=False):
        with st.form("add_word_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                word = st.text_input("英文單字*")
                pos = st.multiselect("詞性", POS_OPTIONS)
                cat = st.text_input("類別", "未分類")
            with c2:
                mean = st.text_input("中文翻譯*")
                syn = st.text_input("同義詞")
                forms = st.text_input("三態/變化")
            
            en_def = st.text_area("英文定義")
            example = st.text_area("例句")
            
            if st.form_submit_button("💾 儲存"):
                if word.strip() and mean.strip():
                    duplicate = next((w for w in raw_data if w['word'].lower() == word.strip().lower()), None)
                    if duplicate:
                        st.session_state.duplicate_word = word.strip()
                        st.rerun()
                    else:
                        payload = {
                            "word": word.strip(), "pos": ", ".join(pos), "meaning_zh": mean,
                            "meaning_en": en_def, "example": example, "category": cat,
                            "synonyms": syn, "other_forms": forms, "mastery": 1,
                            "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        st.success("成功錄入！")
                        st.rerun()
                else: st.error("必填項(*)未填")

    # --- 功能 2：突擊測驗邏輯 ---
    if st.session_state.duplicate_word:
        dw = st.session_state.duplicate_word
        st.warning(f"⚠️ 「{dw}」已存在！")
        if st.button(f"⚔️ 對「{dw}」發動突擊測驗"):
            st.session_state.force_quiz_word = dw
            st.session_state.duplicate_word = None
            st.rerun()

    if st.session_state.force_quiz_word:
        quiz = next((w for w in raw_data if w['word'].lower() == st.session_state.force_quiz_word.lower()), None)
        if quiz:
            st.info(f"🔥 突擊測驗！中文提示：{quiz['meaning_zh']}")
            ans = st.text_input("請輸入拼寫：", key="sudden_quiz_input")
            if st.button("送出"):
                if ans.strip().lower() == quiz['word'].lower():
                    st.session_state.show_balloons = True
                    st.success("答對了！")
                    st.session_state.force_quiz_word = None
                    st.rerun()
                else:
                    st.error("答錯了！")

    # --- 功能 3：編輯與預覽 ---
    st.divider()
    if raw_data:
        search_word = st.selectbox("🔍 選擇或搜尋單字：", [w['word'] for w in raw_data])
        target_w = next((w for w in raw_data if w['word'] == search_word), None)
        
        if target_w:
            with st.container(border=True):
                edit_on = st.toggle("✏️ 進入編輯模式")
                if edit_on:
                    with st.form("edit_form"):
                        col1, col2 = st.columns(2)
                        with col1:
                            u_word = st.text_input("單字", value=target_w['word'])
                            u_cat = st.text_input("類別", value=target_w['category'])
                            u_mas = st.number_input("等級", 0, 5, value=int(target_w['mastery']))
                        with col2:
                            u_mean = st.text_input("中文", value=target_w['meaning_zh'])
                            u_syn = st.text_input("同義詞", value=target_w.get('synonyms', ''))
                            u_form = st.text_input("三態變化", value=target_w.get('other_forms', ''))
                        
                        u_def = st.text_area("英文定義", value=target_w.get('meaning_en', ''))
                        u_ex = st.text_area("例句", value=target_w.get('example', ''))
                        
                        if st.form_submit_button("💾 更新資料"):
                            up_payload = {
                                "word": u_word, "meaning_zh": u_mean, "category": u_cat,
                                "mastery": u_mas, "meaning_en": u_def, "example": u_ex,
                                "synonyms": u_syn, "other_forms": u_form,
                                "next_review": get_next_review_date(u_mas)
                            }
                            httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{target_w['id']}", json=up_payload, headers=HEADERS)
                            st.success("已更新")
                            st.rerun()
                else:
                    st.subheader(f"🔤 {target_w['word']}")
                    st.write(f"**中文：** {target_w['meaning_zh']}")
                    st.write(f"**定義：** {target_w.get('meaning_en', '未填')}")
                    st.write(f"**例句：** {target_w.get('example', '未填')}")

# --- B. 訓練模式頁面 ---
elif choice == "🎯 訓練模式":
    st.title("🎯 單字挑戰")
    raw_data = load_data()
    if raw_data:
        if st.button("🎲 隨機選題"):
            q = random.choice(raw_data)
            st.session_state.quiz_state = {'word': q['word'], 'meaning': q['meaning_zh'], 'attempts': 0}
        
        curr_q = st.session_state.quiz_state
        if curr_q['word']:
            st.info(f"💡 請輸入單字的拼寫：**{curr_q['meaning']}**")
            ans = st.text_input("你的答案：", key="quiz_ans")
            if st.button("提交答案"):
                if ans.strip().lower() == curr_q['word'].lower():
                    st.balloons()
                    st.success("正確！")
                    st.session_state.quiz_state['word'] = None
                else:
                    st.error("再試一次！")
    else:
        st.warning("目前沒有單字可供訓練。")

# --- C. 遺忘排程頁面 ---
elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程")
    st.write("複習清單開發中...")