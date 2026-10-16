import streamlit as st
import pandas as pd
import plotly.express as px
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(
    page_title="【組合員専用】静岡県内高校 自転車通学・ヘルメットアンケート閲覧システム",
    page_icon="🔒",
    layout="wide"
)

# 組合公式HPドロップダウン指定に完全準拠した11地区定義＆市町・校名判定ルール
AREA_RULES = {
    "賀茂": ["下田", "東伊豆", "河津", "南伊豆", "松崎", "西伊豆", "稲取"],
    "田方": ["熱海", "伊東", "三島", "伊豆", "伊豆の国", "函南", "韮山", "修善寺", "伊豆中央", "伊豆総合", "知徳"],
    "沼駿": ["沼津", "御殿場", "裾野", "清水町", "長泉", "小山", "桐陽", "飛龍", "加藤学園"],
    "富士": ["富士市", "富士宮", "吉原", "星陵"],
    "清庵": ["清水区", "由比", "蒲原", "清水東", "清水西", "清水南", "清水国際", "清水桜が丘"],
    "静岡": ["葵区", "駿河区", "城南", "橘", "サレジオ", "常葉", "科学技術"],
    "志太": ["焼津", "藤枝"],
    "榛原": ["島田", "牧之原", "吉田町", "川根", "榛原"],
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

# --- PDF生成機能（A4サイズ1枚に収めるレイアウト） ---
def generate_pdf(school_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=15, leading=18, alignment=1)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=8, leading=11)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.whitesmoke)

    school_name = str(school_data.get('学校名', '高校アンケート回答'))
    story.append(Paragraph(f"🚲 静岡県内高校 自転車通学・ヘルメット着用状況 回答シート", title_style))
    story.append(Spacer(1, 8))

    table_data = [
        [Paragraph("<b>項目 / 設問</b>", header_style), Paragraph("<b>回答内容</b>", header_style)]
    ]
    
    ignore_keys = ["地区", "タイムスタンプ"]
    for key, val in school_data.items():
        if key in ignore_keys or pd.isna(val):
            continue
        q_text = Paragraph(str(key), body_style)
        a_text = Paragraph(str(val), body_style)
        table_data.append([q_text, a_text])

    t = Table(table_data, colWidths=[180, 340])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- データの安全な取得（404保護付き） ---
