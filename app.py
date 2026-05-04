import streamlit as st
import httpx
import pandas as pd
from datetime import date, timedelta
import random
import re

# --- 1. 頁面基本設定 ---
st.set_page_config(page_title="LexiMatrix Pro", page_icon="🛡️", layout="wide")

# --- 2. 初始化全域狀態 ---
for key in ['quiz_state', 'show_balloons', 'duplicate_word', 'force_quiz_word']:
    if key not in st.session_state:
        if key == 'quiz_state': 
            st.session_state[key] = {'word': None, 'q_type': None, 'attempts': 0}
        else: 
            st.session_state[key] = False

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

# --- 5. 側邊欄 ---
with st.sidebar:
    st.title("🛡️ LexiMatrix")
    choice = st.radio("功能選單", ["📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])
    st.divider()
    if st.button("♻️ 重新整理資料"): st.rerun()

# --- 6. 主要功能頁面 ---

if choice == "📋 管理矩陣":
    st.title("📋 矩陣資料庫管理")
    raw_data = load_data()
    
    # A. 新增單字區
    with st.expander("➕ 新增單字", expanded=not st.session_state.duplicate_word):
        with st.form("add_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                f_word = st.text_input("英文單字*")
                f_pos = st.multiselect("詞性", ["n.", "v.", "adj.", "adv.", "phr.", "Term."])
                f_cat = st.text_input("類別", value="未分類")
            with c2:
                f_mean = st.text_input("中文翻譯*")
                f_forms = st.text_input("三態/變化 (other_forms)")
                f_coll = st.text_input("慣用搭配 (collocations)")
            f_en_def = st.text_area("英文定義 (meaning_en)")
            f_ex = st.text_area("例句 (example)")
            
            if st.form_submit_button("🚀 錄入矩陣"):
                if f_word.strip() and f_mean.strip():
                    # 檢查重複
                    dup = next((w for w in raw_data if w['word'].lower() == f_word.strip().lower()), None)
                    if dup:
                        st.session_state.duplicate_word = f_word.strip()
                        st.rerun()
                    else:
                        # 核心防呆：將 List 轉為字串，並處理空值
                        pos_str = ", ".join(f_pos) if f_pos else None
                        payload = {
                            "word": f_word.strip(), "meaning_zh": f_mean.strip(), 
                            "pos": pos_str, "category": f_cat if f_cat else "未分類",
                            "other_forms": f_forms if f_forms else None,
                            "collocations": f_coll if f_coll else None,
                            "meaning_en": f_en_def if f_en_def else None,
                            "example": f_ex if f_ex else None,
                            "mastery": 1, "next_review": get_next_review_date(1)
                        }
                        # 暴力排除 None 欄位，避開 malformed array 錯誤
                        payload = {k: v for k, v in payload.items() if v is not None}
                        
                        resp = httpx.post(f"{URL}/rest/v1/vocabulary", json=payload, headers=HEADERS)
                        if resp.status_code < 300:
                            st.success(f"✅ {f_word} 成功錄入！")
                            st.session_state.show_balloons = True
                            st.rerun()
                        else:
                            st.error("❌ 儲存失敗！")
                            st.code(resp.text)

    # B. 重複偵測與突擊測驗
    if st.session_state.duplicate_word:
        dw = st.session_state.duplicate_word
        st.warning(f"⚠️ 單字「{dw}」已在矩陣中！")
        if st.button(f"⚔️ 發動突擊測驗挑戰「{dw}」"):
            st.session_state.force_quiz_word = dw
            st.session_state.duplicate_word = False
            st.rerun()

    if st.session_state.force_quiz_word:
        target_quiz = next((w for w in raw_data if w['word'].lower() == st.session_state.force_quiz_word.lower()), None)
        if target_quiz:
            st.info(f"🔥 突擊挑戰！請拼寫出「{target_quiz['meaning_zh']}」的英文：")
            ans = st.text_input("拼寫單字：", key="sudden_quiz")
            if st.button("確認提交"):
                if ans.strip().lower() == target_quiz['word'].lower():
                    st.session_state.show_balloons = True
                    st.success("🎊 記憶正確！測驗通過！")
                    st.session_state.force_quiz_word = False
                    st.rerun()
                else: st.error("❌ 拼寫有誤，再試一次！")

    # C. 表格工具與顯示
    if raw_data:
        st.divider()
        df = pd.DataFrame(raw_data)
        
        # 1. 搜尋
        search_q = st.text_input("🔍 搜尋關鍵字：", "")
        if search_q:
            mask = df.apply(lambda row: search_q.lower() in str(row.values).lower(), axis=1)
            df = df[mask]

        # 2. 工具列
        t_c1, t_c2 = st.columns([3, 1])
        with t_c1:
            view_mode = st.radio("顯示模式", ["分區顯示 (L0-5)", "完整矩陣"], horizontal=True)
        with t_c2:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載 CSV", data=csv, file_name=f"lexi_{date.today()}.csv")

        # 3. 欄位整理
        cols_map = {'word':'單字','meaning_zh':'中文','category':'類別','mastery':'等級','pos':'詞性','other_forms':'變化','example':'例句'}
        valid_cols = [c for c in cols_map.keys() if c in df.columns]
        df_show = df[valid_cols].rename(columns=cols_map)
        df_show.index = range(1, len(df_show) + 1)

        # 4. 呈現
        if view_mode == "分區顯示 (L0-5)":
            t1, t2, t3 = st.tabs(["🌱 L0-L1", "🏃 L2-L3", "👑 L4-L5"])
            with t1: st.dataframe(df_show[df_show['等級'] <= 1], use_container_width=True)
            with t2: st.dataframe(df_show[(df_show['等級'] >= 2) & (df_show['等級'] <= 3)], use_container_width=True)
            with t3: st.dataframe(df_show[df_show['等級'] >= 4], use_container_width=True)
        else:
            st.dataframe(df_show, use_container_width=True)

elif choice == "🎯 訓練模式":
    st.title("🎯 深度訓練模式")
    raw_data = load_data()
    today = str(date.today())
    due_list = [w for w in raw_data if not w.get('next_review') or str(w.get('next_review'))[:10] <= today]

    if due_list:
        if not st.session_state.quiz_state['word']:
            q = random.choice(due_list)
            st.session_state.quiz_state.update({'word': q['word'], 'attempts': 0})
            # 動態題型選擇
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

            ans = st.text_input("輸入英文：", key="quiz_input")
            if st.button("提交答案"):
                if ans.strip().lower() == target['word'].lower():
                    st.session_state.show_balloons = True
                    new_m = min(5, target.get('mastery', 1) + 1)
                    httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{target['id']}", 
                                json={"mastery": new_m, "next_review": get_next_review_date(new_m)}, headers=HEADERS)
                    st.session_state.quiz_state['word'] = None
                    st.rerun()
                else:
                    st.session_state.quiz_state['attempts'] += 1
                    if st.session_state.quiz_state['attempts'] >= 3:
                        httpx.patch(f"{URL}/rest/v1/vocabulary?id=eq.{target['id']}", 
                                    json={"mastery": 0, "next_review": today}, headers=HEADERS)
                        st.error(f"💀 失敗！正確答案是 {target['word']}")
                        st.session_state.quiz_state['word'] = None
                    else: st.warning(f"❌ 再試一次！提示：{target['word'][0]}...")
    else: st.success("🎉 今日複習任務已全數完成！")

elif choice == "📅 遺忘排程":
    st.title("📅 遺忘排程追蹤")
    raw_data = load_data()
    if raw_data:
        df = pd.DataFrame(raw_data)
        df['nr_date'] = pd.to_datetime(df['next_review']).dt.date
        today = date.today()
        c1, c2 = st.columns(2)
        with c1:
            st.error(f"🔥 今日待辦 ({len(df[df['nr_date'] <= today])})")
            st.dataframe(df[df['nr_date'] <= today][['word', 'meaning_zh', 'mastery']], use_container_width=True)
        with c2:
            st.info("📅 未來複習預告")
            st.dataframe(df[df['nr_date'] > today].sort_values('nr_date')[['nr_date', 'word']], use_container_width=True)