import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 (解決錯誤與氣球) ---
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0, 'msg': None, 'msg_type': None}
if 'show_balloons' not in st.session_state: st.session_state.show_balloons = False
if 'duplicate_word' not in st.session_state: st.session_state.duplicate_word = None
if 'force_quiz_word' not in st.session_state: st.session_state.force_quiz_word = None
if 'sudden_quiz_state' not in st.session_state:
    st.session_state.sudden_quiz_state = {'attempts': 0, 'msg': None, 'msg_type': None}

if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. 連線資訊與常數 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
POS_OPTIONS = ["n. (名詞)", "v. (動詞)", "adj. (形容詞)", "adv. (副詞)", "phr. (慣用語)", "Term. (專業術語)"]
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
MAX_LEVEL = 5

# --- 4. 功能函式 (全面對接雲端) ---
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
    response = httpx.patch(api_url, json=payload, headers=HEADERS)
    return response.status_code < 400

# --- 5. 側邊欄導航 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix")
    choice = st.radio("功能清單", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()
    st.caption(f"📅 Today: {date.today()}")

# --- 6. 頁面分流 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()

    # --- A. 新增單字 ---
    with st.expander("➕ 新增單字至雲端"):
        with st.form("add_word_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                word = st.text_input("英文單字*")
                pos = st.multiselect("詞性", POS_OPTIONS)
                category = st.text_input("類別", "未分類")
                three_forms = st.text_input("三態/時態變化")
            with col2:
                meaning = st.text_input("中文翻譯*")
                synonyms = st.text_input("同義詞")
                collocations = st.text_input("慣用搭配")
            en_def = st.text_area("英文定義")
            example = st.text_area("例句")
            
            if st.form_submit_button("儲存至矩陣"):
                if word.strip() and meaning.strip():
                    duplicate = next((w for w in raw_data if w['word'].lower() == word.strip().lower()), None)
                    if duplicate:
                        st.session_state.duplicate_word = word.strip()
                        st.rerun()
                    else:
                        payload = {
                            "word": word.strip(), "pos": ", ".join(pos), "meaning_zh": meaning,
                            "meaning_en": en_def, "example": example, "category": category,
                            "synonyms": synonyms, "other_forms": three_forms, "collocations": collocations,
                            "mastery": 1, "last_reviewed": str(date.today()),
                            "next_review": get_next_review_date(1)
                        }
                        httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        st.success("✅ 錄入成功！")
                        st.rerun()

    # --- B. 編輯與表格區 ---
    if raw_data:
        st.divider()
        search_word = st.selectbox("🔍 選擇單字進行預覽或修改：", [w['word'] for w in raw_data])
        target_w = next((w for w in raw_data if w['word'] == search_word), None)
        
        if target_w:
            with st.container(border=True):
                edit_mode = st.toggle("✏️ 修改資料內容")
                if edit_mode:
                    with st.form("edit_existing_form"):
                        c1, c2 = st.columns(2)
                        with c1:
                            u_word = st.text_input("單字", value=target_w['word'])
                            u_pos = st.multiselect("詞性", POS_OPTIONS, default=[p.strip() for p in target_w.get('pos','').split(',') if p.strip() in POS_OPTIONS])
                            u_cat = st.text_input("類別", value=target_w.get('category',''))
                            u_mas = st.number_input("手動調整等級", 0, 5, value=int(target_w.get('mastery', 0)))
                        with c2:
                            u_mean = st.text_input("中文", value=target_w.get('meaning_zh',''))
                            u_syn = st.text_input("同義詞", value=target_w.get('synonyms',''))
                            u_coll = st.text_input("搭配", value=target_w.get('collocations',''))
                            u_forms = st.text_input("三態變化", value=target_w.get('other_forms',''))
                        u_def = st.text_area("定義", value=target_w.get('meaning_en',''))
                        u_ex = st.text_area("例句", value=target_w.get('example',''))
                        
                        if st.form_submit_button("💾 覆蓋儲存並同步雲端"):
                            up_payload = {
                                "word": u_word, "pos": ", ".join(u_pos), "meaning_zh": u_mean,
                                "category": u_cat, "mastery": u_mas, "synonyms": u_syn,
                                "collocations": u_coll, "other_forms": u_forms,
                                "meaning_en": u_def, "example": u_ex,
                                "next_review": get_next_review_date(u_mas)
                            }
                            if update_supabase(target_w['id'], up_payload):
                                st.success("✅ 雲端數據已更新！")
                                st.rerun()
                else:
                    st.markdown(f"### 🔤 {target_w['word']} ({target_w.get('pos','')})")
                    st.info(f"**📖 定義：**\n{target_w.get('meaning_en') or '未填'}")
                    st.warning(f"**📝 例句：**\n{target_w.get('example') or '未填'}")

        # --- 表格顯示 ---
        st.divider()
        view_mode = st.radio("👀 視角：", ["✨ 精簡", "🔍 完整"], horizontal=True)
        df = pd.DataFrame(raw_data)
        cols = ["word", "meaning_zh", "pos", "category", "mastery", "other_forms"] if "精簡" in view_mode else df.columns.tolist()
        
        t0, t1, t2 = st.tabs(["🌱 重練 (L0-L1)", "🏃 穩定 (L2-L3)", "👑 精通 (L4-L5)"])
        with t0: st.dataframe(df[df['mastery'].isin([0, 1])][cols], use_container_width=True)
        with t1: st.dataframe(df[df['mastery'].isin([2, 3])][cols], use_container_width=True)
        with t2: st.dataframe(df[df['mastery'].isin([4, 5])][cols], use_container_width=True)

elif choice == "🎯 訓練模式":
    st.title("🎯 深度訓練模式")
    raw_data = load_data()
    today_str = str(date.today())
    # 篩選今天需要複習的單字
    target_list = [w for w in raw_data if w.get('next_review', today_str) <= today_str]

    if target_list:
        if not st.session_state.quiz_state['word']:
            quiz = random.choice(target_list)
            st.session_state.quiz_state.update({'word': quiz['word'], 'attempts': 0, 'msg': None})
            
            avail = ["中文"]
            if quiz.get('example') and quiz['word'].lower() in quiz['example'].lower(): avail.append("例句填空")
            if quiz.get('meaning_en'): avail.append("英文定義")
            if quiz.get('other_forms'): avail.append("三態變化")
            st.session_state.quiz_state['q_type'] = random.choice(avail)

        curr_word = st.session_state.quiz_state['word']
        quiz = next((w for w in target_list if w['word'] == curr_word), None)
        
        if quiz:
            st.markdown(f"### 🎯 挑戰等級: Level {quiz['mastery']}")
            if st.session_state.quiz_state['msg']:
                m = st.session_state.quiz_state['msg']
                mt = st.session_state.quiz_state['msg_type']
                if mt == 'error': st.error(m)
                elif mt == 'warning': st.warning(m)
                elif mt == 'success': st.success(m)

            q_type = st.session_state.quiz_state['q_type']
            st.info(f"💡 考題類型：**{q_type}**")
            
            if q_type == "例句填空":
                st.markdown(f"#### {re.sub(re.escape(quiz['word']), '________', quiz['example'], flags=re.I)}")
            elif q_type == "三態變化":
                st.markdown(f"#### 請拼寫原型：(提示: {quiz['other_forms']})")
            elif q_type == "英文定義":
                st.markdown(f"#### {quiz['meaning_en']}")
            else:
                st.markdown(f"#### 中文意思：{quiz['meaning_zh']}")

            with st.form("quiz_form", clear_on_submit=True):
                ans = st.text_input("輸入答案：")
                if st.form_submit_button("送出"):
                    if ans.strip().lower() == quiz['word'].lower():
                        st.session_state.show_balloons = True
                        new_mas = min(MAX_LEVEL, quiz['mastery'] + 1)
                        update_supabase(quiz['id'], {"mastery": new_mas, "last_reviewed": today_str, "next_review": get_next_review_date(new_mas)})
                        st.session_state.quiz_state.update({'word': None, 'msg': f"🎊 正確！升至 L{new_mas}", 'msg_type': 'success'})
                        st.rerun()
                    else:
                        st.session_state.quiz_state['attempts'] += 1
                        att = st.session_state.quiz_state['attempts']
                        if att >= 3:
                            update_supabase(quiz['id'], {"mastery": 0, "last_reviewed": today_str, "next_review": today_str})
                            st.session_state.quiz_state.update({'word': None, 'msg': f"💀 失敗！正確答案是「{quiz['word']}」", 'msg_type': 'error'})
                        else:
                            st.session_state.quiz_state.update({'msg': f"❌ 錯誤！剩餘 {3-att} 次機會。提示：首字母是 {quiz['word'][0]}", 'msg_type': 'warning'})
                        st.rerun()
    else:
        st.success("🎉 今日複習已全數完成！")

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程")
    st.write("複習清單開發中...")