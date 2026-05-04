import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 基本設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 (防呆與特效觸發) ---
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0, 'msg': None, 'msg_type': None}
if 'show_balloons' not in st.session_state: 
    st.session_state.show_balloons = False
if 'duplicate_word' not in st.session_state: 
    st.session_state.duplicate_word = None
if 'force_quiz_word' not in st.session_state: 
    st.session_state.force_quiz_word = None

# 氣球特效觸發
if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. Supabase 連線與參數 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_LEVEL = 5

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
    httpx.patch(api_url, json=payload, headers=HEADERS)

# --- 5. 側邊欄導航 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix 導航")
    choice = st.radio("前往功能：", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()
    if st.button("♻️ 重新整理"): st.rerun()

# --- 6. 頁面分流 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()
    
    # A. 新增單字與突擊測驗邏輯
    with st.expander("➕ 新增單字", expanded=not st.session_state.duplicate_word):
        with st.form("add_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                f_word = st.text_input("英文單字*")
                f_pos = st.multiselect("詞性", ["n.", "v.", "adj.", "adv.", "phr.", "Term."])
                f_cat = st.text_input("類別 (例如：托福)", value="未分類")
            with col2:
                f_mean = st.text_input("中文翻譯*")
                f_forms = st.text_input("三態/時態變化")
                f_coll = st.text_input("慣用搭配")
            f_en_def = st.text_area("英文定義")
            f_ex = st.text_area("例句")
            
            if st.form_submit_button("🚀 錄入矩陣"):
                if f_word.strip() and f_mean.strip():
                    # 檢查重複
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.duplicate_word = f_word.strip()
                        st.rerun()
                    else:
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean, "pos": ", ".join(f_pos),
                            "category": f_cat, "other_forms": f_forms, "meaning_en": f_en_def, 
                            "example": f_ex, "collocations": f_coll, "mastery": 1, 
                            "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        st.success("✅ 存入成功！")
                        st.rerun()

    # 重複單字觸發突擊測驗
    if st.session_state.duplicate_word:
        dw = st.session_state.duplicate_word
        st.warning(f"⚠️ 單字「{dw}」已在矩陣中！")
        if st.button(f"⚔️ 發動突擊測驗挑戰「{dw}」"):
            st.session_state.force_quiz_word = dw
            st.session_state.duplicate_word = None
            st.rerun()

    if st.session_state.force_quiz_word:
        target_quiz = next((w for w in raw_data if w['word'].lower() == st.session_state.force_quiz_word.lower()), None)
        if target_quiz:
            st.info(f"🔥 突擊挑戰！請輸入「{target_quiz['meaning_zh']}」的英文：")
            ans = st.text_input("拼寫單字：", key="sudden_quiz")
            if st.button("確認提交"):
                if ans.strip().lower() == target_quiz['word'].lower():
                    st.session_state.show_balloons = True
                    st.success("太強了！測驗通過！")
                    st.session_state.force_quiz_word = None
                    st.rerun()
                else: st.error("拼寫錯誤，再試一次！")

    # B. 表格顯示區
    if raw_data:
        st.divider()
        df = pd.DataFrame(raw_data)
        df_display = df.rename(columns={'word':'單字','meaning_zh':'中文','pos':'詞性','category':'類別','mastery':'掌握度','other_forms':'三態/變化'})
        df_display.index = range(1, len(df_display) + 1)
        
        t0, t1, t2 = st.tabs(["🌱 L0-L1 (重練)", "🏃 L2-L3 (穩定)", "👑 L4-L5 (精通)"])
        with t0: st.dataframe(df_display[df_display['掌握度'] <= 1], use_container_width=True)
        with t1: st.dataframe(df_display[(df_display['掌握度'] > 1) & (df_display['掌握度'] <= 3)], use_container_width=True)
        with t2: st.dataframe(df_display[df_display['掌握度'] > 3], use_container_width=True)

elif choice == "🎯 訓練模式":
    st.title("🎯 深度複習訓練")
    raw_data = load_data()
    today = str(date.today())
    due_list = [w for w in raw_data if w.get('next_review', today) <= today]

    if due_list:
        if not st.session_state.quiz_state['word']:
            q = random.choice(due_list)
            st.session_state.quiz_state.update({'word': q['word'], 'attempts': 0})
            # 隨機題型邏輯
            types = ["中文"]
            if q.get('example') and q['word'].lower() in q['example'].lower(): types.append("例句填空")
            if q.get('meaning_en'): types.append("英文定義")
            st.session_state.quiz_state['q_type'] = random.choice(types)

        target = next((w for w in due_list if w['word'] == st.session_state.quiz_state['word']), None)
        if target:
            st.subheader(f"當前等級：L{target['mastery']}")
            q_type = st.session_state.quiz_state['q_type']
            
            if q_type == "例句填空":
                st.info(f"📝 填空題目：\n{re.sub(re.escape(target['word']), '_______', target['example'], flags=re.I)}")
            elif q_type == "英文定義":
                st.info(f"📖 英文定義：\n{target['meaning_en']}")
            else:
                st.info(f"💡 中文提示：**{target['meaning_zh']}**")

            with st.form("main_quiz_form"):
                ans = st.text_input("請輸入答案：")
                if st.form_submit_button("提交"):
                    if ans.strip().lower() == target['word'].lower():
                        st.session_state.show_balloons = True
                        new_mas = min(MAX_LEVEL, target['mastery'] + 1)
                        update_supabase(target['id'], {"mastery": new_mas, "next_review": get_next_review_date(new_mas)})
                        st.session_state.quiz_state['word'] = None # 換題
                        st.rerun()
                    else:
                        st.session_state.quiz_state['attempts'] += 1
                        if st.session_state.quiz_state['attempts'] >= 3:
                            update_supabase(target['id'], {"mastery": 0, "next_review": today})
                            st.error(f"💀 失敗！正確答案是：{target['word']}，等級歸零。")
                            st.session_state.quiz_state['word'] = None
                        else:
                            st.warning(f"❌ 不對喔！提示：字首是 {target['word'][0]}")
    else:
        st.success("🎉 今日任務已全數完成！大腦已進入深度記憶模式。")

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程追蹤")
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['next_review'] = pd.to_datetime(df['next_review']).dt.date
        today = date.today()
        
        due_today = df[df['next_review'] <= today].rename(columns={'word':'單字','meaning_zh':'中文','mastery':'掌握度'})
        due_today.index = range(1, len(due_today)+1)
        
        due_future = df[df['next_review'] > today].sort_values('next_review').rename(columns={'word':'單字','next_review':'下次複習日','mastery':'掌握度'})
        due_future.index = range(1, len(due_future)+1)

        c1, c2 = st.columns(2)
        with c1:
            st.error(f"🔥 今日待辦 ({len(due_today)} 字)")
            st.dataframe(due_today[['單字', '中文', '掌握度']], use_container_width=True)
        with c2:
            st.info(f"📅 未來排程 ({len(due_future)} 字)")
            st.dataframe(due_future[['下次複習日', '單字', '掌握度']], use_container_width=True)