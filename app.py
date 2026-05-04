import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 頁面設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 狀態初始化 ---
for key in ['quiz_state', 'show_balloons', 'duplicate_word', 'force_quiz_word']:
    if key not in st.session_state:
        if key == 'quiz_state': st.session_state[key] = {'word': None, 'q_type': None, 'attempts': 0}
        else: st.session_state[key] = False

if st.session_state.get('show_balloons'):
    st.balloons()
    st.session_state.show_balloons = False

# --- 3. Supabase 配置 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]
HEADERS = {"apikey": KEY, "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# --- 4. 工具函式 ---
def get_next_review_date(level):
    intervals = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30}
    return str(date.today() + timedelta(days=intervals.get(level, 0)))

def load_data():
    try:
        resp = httpx.get(f"{URL}/rest/v1/vocabulary?select=*&order=id.desc", headers=HEADERS)
        return resp.json()
    except: return []

# --- 5. 主要功能導航 ---
choice = st.sidebar.radio("功能選單", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()
    df = pd.DataFrame(raw_data) if raw_data else pd.DataFrame()

    # --- A. 新增與編輯分頁 ---
    tab_add, tab_edit = st.tabs(["➕ 新增單字", "📝 編輯 / 刪除單字"])

    with tab_add:
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            f_word = c1.text_input("英文單字*")
            f_mean = c2.text_input("中文翻譯*")
            f_pos = st.multiselect("詞性", ["n.", "v.", "adj.", "adv.", "phr.", "Term."])
            f_forms = st.text_input("三態/變化 (other_forms)")
            f_en_def = st.text_area("英文定義 (meaning_en)")
            f_ex = st.text_area("例句 (example)")
            
            if st.form_submit_button("🚀 錄入矩陣"):
                if f_word.strip() and f_mean.strip():
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.duplicate_word = f_word.strip()
                        st.rerun()
                    else:
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), "pos": ", ".join(f_pos) if f_pos else None,
                            "other_forms": f_forms if f_forms else None, "meaning_en": f_en_def if f_en_def else None,
                            "example": f_ex if f_ex else None, "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        payload = {k: v for k, v in payload.items() if v is not None}
                        httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        st.rerun()

    with tab_edit:
        if not df.empty:
            target_word = st.selectbox("🎯 選擇要操作的單字", options=df['word'].tolist())
            row = df[df['word'] == target_word].iloc[0]
            with st.form("edit_form"):
                ec1, ec2 = st.columns(2)
                u_word = ec1.text_input("單字", value=row['word'])
                u_mean = ec2.text_input("中文翻譯", value=row['meaning_zh'])
                u_pos = st.text_input("詞性 (字串格式)", value=row.get('pos', ''))
                u_ex = st.text_area("例句", value=row.get('example', ''))
                
                btn_save, btn_del, _ = st.columns([1, 1, 4])
                if btn_save.form_submit_button("💾 儲存修改"):
                    upd = {"word": u_word, "meaning_zh": u_mean, "pos": u_pos, "example": u_ex}
                    httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", json=upd, headers=HEADERS)
                    st.rerun()
                if btn_del.form_submit_button("🗑️ 刪除單字"):
                    httpx.delete(f"{URL}/rest/v1/vocabulary?id=eq.{row['id']}", headers=HEADERS)
                    st.rerun()

    # --- B. 重複挑戰 ---
    if st.session_state.duplicate_word:
        st.warning(f"⚠️ 「{st.session_state.duplicate_word}」已存在！")
        if st.button("⚔️ 挑戰突擊測驗"):
            st.session_state.force_quiz_word = st.session_state.duplicate_word
            st.session_state.duplicate_word = False
            st.rerun()

    if st.session_state.force_quiz_word:
        target = next((w for w in raw_data if w['word'].lower() == st.session_state.force_quiz_word.lower()), None)
        if target:
            ans = st.text_input(f"請拼寫出「{target['meaning_zh']}」的英文：")
            if st.button("確認"):
                if ans.strip().lower() == target['word'].lower():
                    st.session_state.show_balloons = True
                    st.session_state.force_quiz_word = False
                    st.rerun()

    # --- C. 搜尋與分區顯示 ---
    if not df.empty:
        st.divider()
        search_q = st.text_input("🔍 搜尋關鍵字")
        if search_q:
            df = df[df.apply(lambda r: search_q.lower() in str(r.values).lower(), axis=1)]
        
        c_left, c_right = st.columns([3, 1])
        v_mode = c_left.radio("顯示模式", ["分區檢視", "完整名單"], horizontal=True)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        c_right.download_button("📥 下載 CSV", csv, "lexi_export.csv")

        show_cols = ['word', 'meaning_zh', 'pos', 'mastery']
        if v_mode == "分區檢視":
            t1, t2, t3 = st.tabs(["🌱 L0-1", "🏃 L2-3", "👑 L4-5"])
            t1.dataframe(df[df['mastery'] <= 1][show_cols], use_container_width=True)
            t2.dataframe(df[(df['mastery'] >= 2) & (df['mastery'] <= 3)][show_cols], use_container_width=True)
            t3.dataframe(df[df['mastery'] >= 4][show_cols], use_container_width=True)
        else:
            st.dataframe(df[show_cols], use_container_width=True)

elif choice == "🎯 訓練模式":
    st.title("🎯 訓練模式")
    raw_data = load_data()
    today = str(date.today())
    
    if not st.session_state.quiz_state['word']:
        due = [w for w in raw_data if not w.get('next_review') or str(w.get('next_review'))[:10] <= today]
        if due:
            q = random.choice(due)
            st.session_state.quiz_state.update({'word': q['word'], 'attempts': 0})
            opts = ["中文提示"]
            if q.get('example'): opts.append("例句填空")
            if q.get('meaning_en'): opts.append("英文定義")
            st.session_state.quiz_state['q_type'] = random.choice(opts)
        else:
            st.success("🎉 今日複習完成！")
            st.stop()

    target = next((w for w in raw_data if w['word'] == st.session_state.quiz_state['word']), None)
    if target:
        st.subheader(f"題型：{st.session_state.quiz_state['q_type']}")
        if st.session_state.quiz_state['q_type'] == "例句填空":
            st.info(f"📝 {re.sub(re.escape(target['word']), '_______', target['example'], flags=re.I)}")
        elif st.session_state.quiz_state['q_type'] == "英文定義":
            st.info(f"📖 {target['meaning_en']}")
        else:
            st.info(f"💡 中文：{target['meaning_zh']}")

        ans = st.text_input("拼寫：")
        if st.button("送出"):
            if ans.strip().lower() == target['word'].lower():
                st.session_state.show_balloons = True
                new_m = min(5, target.get('mastery', 1) + 1)
                httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{target['id']}", json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                st.session_state.quiz_state['word'] = None
                st.rerun()
            else: st.error("不對喔！")

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程")
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        st.dataframe(df[['word', 'meaning_zh', 'mastery', 'next_review']], use_container_width=True)