import json
import httpx
import streamlit as st

# 1. 取得連線資訊
URL = st.secrets["connections"]["supabase"]["url"]
KEY = st.secrets["connections"]["supabase"]["key"]

# 2. 設定讀取 JSON 
with open('my_vocabulary.json', 'r', encoding='utf-8') as f:
    old_data = json.load(f)

# 3. 準備發送資料的「郵差」(headers)
headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 4. 開始搬家
print(f"準備搬移 {len(old_data)} 筆資料...")

with httpx.Client() as client:
    for item in old_data:
        # 對應欄位
        new_row = {
            "word": item.get("單字"),
            "pos": item.get("詞性"), 
            "meaning_zh": item.get("中文解釋"),
            "user_email": "alice@test.com",
            "mastery": item.get("mastery", 1),
            "category": item.get("類別", "預設")
        }
        
        # 直接把資料「POST」到 Supabase 的門口
        # 注意：url 後面要接 /rest/v1/你的表名
        api_url = f"{URL}/rest/v1/vocabulary"
        
        try:
            response = client.post(api_url, json=new_row, headers=headers)
            response.raise_for_status()
            print(f"✅ 成功搬移: {item.get('單字')}")
        except Exception as e:
            print(f"❌ 搬移 {item.get('單字')} 失敗: {e}")

print("\n--- 任務完成！ ---")