import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="静岡県内高校 自転車通学・ヘルメット着用状況",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校 アンケート集計データ")

# 静岡県内の地区マッピングルール
AREA_RULES = {
    "賀茂": ["下田", "稲取", "松崎", "河津"],
    "田方": ["伊豆中央", "修善寺", "伊豆総合", "韮山", "田方", "知徳"],
    "熱海・伊東": ["熱海", "伊東"],
    "沼津・駿東": ["沼津", "桐陽", "飛龍", "加藤学園", "裾野", "御殿場", "小山"],
    "富士": ["富士", "吉原", "星陵", "富士宮"],
    "静岡・中部": ["静岡", "駿河", "清水", "城南", "橘", "サレジオ", "常葉", "葵"],
    "志太榛原": ["藤枝", "焼津", "島田", "榛原"],
    "中遠": ["磐田", "袋井", "掛川", "小笠", "菊川"],
    "西遠": ["浜松", "湖西", "浜名", "オイスカ"]
}

def get_area_name(school_name):
    if not isinstance(school_name, str) or not school_name:
        return "その他"
    for area, keywords in AREA_RULES.items():
        for keyword in keywords:
            if keyword in school_name:
                return area
    return "その他"

try:
    # 1. URL取得とデータ読み込み
    csv_url = st.secrets["SPREADSHEET_URL"]
    df = pd.read_csv(csv_url)
    
    # 完全空行の除去
    df = df.dropna(how='all').reset_index(drop=True)

    # 2. 「学校名」列の特定（2番目の列、あるいは列名に「学校」が含まれる列）
    school_col = None
    for col in df.columns:
        if "学校" in str(col):
            school_col = col
            break
            
    # 見つからない場合は2番目の列（B列）を使用
    if school_col is None and len(df.columns) > 1:
        school_col = df.columns[1]

    # 3. 地区判定の付与
    if school_col and school_col in df.columns:
        df["地区"] = df[school_col].astype(str).apply(get_area_name)
    else:
        df["地区"] = "その他"

    # 4. サイドバー絞り込みコントロール
    st.sidebar.header("🔍 絞り込み検索")
    
    area_options = ["すべて"] + list(AREA_RULES.keys()) + ["その他"]
    selected_area = st.sidebar.selectbox("地区で絞り込み", area_options)
    
    search_keyword = st.sidebar.text_input("学校名で検索")

    # 5. データのフィルタリング
    filtered_df = df.copy()
    
    if selected_area != "すべて":
        filtered_df = filtered_df[filtered_df["地区"] == selected_area]
        
    if search_keyword and school_col:
        filtered_df = filtered_df[filtered_df[school_col].astype(str).str.contains(search_keyword, na=False)]

    # 6. ダッシュボード表示
    col1, col2, col3 = st.columns(3)
    col1.metric("総回答数", f"{len(df)} 件")
    col2.metric("表示件数", f"{len(filtered_df)} 件")
    col3.metric("選択地区", selected_area)

    st.subheader("📊 回答データ一覧")
    
    # 地区列を一番左に移動して表示
    cols = ["地区"] + [c for c in filtered_df.columns if c != "地区"]
    st.dataframe(filtered_df[cols], use_container_width=True)

except Exception as e:
    st.error(f"アプリの実行中にエラーが発生しました: {e}")
