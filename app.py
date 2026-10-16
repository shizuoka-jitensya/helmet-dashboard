import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(
    page_title="静岡県内高校 自転車通学・ヘルメット着用状況",
    page_icon="🚲",
    layout="wide"
)

st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
st.caption("対象：静岡県内高校 送付先マスター＆アンケート集計・未回答校管理")

# 組合HP・県内地区区分マッピングルール（市名・地区キーワード）
AREA_RULES = {
    "賀茂": ["下田", "稲取", "松崎", "河津", "南伊豆", "西伊豆"],
    "田方": ["伊豆中央", "修善寺", "伊豆総合", "韮山", "田方", "知徳", "伊豆市", "伊豆の国市", "函南"],
    "熱海・伊東": ["熱海", "伊東"],
    "沼津・駿東": ["沼津", "桐陽", "飛龍", "加藤学園", "裾野", "御殿場", "小山", "清水町", "長泉"],
    "富士": ["富士", "吉原", "星陵", "富士宮"],
    "清庵": ["由比", "蒲原", "清水東", "清水西", "清水南", "清水国際", "清水桜が丘"],
    "静岡・中部": ["静岡", "駿河", "城南", "橘", "サレジオ", "常葉", "葵区", "駿河区", "科学技術"],
    "志太榛原": ["藤枝", "焼津", "島田", "榛原", "川根", "吉田"],
    "中遠（小笠・磐周）": ["磐田", "袋井", "掛川", "小笠", "菊川", "周南", "森町", "御前崎"],
    "西遠": ["浜松", "湖西", "浜名", "オイスカ", "江之島"]
}

def get_area_from_text(text):
    if not isinstance(text, str) or not text:
        return "その他"
    for area, keywords in AREA_RULES.items():
        for keyword in keywords:
            if keyword in text:
                return area
    return "その他"

try:
    # Googleスプレッドシート（Web公開CSV）の取得
    csv_url = st.secrets["SPREADSHEET_URL"]
    
    # 複数シート読み込み対応（メインシート＆送付先リストシート）
    # ※ SPREADSHEET_URLはメインのアンケート集計URL
    df_survey = pd.read_csv(csv_url).dropna(how='all').reset_index(drop=True)

    # 送付先学校一覧URLが個別に設定されている場合、またはSecretsから読み込み
    master_url = st.secrets.get("MASTER_SPREADSHEET_URL", csv_url)
    
    try:
        df_master = pd.read_csv(master_url).dropna(how='all').reset_index(drop=True)
    except:
        df_master = pd.DataFrame()

    # 「学校名」列の特定
    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None)
    if not survey_school_col and len(df_survey.columns) > 1:
        survey_school_col = df_survey.columns[1]

    # 回答済みの学校名リスト抽出
    answered_schools = []
    if survey_school_col and len(df_survey) > 0:
        answered_schools = df_survey[survey_school_col].dropna().astype(str).tolist()

    # 地区の自動判定付与
    if survey_school_col:
        df_survey["地区"] = df_survey[survey_school_col].astype(str).apply(get_area_from_text)
    else:
        df_survey["地区"] = "その他"

    # ---------------------------------------------------------
    # サイドバー：絞り込み・検索フィルター
    # ---------------------------------------------------------
    st.sidebar.header("🔍 絞り込み検索")
    
    area_options = ["すべて"] + list(AREA_RULES.keys()) + ["その他"]
    selected_area = st.sidebar.selectbox("地区で絞り込み", area_options)
    
    search_keyword = st.sidebar.text_input("学校名で検索")

    # フィルタリング処理
    filtered_survey = df_survey.copy()
    if selected_area != "すべて":
        filtered_survey = filtered_survey[filtered_survey["地区"] == selected_area]
    if search_keyword and survey_school_col:
        filtered_survey = filtered_survey[filtered_survey[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # ---------------------------------------------------------
    # 1. 上部サマリーカード（KPI）
    # ---------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    total_responses = len(df_survey)
    col1.metric("アンケート回答数", f"{total_responses} 校")
    
    if not df_master.empty and "学校名" in df_master.columns:
        total_master = len(df_master)
        response_rate = int((total_responses / total_master) * 100) if total_master > 0 else 0
        col2.metric("対象全高校数", f"{total_master} 校")
        col3.metric("全体回答率", f"{response_rate} %")
    else:
        col2.metric("絞り込み表示数", f"{len(filtered_survey)} 校")
        col3.metric("選択地区", selected_area)

    col4.metric("システムステータス", "正常同期中")

    st.markdown("---")

    # ---------------------------------------------------------
    # 2. タブ別分析画面
    # ---------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 回答データ＆集計", "📍 地区別回答状況", "📋 未回答校リスト（進捗管理）"])

    with tab1:
        st.subheader("💡 設問別回答割合")
        rule_cols = [col for col in df_survey.columns if any(k in str(col) for k in ["ヘルメット", "許可", "点検", "TSマーク", "施錠", "ルール"])]
        
        if rule_cols and len(filtered_survey) > 0:
            selected_q = st.selectbox("集計したい設問を選択してください：", rule_cols)
            if selected_q:
                q_counts = filtered_survey[selected_q].value_counts().reset_index()
                q_counts.columns = ["回答内容", "校数"]
                fig_q = px.pie(q_counts, names="回答内容", values="校数", title=f"【設問集計】{selected_q}", hole=0.4)
                st.plotly_chart(fig_q, use_container_width=True)
        
        st.subheader("📄 アンケート回答一覧")
        display_cols = ["地区"] + [c for c in filtered_survey.columns if c != "地区"]
        st.dataframe(filtered_survey[display_cols], use_container_width=True)

    with tab2:
        st.subheader("📍 地区別 回答校数グラフ")
        if len(filtered_survey) > 0:
            area_counts = filtered_survey["地区"].value_counts().reset_index()
            area_counts.columns = ["地区", "回答校数"]
            fig_area = px.bar(area_counts, x="地区", y="回答校数", text="回答校数", color="地区")
            st.plotly_chart(fig_area, use_container_width=True)

    with tab3:
        st.subheader("⚠️ 未回答校の進捗管理")
        if not df_master.empty and "学校名" in df_master.columns:
            # 未回答校の抽出ロジック
            df_master["回答ステータス"] = df_master["学校名"].apply(
                lambda x: "回答済み" if any(ans in str(x) or str(x) in ans for ans in answered_schools) else "未回答"
            )
            df_unanswered = df_master[df_master["回答ステータス"] == "未回答"]
            
            st.warning(f"現在、対象 {len(df_master)} 校中 **{len(df_unanswered)} 校** が未回答です。")
            st.dataframe(df_unanswered[["設置区分", "学校名", "電話番号", "メールアドレス / 連絡先状況"]], use_container_width=True)
        else:
            st.info("送付先学校一覧マスターが読み込まれると、ここに未回答校一覧が自動生成されます。")

except Exception as e:
    st.error(f"データ連携エラーが発生しました: {e}")
