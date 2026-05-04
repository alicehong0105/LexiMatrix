import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta, datetime
import random
import re

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 ---
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0}
if 'show_balloons' not in st.session_state: 
    st.session_state.show_balloons = False
if 'duplicate_word' not in st.session_state: 
    st.session_state.duplicate_word = None
if 'force_quiz_word' not in st.session_state: 
    st.session_state.force_quiz_word = None

# 氣球特效
if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. Supabase 配置 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_LEVEL = 5

# --- 4. 工具函式 ---
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
    st.title("🛡️ LexiMatrix")
    choice = st.radio("功能導航", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()
    if st.button("♻️ 強制刷新資料"): st.rerun()

# --- 6. 主要頁面內容 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()
    
    # A. 新增單字表單
    with st.expander("➕ 新增單字", expanded=not st.session_state.duplicate_word):
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                f_word = st.text_input("英文單字*")
                f_pos = st.multiselect("詞性", ["n.", "v.", "adj.", "adv.", "phr.", "prep.", "conj."])
                f_cat = st.text_input("類別", value="未分類")
                f_forms = st.text_input("三態/時態變化")
            with c2:
                f_mean = st.text_input("中文翻譯*")
                f_syn = st.text_input("同義詞")
                f_coll = st.text_input("慣用搭配") # 現在這裡可以安全運作了
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
                            "category": f_cat, "other_forms": f_forms, "synonyms": f_syn,
                            "collocations": f_coll, "meaning_en": f_en_def, "example": f_ex,
                            "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        resp = httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        if resp.status_code < 300:
                            st.success(f"✅ {f_word} 已存入！")
                            st.rerun()
                        else:
                            st.error(f"❌ 儲存失敗：{resp.json().get('message')}")

    # B. 重複單字突擊測驗
    if st.session_state.duplicate_word:
        dw = st.session_state.duplicate_word
        st.warning(f"⚠️ 單字「{dw}」已存在於矩陣中！")
        if st.button(f"⚔️ 發動突擊測驗挑戰「{dw}」"):
            st.session_state.force_quiz_word = dw
            st.session_state.duplicate_word = None
            st.rerun()

    if st.session_state.force_quiz_word:
        target_quiz = next((w for w in raw_data if w['word'].lower() == st.session_state.force_quiz_word.lower()), None)
        if target_quiz:
            st.info(f"🔥 突擊挑戰！請拼寫出「{target_quiz['meaning_zh']}」的英文：")
            ans = st.text_input("拼寫單字：", key="sudden_quiz")
            if st.button("確認提交"):
                if ans.strip().lower() == target_quiz['word'].lower():
                    st.session_state.show_balloons = True
                    st.success("🎊 記憶力正確！測驗通過！")
                    st.session_state.force_quiz_word = None
                    st.rerun()
                else: st.error("❌ 拼寫有誤，再試一次！")

    # C. 表格顯示 (分區 L0-1, L2-3, L4-5)
    if raw_data:
        st.divider()
        df = pd.DataFrame(raw_data)
        cols_map = {'word':'單字','meaning_zh':'中文','category':'類別','mastery':'等級','pos':'詞性'}
        # 只顯示存在的欄位
        valid_cols = [c for c in cols_map.keys() if c in df.columns]
        df_display = df[valid_cols].rename(columns=cols_map)
        df_display.index = range(1, len(df_display) + 1)
        
        t1, t2, t3 = st.tabs(["🌱 L0-L1 新單字", "🏃 L2-L3 熟悉中", "👑 L4-L5 已精通"])
        with t1: st.dataframe(df_display[df_display['等級'] <= 1], use_container_width=True)
        with t2: st.dataframe(df_display[(df_display['等級'] >= 2) & (df_display['等級'] <= 3)], use_container_width=True)
        with t3: st.dataframe(df_display[df_display['等級'] >= 4], use_container_width=True)

elif choice == "🎯 訓練模式":
    st.title("🎯 深度複習訓練")
    raw_data = load_data()
    today_str = str(date.today())
    # 日期安全過濾
    due_list = [w for w in raw_data if not w.get('next_review') or str(w.get('next_review'))[:10] <= today_str]

    if due_list:
        if not st.session_state.quiz_state['word']:
            q = random.choice(due_list)
            st.session_state.quiz_state.update({'word': q['word'], 'attempts': 0})
            # 隨機題型
            opts = ["中文提示"]
            if q.get('example') and q['word'].lower() in q.get('example','').lower(): opts.append("例句填空")
            if q.get('meaning_en'): opts.append("英文定義題")
            st.session_state.quiz_state['q_type'] = random.choice(opts)

        target = next((w for w in due_list if w['word'] == st.session_state.quiz_state['word']), None)
        if target:
            st.subheader(f"Level {target['mastery']} | 題型：{st.session_state.quiz_state['q_type']}")
            if st.session_state.quiz_state['q_type'] == "例句填空":
                st.info(f"📝 {re.sub(re.escape(target['word']), '_______', target['example'], flags=re.I)}")
            elif st.session_state.quiz_state['q_type'] == "英文定義題":
                st.info(f"📖 {target['meaning_en']}")
            else:
                st.info(f"💡 中文：{target['meaning_zh']}")

            with st.form("quiz_form"):
                ans = st.text_input("輸入答案：")
                if st.form_submit_button("提交"):
                    if ans.strip().lower() == target['word'].lower():
                        st.session_state.show_balloons = True
                        new_mas = min(MAX_LEVEL, target['mastery'] + 1)
                        update_supabase(target['id'], {"mastery": new_mas, "next_review": get_next_review_date(new_mas)})
                        st.session_state.quiz_state['word'] = None
                        st.rerun()
                    else:
                        st.session_state.quiz_state['attempts'] += 1
                        att = st.session_state.quiz_state['attempts']
                        if att >= 3:
                            update_supabase(target['id'], {"mastery": 0, "next_review": today_str})
                            st.error(f"💀 失敗！答案是 {target['word']}，等級歸零。")
                            st.session_state.quiz_state['word'] = None
                        else: st.warning(f"❌ 提示：{target['word'][0]}... (剩 {3-att} 次機會)")
                        st.rerun()
    else:
        st.success("🎉 今日複習任務已全數完成！")

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘曲線排程追蹤")
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['nr_date'] = pd.to_datetime(df['next_review']).dt.date
        today = date.today()
        
        due_t = df[df['nr_date'] <= today].copy()
        due_f = df[df['nr_date'] > today].sort_values('nr_date').copy()
        
        for d in [due_t, due_f]:
            d.rename(columns={'word':'單字','meaning_zh':'中文','mastery':'等級','nr_date':'排程日期'}, inplace=True)
            d.index = range(1, len(d) + 1)

        c1, c2 = st.columns(2)
        with c1:
            st.error(f"🔥 今日待辦 ({len(due_t)})")
            st.dataframe(due_t[['單字', '中文', '等級']], use_container_width=True)
        with c2:
            st.info(f"📅 未來排程 ({len(due_f)})")
            st.dataframe(due_f[['排程日期', '單字', '等級']], use_container_width=True)