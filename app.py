import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="静岡県内高校 自転車通学・ヘルメット着用状況",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校 アンケート集計データ")

try:
    # SecretsからWeb公開用CSV URLを取得
    csv_url = st.secrets["SPREADSHEET_URL"]
    
    @st.cache_data(ttl=300)  # 5分キャッシュ
    def load_data(url):
        return pd.read_csv(url)

    df = load_data(csv_url)

    # 上部サマリー表示
    col1, col2, col3 = st.columns(3)
    col1.metric("回答回答校数", f"{len(df)} 校")
    
    st.success("✅ データ取得に成功しました")

    # データ一覧のプレビュー表示
    st.subheader("📊 回答データ一覧")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("Secretsの設定（SPREADSHEET_URL）をご確認ください。")
