import streamlit as st
import pandas as pd
import plotly.express as px
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="【組合員専用】静岡県内高校 自転車通学・ヘルメットアンケート閲覧システム",
    page_icon="🔒",
    layout="wide"
)

# 組合公式HPドロップダウン指定に完全準拠した11地区定義
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
    
    # 簡易日本語フォントスタイル
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=16, leading=20, alignment=1)
    body_style = ParagraphStyle('BodyStyle', parent=styles['Normal'], fontSize=9, leading=12)
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.whitesmoke)

    school_name = str(school_data.get('学校名', '高校アンケート回答'))
    story.append(Paragraph(f"🚲 自転車通学・ヘルメット着用状況 回答シート", title_style))
    story.append(Spacer(1, 10))

    # アンケート設問・回答データの表組み作成
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

    t = Table(table_data, colWidths=[200, 320])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- 認証処理 ---
try:
    # 1. データの読み込み
    csv_url = st.secrets.get("SPREADSHEET_URL")
    master_url = st.secrets.get("MASTER_SPREADSHEET_URL")
    store_url = st.secrets.get("STORE_SPREADSHEET_URL") # 店舗マスターURL

    if not csv_url:
        st.error("システムエラー: SPREADSHEET_URL が未設定です。")
        st.stop()

    df_survey = pd.read_csv(csv_url).dropna(how='all').reset_index(drop=True)
    df_master = pd.read_csv(master_url).dropna(how='all').reset_index(drop=True) if master_url else pd.DataFrame()
    df_stores = pd.read_csv(store_url).dropna(how='all').reset_index(drop=True) if store_url else pd.DataFrame()

    # 店舗マスター列名の正規化
    if not df_stores.empty:
        df_stores.columns = [c.strip() for c in df_stores.columns]

    # セッション状態の初期化（ログイン管理）
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.store_info = None

    # --- ログイン画面 ---
    if not st.session_state.authenticated:
        st.title("🔒 自転車組合 組合員専用閲覧システム")
        st.caption("※当システムの情報は組合外部・一般には非公表です。")
        
        with st.form("login_form"):
            access_key_input = st.text_input("アクセスキーを入力してください", type="password")
            submit_btn = st.form_submit_button("ログイン")
            
            if submit_btn:
                if not df_stores.empty and "アクセスキー" in df_stores.columns:
                    # 有効なアクセスキーの判定
                    valid_store = df_stores[df_stores["アクセスキー"].astype(str).str.strip() == access_key_input.strip()]
                    if not valid_store.empty and pd.notna(access_key_input.strip()):
                        st.session_state.authenticated = True
                        st.session_state.store_info = valid_store.iloc[0].to_dict()
                        st.success("認証に成功しました。")
                        st.rerun()
                    else:
                        st.error("アクセスキーが正しくないか、無効（脱退・未登録）です。組合事務局にお問い合わせください。")
                elif access_key_input == "admin123": # 事務局用バックドア例
                    st.session_state.authenticated = True
                    st.session_state.store_info = {"店舗名": "組合事務局", "地区": "全県"}
                    st.rerun()
                else:
                    st.error("店舗マスターが連携されていないか、アクセスキーが無効です。")
        st.stop()

    # --- ログイン後のメイン画面 ---
    store = st.session_state.store_info
    
    # ログアウトボタン
    st.sidebar.markdown(f"**ログイン店舗:** {store.get('店舗名', '組合員')}")
    st.sidebar.markdown(f"**自地区:** {store.get('地区', '-')}地区")
    if st.sidebar.button("ログアウト"):
        st.session_state.authenticated = False
        st.session_state.store_info = None
        st.rerun()

    st.title("🚲 静岡県内高校 自転車通学アンケート集計閲覧システム")
    st.caption("【組合員限定】非公表情報（第三者への提供・公開厳禁）")

    # 地区の自動付与（アンケートデータ）
    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None) or df_survey.columns[1]
    survey_addr_col = next((col for col in df_survey.columns if "住所" in str(col)), None)

    def judge_survey_area(row):
        addr_text = str(row[survey_addr_col]) if survey_addr_col and pd.notna(row[survey_addr_col]) else ""
        school_text = str(row[survey_school_col]) if pd.notna(row[survey_school_col]) else ""
        area = get_area_from_text(addr_text)
        if area == "その他":
            area = get_area_from_text(school_text)
        return area

    df_survey["地区"] = df_survey.apply(judge_survey_area, axis=1)

    # --- サイドバー絞り込み（デフォルトは自地区） ---
    st.sidebar.header("🔍 表示データの絞り込み")
    default_index = 0
    area_list = ["すべての地区（全県）"] + list(AREA_RULES.keys()) + ["その他"]
    
    if store.get("地区") in AREA_RULES:
        default_index = area_list.index(store.get("地区"))

    selected_area = st.sidebar.selectbox("地区を選択（他地区も参照可）", area_list, index=default_index)
    search_keyword = st.sidebar.text_input("学校名で検索")

    # データ絞り込み
    filtered_df = df_survey.copy()
    if selected_area != "すべての地区（全県）":
        filtered_df = filtered_df[filtered_df["地区"] == selected_area]
    if search_keyword:
        filtered_df = filtered_df[filtered_df[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # --- メインコンテンツ ---
    tab1, tab2 = st.tabs(["📄 学校別 回答PDF印刷・閲覧", "📊 設問集計・グラフ分析"])

    with tab1:
        st.subheader("🏫 学校別回答の閲覧・A4 PDF出力")
        
        if len(filtered_df) > 0:
            selected_school_name = st.selectbox("閲覧・印刷する学校を選択してください：", filtered_df[survey_school_col].unique())
            school_data = filtered_df[filtered_df[survey_school_col] == selected_school_name].iloc[0].to_dict()
            
            # PDFダウンロードボタン
            pdf_bytes = generate_pdf(school_data)
            st.download_button(
                label=f"📥 【{selected_school_name}】の回答結果を A4 PDF で印刷・保存",
                data=pdf_bytes,
                file_name=f"{selected_school_name}_アンケート回答.pdf",
                mime="application/pdf",
                type="primary"
            )
            
            st.markdown("---")
            st.markdown(f"#### 📋 【{selected_school_name}】 回答詳細")
            # 画面上でのテーブル表示
            detail_df = pd.DataFrame(list(school_data.items()), columns=["項目・設問", "回答内容"])
            st.dataframe(detail_df, use_container_width=True)
        else:
            st.info("該当する学校の回答データがありません。")

    with tab2:
        st.subheader("📈 設問別 集計グラフ")
        rule_cols = [col for col in df_survey.columns if any(k in str(col) for k in ["ヘルメット", "許可", "点検", "TSマーク", "施錠", "ルール"])]
        if rule_cols and len(filtered_survey := filtered_df) > 0:
            selected_q = st.selectbox("集計設問の選択：", rule_cols)
            if selected_q:
                q_counts = filtered_survey[selected_q].value_counts().reset_index()
                q_counts.columns = ["回答内容", "校数"]
                fig_q = px.pie(q_counts, names="回答内容", values="校数", title=f"【集計】{selected_q}", hole=0.4)
                st.plotly_chart(fig_q, use_container_width=True)

except Exception as e:
    st.error(f"エラーが発生しました: {e}")