try:
    csv_url = st.secrets.get("SPREADSHEET_URL")
    master_url = st.secrets.get("MASTER_SPREADSHEET_URL")
    store_url = st.secrets.get("STORE_SPREADSHEET_URL")

    df_survey = pd.DataFrame()
    df_master = pd.DataFrame()
    df_stores = pd.DataFrame()

    if csv_url:
        try:
            df_survey = pd.read_csv(csv_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass

    if master_url:
        try:
            df_master = pd.read_csv(master_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass

    if store_url:
        try:
            df_stores = pd.read_csv(store_url).dropna(how='all').reset_index(drop=True)
            df_stores.columns = [c.strip() for c in df_stores.columns]
        except Exception:
            pass

    # セッション状態の初期化
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.store_info = None

    # --- 1. ログイン認証画面 ---
    if not st.session_state.authenticated:
        st.title("🔒 自転車組合 組合員専用閲覧システム")
        st.caption("※当システムの情報は組合事務局集計によるものであり、組合外部・一般には非公表です。")
        
        with st.form("login_form"):
            access_key_input = st.text_input("アクセスキーを入力してください", type="password")
            submit_btn = st.form_submit_button("ログイン")
            
            if submit_btn:
                if not df_stores.empty and "アクセスキー" in df_stores.columns:
                    valid_store = df_stores[df_stores["アクセスキー"].astype(str).str.strip() == access_key_input.strip()]
                    if not valid_store.empty and pd.notna(access_key_input.strip()):
                        st.session_state.authenticated = True
                        st.session_state.store_info = valid_store.iloc[0].to_dict()
                        st.success("認証に成功しました。")
                        st.rerun()
                    else:
                        st.error("アクセスキーが正しくないか、無効（脱退・未登録）です。組合事務局にお問い合わせください。")
                elif access_key_input == "admin123":  # 事務局管理者用
                    st.session_state.authenticated = True
                    st.session_state.store_info = {"店舗名": "組合事務局", "地区": "全県"}
                    st.rerun()
                else:
                    st.error("店舗マスターが読み込めていないか、アクセスキーが無効です。")
        st.stop()

    # --- 2. ログイン後のメイン画面 ---
    store = st.session_state.store_info
    
    st.sidebar.markdown(f"**ログイン店舗:** {store.get('店舗名', '組合員')}")
    st.sidebar.markdown(f"**自地区:** {store.get('地区', '-')}地区")
    if st.sidebar.button("ログアウト"):
        st.session_state.authenticated = False
        st.session_state.store_info = None
        st.rerun()

    st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
    st.caption("【組合員限定閲覧】（一般非公開情報）")

    # 地区の自動判定付与（アンケートデータ）
    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None) or df_survey.columns[1] if not df_survey.empty else None
    survey_addr_col = next((col for col in df_survey.columns if "住所" in str(col)), None) if not df_survey.empty else None

    def judge_survey_area(row):
        addr_text = str(row[survey_addr_col]) if survey_addr_col and pd.notna(row[survey_addr_col]) else ""
        school_text = str(row[survey_school_col]) if pd.notna(row[survey_school_col]) else ""
        area = get_area_from_text(addr_text)
        if area == "その他":
            area = get_area_from_text(school_text)
        return area

    if not df_survey.empty:
        df_survey["地区"] = df_survey.apply(judge_survey_area, axis=1)

    # サイドバー：自地区優先の絞り込み
    st.sidebar.header("🔍 絞り込み検索")
    area_list = ["すべての地区（全県）"] + list(AREA_RULES.keys()) + ["その他"]
    default_index = 0
    if store.get("地区") in AREA_RULES:
        default_index = area_list.index(store.get("地区"))

    selected_area = st.sidebar.selectbox("地区を選択（他地区も参照可能）", area_list, index=default_index)
    search_keyword = st.sidebar.text_input("学校名で検索")

    # フィルタリング
    filtered_survey = df_survey.copy()
    if not filtered_survey.empty:
        if selected_area != "すべての地区（全県）":
            filtered_survey = filtered_survey[filtered_survey["地区"] == selected_area]
        if search_keyword and survey_school_col:
            filtered_survey = filtered_survey[filtered_survey[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # 上部サマリーカード
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

    col4.metric("ログインステータス", "認証済み")

    st.markdown("---")

    # タブ画面
    tab1, tab2, tab3 = st.tabs(["📄 学校別 回答PDF印刷・閲覧", "📊 設問集計・グラフ分析", "📋 未回答校リスト（進捗管理）"])

    with tab1:
        st.subheader("🏫 学校別回答の閲覧・A4 PDF出力")
        if not filtered_survey.empty and survey_school_col:
            selected_school_name = st.selectbox("閲覧・印刷する学校を選択してください：", filtered_survey[survey_school_col].unique())
            school_data = filtered_survey[filtered_survey[survey_school_col] == selected_school_name].iloc[0].to_dict()
            
            # PDF出力ボタン
            pdf_bytes = generate_pdf(school_data)
            st.download_button(
                label=f"📥 【{selected_school_name}】の回答結果を A4 PDF で保存・印刷",
                data=pdf_bytes,
                file_name=f"{selected_school_name}_アンケート回答.pdf",
                mime="application/pdf",
                type="primary"
            )
            
            st.markdown("---")
            st.markdown(f"#### 📋 【{selected_school_name}】 回答詳細")
            detail_df = pd.DataFrame(list(school_data.items()), columns=["項目・設問", "回答内容"])
            st.dataframe(detail_df, use_container_width=True)
        else:
            st.info("該当する学校の回答データがありません。")

    with tab2:
        st.subheader("💡 設問別回答割合")
        rule_cols = [col for col in df_survey.columns if any(k in str(col) for k in ["ヘルメット", "許可", "点検", "TSマーク", "施錠", "ルール"])] if not df_survey.empty else []
        if rule_cols and len(filtered_survey) > 0:
            selected_q = st.selectbox("集計したい設問を選択してください：", rule_cols)
            if selected_q:
                q_counts = filtered_survey[selected_q].value_counts().reset_index()
                q_counts.columns = ["回答内容", "校数"]
                fig_q = px.pie(q_counts, names="回答内容", values="校数", title=f"【設問集計】{selected_q}", hole=0.4)
                st.plotly_chart(fig_q, use_container_width=True)

    with tab3:
        st.subheader("⚠️ 未回答校の進捗管理")
        if not df_master.empty and master_school_col:
            master_addr_col = next((c for c in df_master.columns if "住所" in str(c)), None)
            
            def judge_master_area(row):
                addr_text = str(row[master_addr_col]) if master_addr_col and pd.notna(row[master_addr_col]) else ""
                school_text = str(row[master_school_col]) if pd.notna(row[master_school_col]) else ""
                area = get_area_from_text(addr_text)
                if area == "その他":
                    area = get_area_from_text(school_text)
                return area

            df_master["地区"] = df_master.apply(judge_master_area, axis=1)
            
            answered_schools = df_survey[survey_school_col].dropna().astype(str).tolist() if not df_survey.empty and survey_school_col else []
            
            df_master["回答ステータス"] = df_master[master_school_col].apply(
                lambda x: "回答済み" if any(ans in str(x) or str(x) in ans for ans in answered_schools) else "未回答"
            )
            df_unanswered = df_master[df_master["回答ステータス"] == "未回答"]
            
            if selected_area != "すべての地区（全県）":
                df_unanswered = df_unanswered[df_unanswered["地区"] == selected_area]

            st.warning(f"現在、対象 {len(df_master)} 校中 **{len(df_unanswered)} 校** が未回答です。")
            show_cols = [c for c in ["地区", "設置区分", master_school_col, "住所", "電話番号", "メールアドレス / 連絡先状況"] if c in df_unanswered.columns]
            st.dataframe(df_unanswered[show_cols], use_container_width=True)
        else:
            st.info("💡 送付先マスターが連携されると、未回答校リストが自動表示されます。")

except Exception as e:
    st.error(f"システムエラーが発生しました: {e}")
