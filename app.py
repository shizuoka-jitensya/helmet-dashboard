import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="静岡県内高校 自転車通学・ヘルメット着用状況",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校141校 アンケート集計・分析")

# 組合HPソースに基づく正確な地区区分マッピング
AREA_RULES = {
    "賀茂": ["下田", "稲取", "松崎", "河津"],
    "田方": ["伊豆中央", "修善寺", "伊豆総合", "韮山", "田方", "知徳"],
    "熱海・伊東": ["熱海", "伊東"],
    "沼津・駿東": ["沼津", "桐陽", "飛龍", "加藤学園", "裾野", "御殿場", "小山", "知徳"],
    "富士": ["富士", "吉原", "星陵", "富士宮"],
    "静岡・中部": ["静岡", "駿河", "清水", "城南", "橘", "サレジオ", "常葉", "葵"],
    "志太榛原": ["藤枝", "焼津", "島田", "榛原"],
    "中遠（小笠・磐周）": ["磐田", "袋井", "掛川", "小笠", "菊川", "周南"],
    "西遠": ["浜松", "湖西", "浜名", "オイスカ", "江之島"]
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
    csv_url = st.secrets["SPREADSHEET_URL"]
    df = pd.read_csv(csv_url).dropna(how='all').reset_index(drop=True)

    # 「学校名」列の判定
    school_col = next((col for col in df.columns if "学校" in str(col)), None)
    if not school_col and len(df.columns) > 1:
        school_col = df.columns[1]

    # 地区の自動判定付与
    if school_col:
        df["地区"] = df[school_col].astype(str).apply(get_area_name)
    else:
        df["地区"] = "その他"

    # ---------------------------------------------------------
    # サイドバー：絞り込み・検索フィルター
    # ---------------------------------------------------------
    st.sidebar.header("🔍 絞り込み検索")
    
    area_options = ["すべて"] + list(AREA_RULES.keys()) + ["その他"]
    selected_area = st.sidebar.selectbox("地区で絞り込み", area_options)
    
    search_keyword = st.sidebar.text_input("学校名で検索")

    # データの絞り込み実行
    filtered_df = df.copy()
    if selected_area != "すべて":
        filtered_df = filtered_df[filtered_df["地区"] == selected_area]
    if search_keyword and school_col:
        filtered_df = filtered_df[filtered_df[school_col].astype(str).str.contains(search_keyword, na=False)]

    # ---------------------------------------------------------
    # 1. 上部サマリーカード（メトリクス）
    # ---------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("総回答数", f"{len(df)} 件")
    col2.metric("絞り込み表示数", f"{len(filtered_df)} 件")
    col3.metric("選択中の地区", selected_area)
    
    # 許可基準の「はい」回答割合例（該当列が存在する場合）
    permit_col = next((col for col in df.columns if "許可" in str(col)), None)
    if permit_col and len(filtered_df) > 0:
        permit_yes = filtered_df[permit_col].astype(str).str.contains("はい|許可|条件", na=False).sum()
        col4.metric("通学許可あり（率）", f"{permit_yes} 校 ({int(permit_yes/len(filtered_df)*100)}%)")
    else:
        col4.metric("データステータス", "正常同期中")

    st.markdown("---")

    # ---------------------------------------------------------
    # 2. 集計グラフ（Plotly）
    # ---------------------------------------------------------
    st.subheader("📈 集計・可視化グラフ")
    
    tab1, tab2 = st.tabs(["📍 地区別回答状況", "🚲 ヘルメット・通学ルール集計"])

    with tab1:
        if len(filtered_df) > 0:
            area_counts = filtered_df["地区"].value_counts().reset_index()
            area_counts.columns = ["地区", "回答校数"]
            fig_area = px.bar(
                area_counts, x="地区", y="回答校数", 
                text="回答校数",
                title="地区別 回答校数一覧",
                color="地区"
            )
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("該当するデータがありません。")

    with tab2:
        # ヘルメット・ルール関連質問の列を自動抽出して円グラフ化
        rule_cols = [col for col in df.columns if any(k in str(col) for k in ["ヘルメット", "許可", "点検", "TSマーク", "二重施錠"])]
        
        if rule_cols:
            selected_q = st.selectbox("集計したい設問を選択してください：", rule_cols)
            if selected_q and len(filtered_df) > 0:
                q_counts = filtered_df[selected_q].value_counts().reset_index()
                q_counts.columns = ["回答内容", "校数"]
                
                fig_q = px.pie(
                    q_counts, names="回答内容", values="校数", 
                    title=f"【設問】{selected_q}",
                    hole=0.4
                )
                st.plotly_chart(fig_q, use_container_width=True)
        else:
            st.info("アンケートの設問項目を集計中です。")

    st.markdown("---")

    # ---------------------------------------------------------
    # 3. データ一覧表示
    # ---------------------------------------------------------
    st.subheader("📊 回答データ詳細")
    display_cols = ["地区"] + [c for c in filtered_df.columns if c != "地区"]
    st.dataframe(filtered_df[display_cols], use_container_width=True)

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
