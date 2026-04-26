import streamlit as st
import json
import pandas as pd
from datetime import date, timedelta
import random
import re

# 頁面設定
st.set_page_config(layout="wide", page_title="LexiMatrix Pro")

# 樣式調整
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# 全域狀態初始化
if 'show_balloons' not in st.session_state: st.session_state.show_balloons = False
if 'duplicate_word' not in st.session_state: st.session_state.duplicate_word = None
if 'force_quiz_word' not in st.session_state: st.session_state.force_quiz_word = None

# 訓練模式的狀態管理
if 'quiz_state' not in st.session_state:
    st.session_state.quiz_state = {'word': None, 'q_type': None, 'attempts': 0, 'msg': None, 'msg_type': None}

# 突擊測驗的狀態管理
if 'sudden_quiz_state' not in st.session_state:
    st.session_state.sudden_quiz_state = {'attempts': 0, 'msg': None, 'msg_type': None}

# 解決氣球特效
if st.session_state.show_balloons:
    st.balloons()
    st.session_state.show_balloons = False

DATA_FILE = 'my_vocabulary.json'
# 新增「專業術語」選項
POS_OPTIONS = ["n. (名詞)", "v. (動詞)", "adj. (形容詞)", "adv. (副詞)", "phr. (慣用語)", "Term. (專業術語)"]
# 遺忘曲線天數邏輯 (Level 0 為重練)
INTERVALS = {0: 0, 1: 1, 2: 3, 3: 7, 4: 14, 5: 30} 
MAX_LEVEL = 5

def get_next_review_date(mastery_level):
    days_to_add = INTERVALS.get(mastery_level, 0)
    return str(date.today() + timedelta(days=days_to_add))

def load_words():
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [w for w in data if w.get("單字") and w.get("單字") != "未知"]
    except:
        return []

def save_words(words):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(words, f, ensure_ascii=False, indent=4)

def normalize_word_entry(w):
    return {
        "單字": w.get("單字", ""),
        "詞性": w.get("詞性", ["n. (名詞)"]),
        "中文": w.get("中文", ""),
        "類別": w.get("類別", "未分類"),
        "三態/變化": w.get("三態/變化", ""), # 新增欄位
        "英文解釋": w.get("英文解釋", ""),
        "例句": w.get("例句", ""),
        "同義詞": w.get("同義詞", ""),
        "搭配": w.get("搭配", ""),
        "mastery": w.get("mastery", 1), # 初始改為 1
        "last_reviewed": w.get("last_reviewed", str(date.today())),
        "next_review": w.get("next_review", str(date.today()))
    }

st.title("🛡️ LexiMatrix: Pro Learning System")

tabs = st.tabs(["➕ 新增單字", "📋 管理矩陣", "🎯 訓練模式", "📅 遺忘排程"])

