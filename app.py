import streamlit as st
import pandas as pd

st.set_page_config(page_title="静岡県内高校 自転車通学・ヘルメット着用状況", layout="wide")

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校")

# Secretsから設定を取得
try:
    raw_url = st.secrets["SPREADSHEET_URL"]
    
    # URLから純粋なスプレッドシートIDを抽出
    sheet_id = "13AVMiisXTYDV9AiG0DfH9ht4clkfw1YuaeHpqL761M"
    if "/d/" in raw_url:
        sheet_id = raw_url.split("/d/")[1].split("/")[0]
    
    # 確実にデータを引き出す公開CSV直接取得URL
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    @st.cache_data(ttl=0)  # キャッシュを保持しない
    def fetch_data(url):
        return pd.read_csv(url)

    df = fetch_data(csv_url)

    # 成功時のデータ表示
    st.success("✅ スプレッドシートデータの取得に成功しました！")
    
    col1, col2 = st.columns(2)
    col1.metric("アンケート回答件数", f"{len(df)} 件")
    
    st.subheader("📊 調査データ一覧")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("※ スプレッドシートの「共有」設定で【リンクを知っている全員（閲覧者）】になっているか再確認してください。")
