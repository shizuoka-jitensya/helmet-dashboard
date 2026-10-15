import streamlit as st
import pandas as pd
import re

st.set_page_config(page_title="静岡県内高校 自転車通学・ヘルメット着用状況", layout="wide")

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校")

try:
    # SecretsからURLを取得
    sheet_url = st.secrets["SPREADSHEET_URL"]
    
    # スプレッドシートIDを正規表現で抽出
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", sheet_url)
    if not match:
        st.error("スプレッドシートのURL形式が不正です。")
        st.stop()
        
    sheet_id = match.group(1)
    
    # gid（シートID）が含まれている場合は抽出、なければデフォルト（0）
    gid_match = re.search(r"gid=([0-9]+)", sheet_url)
    gid = gid_match.group(1) if gid_match else "0"
    
    # 正しいCSVエクスポート用URLを構築
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    @st.cache_data(ttl=600)
    def load_data(url):
        return pd.read_csv(url)

    df = load_data(csv_url)

    # メトリクス表示
    col1, col2, col3 = st.columns(3)
    col1.metric("回答回答校数", f"{len(df)} 校")
    
    # データのプレビュー表示
    st.subheader("📊 アンケート集計データ一覧")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("Secretsの設定（SPREADSHEET_URL）およびスプレッドシートの共有設定をご確認ください。")
