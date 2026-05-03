import streamlit as st
import httpx

# --- 1. 從 Secrets 讀取連線資訊 ---
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json"
}

# --- 2. 功能函式 ---

def add_word_to_supabase(word_data):
    """將完整的單字資料送往雲端"""
    api_url = f"{URL}/rest/v1/vocabulary"
    try:
        response = httpx.post(api_url, json=word_data, headers=headers)
        response.raise_for_status()
        return True
    except Exception as e:
        st.error(f"❌ 儲存失敗: {e}")
        return False

def load_data_from_supabase():
    """從雲端抓取資料"""
    api_url = f"{URL}/rest/v1/vocabulary?select=*&order=id.desc"
    try:
        response = httpx.get(api_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"❌ 讀取失敗: {e}")
        return []

# --- 3. 網頁介面 ---

st.set_page_config(page_title="LexiMatrix 專業版", page_icon="📝")
st.title("📝 我的全功能雲端單字庫")

# 【A 區塊：進階新增表單】
with st.expander("➕ 加入新單字 (詳細模式)", expanded=False):
    with st.form(key="advanced_add_form", clear_on_submit=True):
        col1, col2 = st.columns([2, 2])
        
        with col1:
            word = st.text_input("英文單字", placeholder="例如: persist")
            # 詞性複選功能
            pos_list = st.multiselect("詞性 (可複選)", ["n.", "v.", "adj.", "adv.", "prep.", "conj."])
            category = st.text_input("類別", placeholder="例如: 考試、托福")
            
        with col2:
            meaning = st.text_area("中文解釋", placeholder="輸入定義...")
            other_forms = st.text_input("三態/變化", placeholder="例如: persisted, persisting")
            mastery = st.slider("掌握等級 (0-5)", 0, 5, 1)

        submit = st.form_submit_button("🚀 儲存到雲端資料庫")

        if submit:
            if word and meaning:
                # 這裡要對齊你的 Supabase 欄位名稱
                # 如果你的欄位名稱是「中文」，這裡就要改寫成中文
                payload = {
                    "word": word,
                    "pos": ", ".join(pos_list), # 將清單轉為字串 "n., v."
                    "meaning_zh": meaning,      # 💡 請檢查資料庫是 meaning 還是 meaning_zh
                    "category": category,
                    "other_forms": other_forms,
                    "mastery": mastery,
                    "user_email": "alice@test.com"
                }
                
                if add_word_to_supabase(payload):
                    st.success(f"✅ '{word}' 已同步至雲端！")
                    st.rerun()
            else:
                st.warning("⚠️ 單字和解釋是必填項喔！")

# 【B 區塊：顯示清單】
data = load_data_from_supabase()

if data:
    st.write(f"📊 目前共有 {len(data)} 個單字")
    for item in data:
        with st.container():
            c1, c2, c3 = st.columns([1.5, 3, 1])
            with c1:
                st.info(f"**{item.get('word')}**")
                st.caption(f"({item.get('pos')})")
            with c2:
                # 這裡的 key 要對應你資料庫的欄位
                st.write(f"💡 {item.get('meaning_zh')}") 
                if item.get('other_forms'):
                    st.caption(f"變化: {item.get('other_forms')}")
            with c3:
                st.write(f"⭐ Lvl: {item.get('mastery')}")
                st.caption(f"#{item.get('category')}")
            st.divider()
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
        
       # 第 304 行開始
with st.container(border=True):
    # 這裡要縮進 4 個空格
    edit_mode = st.toggle("✏️ 修改資料內容")
    
    if edit_mode:
        # if 裡面的內容要再縮進 4 個空格（共 8 個）
        with st.form("edit_existing_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # with 裡面的內容再縮進（共 12 個）
                new_word = st.text_input("單字", value=target_w.get('單字', ''))
                
                # 處理舊的詞性字串轉清單
                old_pos_str = target_w.get('詞性', '')
                if isinstance(old_pos_str, list): # 如果原本就是清單
                    default_pos = old_pos_str
                else: # 如果是字串則切割
                    default_pos = [p.strip() for p in old_pos_str.split(',')] if old_pos_str else []
                
                new_pos_list = st.multiselect(
                    "詞性 (可複選)", 
                    ["n.", "v.", "adj.", "adv.", "prep.", "conj."],
                    default=[p for p in default_pos if p in ["n.", "v.", "adj.", "adv.", "prep.", "conj."]]
                )
                new_pos = ", ".join(new_pos_list) # 轉回字串供儲存

                # 2. 基本分類
                new_cat = st.text_input("類別", value=target_w.get('類別', ''))
                new_forms = st.text_input("三態/變化", value=target_w.get('三態/變化', ''))
                new_mas = st.number_input("手動調整等級 (0~5)", 0, 5, value=int(target_w.get('mastery', 0)))

            with col2:
                new_mean = st.text_input("中文", value=target_w.get('中文', ''))
                new_syn = st.text_input("同義詞", value=target_w.get('同義詞', ''))
                new_coll = st.text_input("搭配", value=target_w.get('搭配', ''))
            
            # 3. 長文字區
            new_def = st.text_area("定義", value=target_w.get('英文解釋', ''))
            new_ex = st.text_area("例句", value=target_w.get('例句', ''))
            
            if st.form_submit_button("💾 覆蓋儲存並同步雲端"):
                # 更新原本的資料字典
                raw_words[target_idx] = {
                    "單字": new_word, "詞性": new_pos, "中文": new_mean,
                    "類別": new_cat, "三態/變化": new_forms, "英文解釋": new_def,
                    "例句": new_ex, "同義詞": new_syn, "搭配": new_coll, 
                    "mastery": new_mas, "last_reviewed": target_w.get('last_reviewed', ''),
                    "next_review": get_next_review_date(new_mas)
                }
                
                # 這裡執行儲存 (包含本地儲存 save_words 和你原本的 Supabase 同步)
                save_words(raw_words)
                st.success(f"✅ '{new_word}' 數據已更新！")
                st.rerun()
    
    else:
        # --- 完整版的單字卡預覽 (非編輯模式) ---
        # 處理詞性顯示，如果是清單就 join，如果是字串就直接顯示
        display_pos = target_w['詞性']
        if isinstance(display_pos, list):
            display_pos = ", ".join(display_pos)
            
        st.markdown(f"### 🔤 {target_w['單字']} ({display_pos})")
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**📌 類別：** {target_w['類別']}")
            st.markdown(f"**💡 中文：** {target_w['中文']}")
            st.markdown(f"**🔄 三態：** {target_w.get('三態/變化', '無')}")
        with c2:
            st.markdown(f"**⭐ 等級：** L{target_w['mastery']}")
            st.markdown(f"**🔗 搭配：** {target_w.get('搭配', '無')}")
            st.markdown(f"**👯 同義：** {target_w.get('同義詞', '無')}")
            
        st.info(f"**📖 定義：**\n{target_w.get('英文解釋') or '未填寫'}")
        st.warning(f"**📝 例句：**\n{target_w.get('例句') or '未填寫'}")

# --- 下方的表格顯示區 ---
st.divider()
st.subheader("📋 矩陣資料庫總表")
view_mode = st.radio("👀 視角切換：", ["✨ 精簡模式 (核心資訊)", "🔍 完整模式 (包含例句/定義)"], horizontal=True)

if words:
    df = pd.DataFrame(words)
    df.index = df.index + 1
    
    # 這裡確保表格顯示的詞性欄位也是美觀的字串
    if "詞性" in df.columns:
        df["詞性"] = df["詞性"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

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