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
    
    # データを読み込み（空行を除外せずそのまま読み込む）
    df = pd.read_csv(csv_url)
    
    # 完全に空の行（タイムスタンプ等も空の行）のみ削除
    df = df.dropna(how='all')

    # 回答件数の表示
    st.metric("現在の回答数", f"{len(df)} 件")
    
    st.success("✅ データ取得に成功しました")

    # データのテーブル表示
    st.subheader("📊 回答データ一覧")
    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("Secretsの設定（SPREADSHEET_URL）をご確認ください。")