# 1. 新增單字 
with tabs[0]:
    with st.form("add_word_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            word = st.text_input("英文單字* (必填)")
            pos = st.multiselect("詞性 (可複選)", POS_OPTIONS)
            category = st.text_input("類別 (例如：托福, 醫學)", "未分類")
            three_forms = st.text_input("三態/時態變化 (如: go-went-gone)")
        with col2:
            meaning = st.text_input("中文翻譯")
            synonyms = st.text_input("同義詞")
            collocations = st.text_input("慣用搭配")
        
        en_def = st.text_area("英文定義")
        example = st.text_area("例句")
        
        submitted = st.form_submit_button("儲存至矩陣")
        
        if submitted:
            if word.strip():
                word_clean = word.strip()
                words = load_words()
                
                if any(w['單字'].lower() == word_clean.lower() for w in words):
                    st.session_state.duplicate_word = word_clean
                    st.session_state.force_quiz_word = None
                    st.session_state.sudden_quiz_state = {'attempts': 0, 'msg': None, 'msg_type': None}
                else:
                    words.append({
                        "單字": word_clean, "詞性": pos, "中文": meaning, 
                        "類別": category, "三態/變化": three_forms,
                        "英文解釋": en_def, "例句": example, 
                        "同義詞": synonyms, "搭配": collocations, 
                        "mastery": 1,
                        "last_reviewed": str(date.today()),
                        "next_review": get_next_review_date(1)
                    })
                    save_words(words)
                    st.session_state.duplicate_word = None
                    st.session_state.force_quiz_word = None
                    st.success(f"✅ 已成功錄入：{word_clean} (初始等級: L1)")
            else:
                st.error("❌ 請至少輸入英文單字！")

    if st.session_state.duplicate_word:
        dw = st.session_state.duplicate_word
        st.warning(f"⚠️ 單字「**{dw}**」已存在！")
        if st.button(f"⚔️ 直接對「{dw}」發動突擊測驗！"):
            st.session_state.force_quiz_word = dw
            st.session_state.duplicate_word = None
            st.rerun()

    # --- 突擊測驗 ---
    if st.session_state.force_quiz_word:
        dw = st.session_state.force_quiz_word
        words = load_words()
        quiz = next((w for w in words if w['單字'].lower() == dw.lower()), None)
        
        if quiz:
            st.markdown("---")
            st.markdown(f"### 🔥 突擊測驗：{quiz['單字'][0]}... (共 {len(quiz['單字'])} 字母)")
            
            msg = st.session_state.sudden_quiz_state.get('msg')
            msg_type = st.session_state.sudden_quiz_state.get('msg_type')
            if msg:
                if msg_type == 'error': st.error(msg)
                elif msg_type == 'warning': st.warning(msg)
            else:
                st.info(f"💡 **中文提示**：{quiz['中文']}")
            
            with st.form("instant_quiz_form", clear_on_submit=True):
                ans = st.text_input("輸入完整單字拼寫：")
                if st.form_submit_button("送出"):
                    if ans.strip().lower() == quiz['單字'].lower():
                        st.session_state.show_balloons = True
                        st.session_state.force_quiz_word = None
                        st.session_state.sudden_quiz_state = {'attempts': 0, 'msg': None, 'msg_type': None}
                        
                        new_mastery = min(MAX_LEVEL, quiz['mastery'] + 1)
                        for w in words:
                            if w['單字'].lower() == quiz['單字'].lower():
                                w['mastery'] = new_mastery
                                w['last_reviewed'] = str(date.today())
                                w['next_review'] = get_next_review_date(new_mastery)
                        save_words(words)
                        st.success(f"🎉 答對了！等級提升至 L{new_mastery}")
                        st.rerun()
                    else:
                        st.session_state.sudden_quiz_state['attempts'] += 1
                        attempts = st.session_state.sudden_quiz_state['attempts']
                        
                        if attempts == 1:
                            st.session_state.sudden_quiz_state['msg_type'] = 'warning'
                            st.session_state.sudden_quiz_state['msg'] = f"❌ 錯誤！剩餘 2 次機會。\n\n💡 **提示 1**：開頭為 `{quiz['單字'][0]}`，長度為 {len(quiz['單字'])}。"
                        elif attempts == 2:
                            st.session_state.sudden_quiz_state['msg_type'] = 'warning'
                            hints = []
                            if quiz.get('同義詞'): hints.append(f"同義詞：{quiz['同義詞']}")
                            if quiz.get('三態/變化'): hints.append(f"相關變化：{quiz['三態/變化']}")
                            if quiz.get('英文解釋'): hints.append(f"定義：{quiz['英文解釋']}")
                            hint_str = " / ".join(hints) if hints else f"再洩漏一點：{quiz['單字'][:3]}..."
                            st.session_state.sudden_quiz_state['msg'] = f"❌ 還是錯！最後 1 次機會。\n\n💡 **提示 2**：{hint_str}"
                        else:
                            for w in words:
                                if w['單字'].lower() == quiz['單字'].lower():
                                    w['mastery'] = 0
                                    w['last_reviewed'] = str(date.today())
                                    w['next_review'] = str(date.today())
                            save_words(words)
                            st.session_state.sudden_quiz_state['msg_type'] = 'error'
                            st.error(f"💀 三振出局！正確答案是「{quiz['單字']}」。該單字已降級為 L0 重新訓練。")
                            st.session_state.force_quiz_word = None
                            st.session_state.sudden_quiz_state = {'attempts': 0, 'msg': None, 'msg_type': None}
                        st.rerun()

# 2. 管理矩陣 (修正預覽顯示與表格編號)
with tabs[1]:
    raw_words = load_words()
    words = [normalize_word_entry(w) for w in raw_words]
    
    if words:
        search_word = st.selectbox("選擇要管理或預覽的單字：", [w['單字'] for w in words])
        target_idx = next(i for i, w in enumerate(raw_words) if w.get('單字') == search_word)
        target_w = normalize_word_entry(raw_words[target_idx])
        
        with st.container(border=True):
            edit_mode = st.toggle("✏️ 修改資料內容")
            if edit_mode:
                with st.form("edit_existing_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_word = st.text_input("單字", target_w['單字'])
                        new_pos = st.multiselect("詞性", POS_OPTIONS, default=[p for p in target_w['詞性'] if p in POS_OPTIONS])
                        new_cat = st.text_input("類別", target_w['類別'])
                        new_forms = st.text_input("三態/變化", target_w['三態/變化'])
                        new_mas = st.number_input("手動調整等級 (0~5)", 0, 5, target_w['mastery'])
                    with col2:
                        new_mean = st.text_input("中文", target_w['中文'])
                        new_syn = st.text_input("同義詞", target_w['同義詞'])
                        new_coll = st.text_input("搭配", target_w['搭配'])
                    
                    new_def = st.text_area("定義", target_w['英文解釋'])
                    new_ex = st.text_area("例句", target_w['例句'])
                    
                    if st.form_submit_button("💾 覆蓋儲存"):
                        raw_words[target_idx] = {
                            "單字": new_word, "詞性": new_pos, "中文": new_mean,
                            "類別": new_cat, "三態/變化": new_forms, "英文解釋": new_def,
                            "例句": new_ex, "同義詞": new_syn, "搭配": new_coll, 
                            "mastery": new_mas, "last_reviewed": target_w['last_reviewed'],
                            "next_review": get_next_review_date(new_mas)
                        }
                        save_words(raw_words)
                        st.success("✅ 數據已更新！")
                        st.rerun()
            else:
                # 完整版的單字卡預覽
                st.markdown(f"### 🔤 {target_w['單字']} ({', '.join(target_w['詞性'])})")
                st.markdown(f"**類別：** {target_w['類別']} | **中文：** {target_w['中文']}")
                st.markdown(f"**定義：**\n{target_w['英文解釋'] or '無'}")
                st.markdown(f"**例句：**\n{target_w['例句'] or '無'}")
                st.markdown(f"**同義詞：** {target_w['同義詞'] or '無'}")
                st.markdown(f"**搭配：** {target_w['搭配'] or '無'}")
                st.markdown(f"**三態/變化：** {target_w['三態/變化'] or '無'} | **目前等級：** L{target_w['mastery']}")

    st.divider()
    st.subheader("📋 矩陣資料庫總表")
    view_mode = st.radio("👀 視角切換：", ["✨ 精簡模式 (核心資訊)", "🔍 完整模式 (包含例句/定義)"], horizontal=True)
    
    if words:
        df = pd.DataFrame(words)
        df.index = df.index + 1 # 讓 Pandas 的表格編號從 1 開始！
        
        display_cols = ["單字", "中文", "詞性", "類別", "mastery", "三態/變化"] if "精簡" in view_mode else df.columns.tolist()

        t0, t1, t2 = st.tabs(["🌱 新錄入/重練 (L0-L1)", "🏃 穩定熟悉 (L2-L3)", "👑 完全精通 (L4-L5)"])
        with t0: st.dataframe(df[df['mastery'].isin([0, 1])][display_cols], use_container_width=True)
        with t1: st.dataframe(df[df['mastery'].isin([2, 3])][display_cols], use_container_width=True)
        with t2: st.dataframe(df[df['mastery'].isin([4, 5])][display_cols], use_container_width=True)

# 3. 訓練模式 
with tabs[2]:
    raw_words = load_words()
    words = [normalize_word_entry(w) for w in raw_words]
    today_str = str(date.today())
    target_list = [w for w in words if w['next_review'] <= today_str]

    if target_list:
        if not st.session_state.quiz_state['word'] or st.session_state.quiz_state['word'] not in [w['單字'] for w in target_list]:
            quiz = random.choice(target_list)
            st.session_state.quiz_state['word'] = quiz['單字']
            st.session_state.quiz_state['attempts'] = 0
            
            avail_types = ["中文"]
            if quiz.get('例句') and quiz['單字'].lower() in quiz['例句'].lower(): avail_types.append("例句填空")
            if quiz.get('英文解釋'): avail_types.append("英文定義")
            if quiz.get('三態/變化'): avail_types.append("三態變化")
            st.session_state.quiz_state['q_type'] = random.choice(avail_types)

        quiz_word = st.session_state.quiz_state['word']
        quiz = next((w for w in target_list if w['單字'] == quiz_word), None)
        q_type = st.session_state.quiz_state['q_type']

        if quiz:
            st.markdown(f"### 🎯 深度練習 (Level {quiz['mastery']})")
            msg = st.session_state.quiz_state.get('msg')
            if msg:
                if st.session_state.quiz_state['msg_type'] == 'error': st.error(msg)
                elif st.session_state.quiz_state['msg_type'] == 'warning': st.warning(msg)
                elif st.session_state.quiz_state['msg_type'] == 'success': st.success(msg); st.session_state.quiz_state['msg'] = None
            
            st.info(f"💡 考題類型：**{q_type}**")
            if q_type == "例句填空":
                pattern = re.compile(re.escape(quiz['單字']), re.IGNORECASE)
                st.markdown(f"#### {pattern.sub('________', quiz['例句'])}")
            elif q_type == "三態變化":
                st.markdown(f"#### 請填寫該字之原型：(提示: {quiz['三態/變化']})")
            elif q_type == "英文定義":
                st.markdown(f"#### {quiz['英文解釋']}")
            else:
                st.markdown(f"#### 中文意思：{quiz['中文']}")

            with st.form("quiz_training_form", clear_on_submit=True):
                answer = st.text_input("拼寫單字：")
                if st.form_submit_button("送出答案"):
                    if answer.strip().lower() == quiz['單字'].lower():
                        st.session_state.show_balloons = True
                        new_mas = min(MAX_LEVEL, quiz['mastery'] + 1)
                        for w in raw_words:
                            if w['單字'] == quiz['單字']:
                                w['mastery'] = new_mas
                                w['last_reviewed'] = today_str
                                w['next_review'] = get_next_review_date(new_mas)
                        save_words(raw_words)
                        st.session_state.quiz_state.update({'msg_type': 'success', 'msg': f"🎊 正確！晉升至 L{new_mas}", 'word': None, 'attempts': 0})
                        st.rerun()
                    else:
                        st.session_state.quiz_state['attempts'] += 1
                        att = st.session_state.quiz_state['attempts']
                        if att == 1:
                            st.session_state.quiz_state.update({'msg_type': 'warning', 'msg': f"❌ 錯誤！剩餘 2 次。字首是 `{quiz['單字'][0]}`。"})
                        elif att == 2:
                            h = f"定義：{quiz['英文解釋']}" if quiz.get('英文解釋') else f"搭配：{quiz['搭配']}"
                            st.session_state.quiz_state.update({'msg_type': 'warning', 'msg': f"❌ 警告！最後 1 次。提示：{h}"})
                        else:
                            for w in raw_words:
                                if w['單字'] == quiz['單字']:
                                    w['mastery'] = 0
                                    w['last_reviewed'] = today_str
                                    w['next_review'] = today_str
                            save_words(raw_words)
                            st.session_state.quiz_state.update({'msg_type': 'error', 'msg': f"💀 失敗！答案是「{quiz['單字']}」，已降為 L0。", 'word': None, 'attempts': 0})
                        st.rerun()
    else:
        st.success("🎉 今日複習已全數完成！大腦已滿載，明天見！")

# 4. 遺忘曲線
with tabs[3]:
    st.subheader("📅 複習排程追蹤")
    raw_words = load_words()
    words = [normalize_word_entry(w) for w in raw_words]
    if words:
        df = pd.DataFrame(words)
        df.index = df.index + 1 # 這裡也同步改為從 1 開始編號
        df['next_review'] = pd.to_datetime(df['next_review']).dt.date
        today = date.today()
        due_today = df[df['next_review'] <= today]
        due_future = df[df['next_review'] > today].sort_values('next_review')
        
        c1, c2 = st.columns(2)
        with c1:
            st.error(f"🔥 今日待辦 ({len(due_today)} 字)")
            if not due_today.empty: st.dataframe(due_today[['單字', '中文', 'mastery']], hide_index=False)
        with c2:
            st.info(f"📅 未來排程 ({len(due_future)} 字)")
            if not due_future.empty: st.dataframe(due_future[['next_review', '單字', 'mastery']], hide_index=False)