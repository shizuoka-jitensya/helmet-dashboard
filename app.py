import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="静岡県内高校 自転車通学・ヘルメット着用状況",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校 アンケート集計データ")

# 静岡県内高校の地区マッピングルール（キーワード判定用）
AREA_RULES = {
    "賀茂": ["下田", "稲取", "松崎", "河津"],
    "田方": ["伊豆中央", "修善寺工業", "伊豆総合", "韮山", "田方農業", "知徳"],
    "熱海・伊東": ["熱海", "伊東", "伊東商業"],
    "沼津・駿東": ["沼津", "桐陽", "飛龍", "加藤学園", "裾野", "御殿場", "小山"],
    "富士": ["富士", "吉原", "星陵", "富士宮"],
    "静岡・中部": ["静岡", "駿河", "清水", "城南", "橘", "サレジオ", "常葉", "葵"],
    "志太榛原": ["藤枝", "焼津", "島田", "榛原"],
    "中遠": ["磐田", "袋井", "掛川", "小笠", "菊川"],
    "西遠": ["浜松", "湖西", "浜名", "オイスカ"]
}

def get_area_name(school_name):
    """学校名から地区名を判定する関数"""
    if not isinstance(school_name, str) or not school_name:
        return "未分類/その他"
    for area, keywords in AREA_RULES.items():
        if any(keyword in school_name for keyword in keywords):
            return area
    return "その他"

try:
    csv_url = st.secrets["SPREADSHEET_URL"]
    df = pd.read_csv(csv_url).dropna(how='all')

    # 学校名列の特定（「学校名」という文字が含まれる列を探す）
    school_col = next((col for col in df.columns if "学校名" in col), None)

    if school_col:
        # 地区列を自動付与
        df["地区"] = df[school_col].apply(get_area_name)

        # サイドバー：地区・学校名フィルター
        st.sidebar.header("🔍 絞り込み検索")
        
        # 地区フィルター
        area_list = ["すべて"] + list(AREA_RULES.keys()) + ["その他"]
        selected_area = st.sidebar.selectbox("地区で絞り込み", area_list)
        
        # 学校名キーワード検索
        search_keyword = st.sidebar.text_input("学校名で検索（キーワード）")

        # フィルタリング処理
        filtered_df = df.copy()
        if selected_area != "すべて":
            filtered_df = filtered_df[filtered_df["地区"] == selected_area]
        if search_keyword:
            filtered_df = filtered_df[filtered_df[school_col].str.contains(search_keyword, na=False)]

        # KPIメトリクス表示
        col1, col2, col3 = st.columns(3)
        col1.metric("総回答校数", f"{len(df)} 校")
        col2.metric("絞り込み表示数", f"{len(filtered_df)} 校")
        col3.metric("選択地区", selected_area)

        # 地区別回答件数の表示
        st.subheader("📍 地区別回答状況")
        area_counts = filtered_df["地区"].value_counts().reset_index()
        area_counts.columns = ["地区", "回答校数"]
        st.dataframe(area_counts, use_container_width=True)

        # データ一覧（地区列を先頭に移動）
        st.subheader("📊 回答データ一覧")
        cols = ["地区"] + [col for col in filtered_df.columns if col != "地区"]
        st.dataframe(filtered_df[cols], use_container_width=True)

    else:
        st.warning("スプレッドシートに『学校名』の項目が見つかりませんでした。")
        st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"データの読み込みに失敗しました: {e}")
    st.info("Secretsの設定（SPREADSHEET_URL）をご確認ください。")
