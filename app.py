import streamlit as st
import pandas as pd

st.set_page_config(page_title="静岡県内高校 自転車通学・ヘルメット着用状況", layout="wide")

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校")

# SecretsからスプレッドシートURLを取得
try:
    sheet_url = st.secrets["SPREADSHEET_URL"]
    # CSV出力用URLに変換
    csv_url = sheet_url.replace("/edit", "/export?format=csv")
    
    @st.cache_data(ttl=600)
    def load_data(url):
        return pd.read_csv(url)

    df = load_data(csv_url)

    # メトリクス表示
    col1, col2, col3 = st.columns(3)
    col1.metric("調査対象校数", f"{len(df)} 校")
    
    # データのプレビュー
    st.subheader("📊 調査データ一覧")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("Secretsの設定（SPREADSHEET_URL）およびスプレッドシートの共有設定をご確認ください。")
