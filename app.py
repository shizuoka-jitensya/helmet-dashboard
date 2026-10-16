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

# 組合公式HPドロップダウン指定に完全準拠した11地区定義＆市町・校名判定ルール
AREA_RULES = {
    "賀茂": ["下田", "東伊豆", "河津", "南伊豆", "松崎", "西伊豆", "稲取"],
    "田方": ["熱海", "伊東", "三島", "伊豆", "伊豆の国", "函南", "韮山", "修善寺", "伊豆中央", "伊豆総合", "知徳"],
    "沼駿": ["沼津", "御殿場", "裾野", "清水町", "長泉", "小山", "桐陽", "飛龍", "加藤学園"],
    "富士": ["富士", "富士宮", "吉原", "星陵"],
    "清庵": ["清水東", "清水西", "清水南", "清水国際", "清水桜が丘", "由比", "蒲原"],
    "静岡": ["葵区", "駿河区", "静岡", "城南", "橘", "サレジオ", "常葉", "科学技術"],
    "志太": ["焼津", "藤枝"],
    "榛原": ["島田", "牧之原", "吉田", "川根", "榛原"],
    "小笠": ["掛川", "菊川", "御前崎", "小笠"],
    "磐周": ["磐田", "袋井", "森町", "周南"],
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
    # 1. アンケート集計データの読み込み
    csv_url = st.secrets.get("SPREADSHEET_URL")
    if not csv_url:
        st.error("Secretsに SPREADSHEET_URL が設定されていません。")
        st.stop()
        
    df_survey = pd.read_csv(csv_url).dropna(how='all').reset_index(drop=True)

    # 2. 送付先マスターデータの安全な読み込み
    df_master = pd.DataFrame()
    if "MASTER_SPREADSHEET_URL" in st.secrets and st.secrets["MASTER_SPREADSHEET_URL"]:
        try:
            master_url = st.secrets["MASTER_SPREADSHEET_URL"]
            df_master = pd.read_csv(master_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass

    # アンケート側の学校名列特定
    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None)
    if not survey_school_col and len(df_survey.columns) > 1:
        survey_school_col = df_survey.columns[1]

    # 回答済みの学校名リスト抽出
    answered_schools = []
    if survey_school_col and len(df_survey) > 0:
        answered_schools = df_survey[survey_school_col].dropna().astype(str).tolist()

    # 地区の自動判定付与（アンケートデータ）
    if survey_school_col:
        df_survey["地区"] = df_survey[survey_school_col].astype(str).apply(get_area_from_text)
    else:
        df_survey["地区"] = "その他"

    # ---------------------------------------------------------
    # サイドバー：絞り込み・検索フィルター
    # ---------------------------------------------------------
    st.sidebar.header("🔍 絞り込み検索")
    
    # 公式11地区のドロップダウンメニュー
    area_options = ["すべての地区（全県）"] + list(AREA_RULES.keys()) + ["その他"]
    selected_area = st.sidebar.selectbox("地区で絞り込み", area_options)
    
    search_keyword = st.sidebar.text_input("学校名で検索")

    # フィルタリング処理
    filtered_survey = df_survey.copy()
    if selected_area != "すべての地区（全県）":
        filtered_survey = filtered_survey[filtered_survey["地区"] == selected_area]
    if search_keyword and survey_school_col:
        filtered_survey = filtered_survey[filtered_survey[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # ---------------------------------------------------------
    # 1. 上部サマリーカード（KPI）
    # ---------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    total_responses = len(df_survey)
    col1.metric("アンケート回答数", f"{total_responses} 校")
    
    master_school_col = next((c for c in df_master.columns if "学校" in str(c)), None) if not df_master.empty else None

    if not df_master.empty and master_school_col:
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
        if not df_master.empty and master_school_col:
            # マスターシート側の住所・学校名から住所文字列を生成して地区判定
            address_col = next((c for c in df_master.columns if "住所" in str(c)), "")
            
            def match_master_area(row):
                text_to_search = str(row[master_school_col]) + " " + (str(row[address_col]) if address_col else "")
                return get_area_from_text(text_to_search)

            df_master["地区"] = df_master.apply(match_master_area, axis=1)
            
            df_master["回答ステータス"] = df_master[master_school_col].apply(
                lambda x: "回答済み" if any(ans in str(x) or str(x) in ans for ans in answered_schools) else "未回答"
            )
            df_unanswered = df_master[df_master["回答ステータス"] == "未回答"]
            
            if selected_area != "すべての地区（全県）":
                df_unanswered = df_unanswered[df_unanswered["地区"] == selected_area]

            st.warning(f"現在、対象 {len(df_master)} 校中 **{len(df_unanswered)} 校** が未回答です。")
            
            show_cols = [c for c in ["地区", "設置区分", master_school_col, "電話番号", "メールアドレス / 連絡先状況"] if c in df_unanswered.columns]
            st.dataframe(df_unanswered[show_cols], use_container_width=True)
        else:
            st.info("💡 送付先学校一覧シート（MASTER_SPREADSHEET_URL）を設定すると、ここに未回答校リストが自動表示されます。")

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
