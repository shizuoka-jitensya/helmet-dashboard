import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
import requests
import threading
from datetime import datetime, timezone, timedelta

# 日本時間（JST: UTC+9）の定義
JST = timezone(timedelta(hours=9))

# ReportLab関連ライブラリ（日本語フォント設定・レイアウト用）
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 日本語CIDフォントの登録
JAPANESE_FONT = 'HeiseiKakuGo-W5'
pdfmetrics.registerFont(UnicodeCIDFont(JAPANESE_FONT))

st.set_page_config(
    page_title="【組合員専用】静岡県内高校 自転車通学・ヘルメットアンケート閲覧システム",
    page_icon="🔒",
    layout="wide"
)

# 住所から判定する11地区定義
AREA_RULES_ADDR = {
    "賀茂": ["下田市", "東伊豆町", "河津町", "南伊豆町", "松崎町", "西伊豆町", "賀茂郡"],
    "田方": ["熱海市", "伊東市", "三島市", "伊豆市", "伊豆の国市", "函南町", "田方郡"],
    "沼駿": ["沼津市", "御殿場市", "裾野市", "清水町", "長泉町", "小山町", "駿東郡"],
    "富士": ["富士市", "富士宮市"],
    "清庵": ["静岡市清水区", "清水区"],
    "静岡": ["静岡市葵区", "静岡市駿河区", "葵区", "駿河区"],
    "志太": ["焼津市", "藤枝市"],
    "榛原": ["島田市", "牧之原市", "吉田町", "川根本町", "川根町", "榛原郡"],
    "小笠": ["掛川市", "菊川市", "御前崎市"],
    "磐周": ["磐田市", "袋井市", "森町", "周智郡"],
    "西遠": ["浜松市", "湖西市"]
}

# 22項目の精査済み表示用カラム定義
DISPLAY_COLS = [
    ("自転車通学の許可", "許可"),
    ("自転車通学者数", "通学者数"),
    ("自転車通学許可基準の有無", "許可基準"),
    ("点検証明の有無", "点検証明"),
    ("点検を行う自転車店の指定", "店指定"),
    ("色の指定", "車体色"),
    ("ハンドルの形状", "ハンドル"),
    ("スタンドの仕様", "スタンド"),
    ("荷台（キャリア）についてのルール", "荷台"),
    ("鍵の数", "鍵数"),
    ("スポーツ・小径・折り畳み自転車について", "車種制限"),
    ("電動アシストについて", "電動アシスト"),
    ("新１年生の点検時期", "1年点検"),
    ("新２年生の点検時期", "2年点検"),
    ("新３年生の点検時期", "3年点検"),
    ("令和9年度（2027年4月）以降の「学校独自のヘルメット着用制度変更の予定」", "ヘルメット義務化"),
    ("特定の製品モデルのヘルメット指定", "ヘルメット指定"),
    ("令和9年度（2027年4月）以降のヘルメット不足への対応", "ヘルメット不足対応"),
    ("自転車保険・TSマークについて", "保険・TSマーク"),
    ("その他", "その他・特記事項")
]

# --------------------------------------------------
# ⚡ GASログ送信の非同期処理
# --------------------------------------------------
def _send_log_async(log_api_url, payload):
    try:
        requests.post(log_api_url, json=payload, timeout=5)
    except Exception:
        pass

def record_login_to_gas(store_id, store_name, timestamp):
    log_api_url = st.secrets.get("LOG_API_URL")
    if log_api_url:
        payload = {
            "store_id": str(store_id).strip(),
            "store_name": str(store_name).strip(),
            "timestamp": str(timestamp)
        }
        thread = threading.Thread(target=_send_log_async, args=(log_api_url, payload))
        thread.start()

# --------------------------------------------------
# ⚡ CSVキャッシュ読み込み（1分間保持へ短縮）
# --------------------------------------------------
@st.cache_data(ttl=60, show_spinner=False)
def load_csv_data(url):
    if not url or not str(url).startswith("http"):
        return pd.DataFrame()
    try:
        df = pd.read_csv(url).dropna(how='all').reset_index(drop=True)
        df.columns = [str(c).strip().lstrip("\ufeff") for c in df.columns]
        return df
    except Exception:
        return pd.DataFrame()

def get_area_by_address_only(address_text):
    if pd.isna(address_text):
        return "要確認"
    address = str(address_text).strip()
    if not address or address.lower() in {"nan", "none"}:
        return "要確認"
    
    all_rules = [
        (keyword, area)
        for area, keywords in AREA_RULES_ADDR.items()
        for keyword in keywords
    ]
    all_rules.sort(key=lambda item: len(item[0]), reverse=True)
    
    for keyword, area in all_rules:
        if keyword in address:
            return area
    return "要確認"

def normalize_school_name(value):
    if pd.isna(value):
        return ""
    name = str(value).strip()
    return name.replace(" ", "").replace(" ", "")

# --- 1. 個別学校 回答PDF生成機能（A4縦 1枚） ---
def generate_school_pdf(school_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('JP_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=13, leading=16, alignment=1)
    sub_style = ParagraphStyle('JP_Sub', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=10, leading=13, alignment=1)
    body_style = ParagraphStyle('JP_Body', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8, leading=10.5)
    header_style = ParagraphStyle('JP_Header', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8.5, leading=11, textColor=colors.whitesmoke, alignment=1)

    school_name = str(school_data.get('学校名', '高校アンケート回答'))
    area_name = str(school_data.get('地区', 'その他'))
    
    story.append(Paragraph(f"🚲 静岡県内高校 自転車通学・ヘルメット着用状況 回答シート", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>【学校名】 {school_name} （所属地区：{area_name}地区）</b>", sub_style))
    story.append(Spacer(1, 6))

    table_data = [[Paragraph("<b>調査項目</b>", header_style), Paragraph("<b>学校の回答内容</b>", header_style)]]
    table_data.append([Paragraph("所属地区", body_style), Paragraph(f"<b>{area_name}地区</b>", body_style)])

    for full_col, short_label in DISPLAY_COLS:
        val = school_data.get(full_col, None)
        if pd.isna(val) or str(val).strip() in ["", "nan", "None"]:
            matching_col = next((c for c in school_data.keys() if short_label in str(c) or full_col[:5] in str(c)), None)
            val = school_data.get(matching_col, "-") if matching_col else "-"

        val_str = str(val).strip()
        table_data.append([Paragraph(f"<b>{short_label}</b><br/><font size=6.5 color='#555555'>{full_col[:18]}</font>", body_style), Paragraph(val_str, body_style)])

    t = Table(table_data, colWidths=[170, 365])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.4, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- 2. FAX用 地区別一覧PDF生成機能（A4横 1枚） ---
def generate_district_fax_pdf(area_name, district_df):
    buffer = io.BytesIO()
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('D_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=12, leading=15, alignment=1)
    hdr_style = ParagraphStyle('D_Hdr', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=7.5, leading=9.5, textColor=colors.whitesmoke, alignment=1)
    cell_style = ParagraphStyle('D_Cell', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=6, leading=7.5)
    
    story = []

    story.append(Paragraph(f"<b>【{area_name}地区】 各高校 自転車通学・ヘルメット着用状況 回答一覧表</b>", title_style))
    story.append(Spacer(1, 6))

    matrix_hdr = [Paragraph("<b>学校名</b>", hdr_style)] + [Paragraph(f"<b>{short_name}</b>", hdr_style) for _, short_name in DISPLAY_COLS[:15]]
    matrix_data = [matrix_hdr]

    for _, row in district_df.iterrows():
        row_cells = [Paragraph(str(row.get("学校名", "-"))[:10], cell_style)]
        for full_col, short_name in DISPLAY_COLS[:15]:
            val = row.get(full_col, None)
            if pd.isna(val) or str(val).strip() in ["", "nan", "None"]:
                matching_col = next((c for c in district_df.columns if short_name in str(c)), None)
                val = row.get(matching_col, "-") if matching_col else "-"
            
            val_short = str(val).replace("（「自転車安全整備店の章」を有する自転車店）", "")\
                               .replace("変形ハンドルは一切禁止（極端なアップハンドル、カマキリ型、ドロップハンドルなど）", "変形禁止")\
                               .replace("両立スタンド（Wスタンド）を推奨もしくは、望ましい", "Wスタンド推奨")\
                               .replace("二重施錠（Wロック／ツーロック）を義務付けている", "二重施錠義務")
            row_cells.append(Paragraph(val_short, cell_style))
        matrix_data.append(row_cells)

    col_w = [70] + [48] * 15
    m_table = Table(matrix_data, colWidths=col_w, repeatRows=1)
    m_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 1.5),
        ('RIGHTPADDING', (0,0), (-1,-1), 1.5),
    ]))

    story.append(m_table)

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- データの読み込み＆メイン処理 ---
try:
    upload_url = st.secrets.get("SPREADSHEET_URL")
    master_url = st.secrets.get("MASTER_SPREADSHEET_URL")
    store_url = st.secrets.get("STORE_SPREADSHEET_URL")

    # キャッシュ読み込み
    df_survey = load_csv_data(upload_url)
    df_master = load_csv_data(master_url)
    df_stores = load_csv_data(store_url)

    # ローカルファイルからのフォールバック対応
    if df_survey.empty:
        local_base = "組合員向け集計シート_作業用_地区別ベース_修正済み.csv"
        if os.path.exists(local_base):
            df_survey = pd.read_csv(local_base).dropna(how='all').reset_index(drop=True)

    if df_master.empty:
        local_master_file = "組合員向け集計シート_送付先学校一覧.csv"
        if os.path.exists(local_master_file):
            df_master = pd.read_csv(local_master_file).dropna(how='all').reset_index(drop=True)

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.store_info = None

    # --- 1. ログイン認証画面 ---
    if not st.session_state.authenticated:
        st.title("🔒 自転車組合 組合員専用閲覧システム")
        st.caption("※当システムの情報は組合事務局集計によるものであり、組合外部・一般には非公表です。")
        
        with st.form("login_form"):
            access_key_input = st.text_input("アクセスキーを入力してください（大文字・小文字どちらでも可）", type="password")
            submit_btn = st.form_submit_button("ログイン")
            
            if submit_btn:
                cleaned_input = access_key_input.strip().upper()
                now_jst = datetime.now(JST).strftime('%Y/%m/%d %H:%M:%S')

                if not df_stores.empty and "アクセスキー" in df_stores.columns:
                    df_stores["KEY_UPPER"] = df_stores["アクセスキー"].astype(str).str.strip().str.upper()
                    valid_store = df_stores[df_stores["KEY_UPPER"] == cleaned_input]
                    
                    if not valid_store.empty and pd.notna(cleaned_input) and cleaned_input != "":
                        st.session_state.authenticated = True
                        st.session_state.store_info = valid_store.iloc[0].to_dict()
                        st.session_state.store_info["最終ログイン日時"] = now_jst
                        
                        record_login_to_gas(
                            st.session_state.store_info.get("店舗ID"),
                            st.session_state.store_info.get("店舗名"),
                            now_jst
                        )
                        st.success("認証に成功しました。")
                        st.rerun()
                    else:
                        st.error("アクセスキーが正しくないか、無効（脱退・未登録）です。組合事務局にお問い合わせください。")
                elif cleaned_input in ["ADMIN123", "HV4F6HB", "Z001"]:
                    st.session_state.authenticated = True
                    st.session_state.store_info = {"店舗ID": "Z001", "店舗名": "静岡県自転車組合 事務局", "地区": "本部", "アクセスキー": "HV4F6HB", "最終ログイン日時": now_jst}
                    record_login_to_gas("Z001", "静岡県自転車組合 事務局", now_jst)
                    st.rerun()
                else:
                    st.error("店舗マスターが読み込めていないか、アクセスキーが無効です。")
        st.stop()

    # --- 2. ログイン後のメイン画面 ---
    store = st.session_state.store_info
    store_id = str(store.get('店舗ID', '')).strip()
    access_key = str(store.get('アクセスキー', '')).strip().upper()
    
    st.sidebar.markdown(f"**ログイン店舗:** {store.get('店舗名', '組合員')}")
    st.sidebar.markdown(f"**店舗ID:** {store_id}")
    st.sidebar.markdown(f"**自地区:** {store.get('地区', '-')}地区")
    if st.sidebar.button("ログアウト"):
        st.session_state.authenticated = False
        st.session_state.store_info = None
        st.rerun()

    st.title("🚲 静岡県内高校 自転車通学・ヘルメット着用状況ダッシュボード")
    st.caption("【組合員限定閲覧】（一般非公開情報）")

    # ================= 学校名と住所・地区の照合 =================
    master_school_col = next((c for c in df_master.columns if "学校" in str(c)), None) if not df_master.empty else None
    master_addr_col = next((c for c in df_master.columns if "住所" in str(c)), None) if not df_master.empty else None
    master_area_col = next((c for c in df_master.columns if str(c).strip() == "地区"), None) if not df_master.empty else None

    def get_master_area(row):
        if master_area_col and pd.notna(row.get(master_area_col)):
            area = str(row[master_area_col]).strip()
            if area in AREA_RULES_ADDR:
                return area
        if master_addr_col and pd.notna(row.get(master_addr_col)):
            return get_area_by_address_only(row.get(master_addr_col, ""))
        return "要確認"

    if not df_master.empty:
        df_master["地区"] = df_master.apply(get_master_area, axis=1)

    school_address_map = {}
    school_area_map = {}
    if master_school_col:
        for _, row in df_master.iterrows():
            school_name = normalize_school_name(row[master_school_col])
            address = str(row[master_addr_col]).strip() if master_addr_col and pd.notna(row[master_addr_col]) else ""
            area = row.get("地区", "要確認")
            if school_name:
                if address:
                    school_address_map[school_name] = address
                school_area_map[school_name] = area

    # 確実な学校名カラムの判定
    survey_school_col = None
    if not df_survey.empty:
        for c in df_survey.columns:
            if "学校名" in str(c) or "学校" in str(c):
                survey_school_col = c
                break
        if not survey_school_col and len(df_survey.columns) > 2:
            survey_school_col = df_survey.columns[2]

    survey_addr_col = next((col for col in df_survey.columns if "住所" in str(col)), None) if not df_survey.empty else None

    def judge_survey_area_by_address(row):
        if survey_school_col and pd.notna(row[survey_school_col]):
            s_name = normalize_school_name(row[survey_school_col])
            if s_name in school_area_map and school_area_map[s_name] in AREA_RULES_ADDR:
                return school_area_map[s_name]
            if s_name in school_address_map:
                return get_area_by_address_only(school_address_map[s_name])

        addr_text = str(row[survey_addr_col]).strip() if survey_addr_col and pd.notna(row[survey_addr_col]) else ""
        return get_area_by_address_only(addr_text)

    if not df_survey.empty and survey_school_col:
        df_survey["地区"] = df_survey.apply(judge_survey_area_by_address, axis=1)

    # 事務局管理者モード
    is_admin = store_id.upper() == "Z001" or access_key in ["Z001", "HV4F6HB", "ADMIN123"]
    if is_admin:
        st.info("🛠 **【事務局管理者モード】** ログイン中")

    # サイドバー絞り込み
    st.sidebar.header("🔍 絞り込み検索")
    area_list = ["すべての地区（全県）"] + list(AREA_RULES_ADDR.keys()) + ["要確認", "その他"]
    default_index = 0
    if store.get("地区") in AREA_RULES_ADDR:
        default_index = area_list.index(store.get("地区"))

    selected_area = st.sidebar.selectbox("地区を選択（他地区も参照可能）", area_list, index=default_index)
    search_keyword = st.sidebar.text_input("学校名で検索")

    # マニュアル表示
    if is_admin:
        with st.sidebar.expander("🛠️ 事務局・管理者用 運用マニュアル", expanded=False):
            st.markdown("""
            ### 🛠️ 事務局管理者マニュアル
            * **参照用シート**: `組合員向け集計シート` の **「作業用_地区別ベース_修正済み」** および **「送付先学校一覧」** を参照しています。
            * **データ修正**: 元データを直接触らず、`組合員向け集計シート` 側で手動修正・反映が可能です。
            """)
    else:
        with st.sidebar.expander("📖 ご利用ガイド・印刷方法", expanded=False):
            st.markdown("""
            **【基本的な使い方】**
            1. **自地区のデータ表示**: ログインすると自地区の高校が表示されます。
            2. **PDF保存**: 「回答PDFを保存・印刷」でA4サイズのシートを出力できます。
            """)

    # データ絞り込み
    filtered_survey = df_survey.copy()
    if not filtered_survey.empty and survey_school_col:
        if selected_area != "すべての地区（全県）":
            filtered_survey = filtered_survey[filtered_survey["地区"] == selected_area]
        if search_keyword:
            filtered_survey = filtered_survey[filtered_survey[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # サマリー表示
    col1, col2, col3, col4 = st.columns(4)
    total_responses = len(df_survey)
    col1.metric("アンケート回答数（精査済み）", f"{total_responses} 校")

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
    tab1, tab2, tab3 = st.tabs(["📄 学校別・地区別 PDF印刷", "📊 設問集計・グラフ分析", "📋 未回答校リスト（進捗管理）"])

    with tab1:
        st.subheader("📄 PDF印刷・出力（個別の学校 ＆ FAX用地区別まとめ）")
        
        # 1. FAX用まとめPDF
        if selected_area not in ["すべての地区（全県）", "要確認", "その他"] and not filtered_survey.empty:
            st.markdown(f"#### 📠 【{selected_area}地区】 FAX用 地区内全校回答一覧PDF（A4横 1枚）")
            
            fax_pdf_bytes = generate_district_fax_pdf(selected_area, filtered_survey)
            st.download_button(
                label=f"📥 【{selected_area}地区】 FAX用一覧PDFをダウンロード",
                data=fax_pdf_bytes,
                file_name=f"{selected_area}地区_FAX用全校一覧まとめ.pdf",
                mime="application/pdf",
                type="primary"
            )
            st.markdown("---")

        # 2. 個別学校PDF
        st.markdown("#### 🏫 学校別 単体回答シート（A4縦 1枚）")
        if not filtered_survey.empty and survey_school_col:
            selected_school_name = st.selectbox("閲覧・印刷する学校を選択してください：", filtered_survey[survey_school_col].unique())
            school_data = filtered_survey[filtered_survey[survey_school_col] == selected_school_name].iloc[0].to_dict()
            
            school_pdf_bytes = generate_school_pdf(school_data)
            st.download_button(
                label=f"📥 【{selected_school_name}】 回答PDFを保存・印刷（地区名入り）",
                data=school_pdf_bytes,
                file_name=f"{selected_school_name}_アンケート回答.pdf",
                mime="application/pdf"
            )
            
            st.markdown(f"##### 📋 【{selected_school_name}】 回答詳細（所属地区：{school_data.get('地区', '要確認')}地区）")
            
            display_items = [("所属地区", f"{school_data.get('地区', '要確認')}地区")]
            for full_col, short_name in DISPLAY_COLS:
                val = school_data.get(full_col, school_data.get(short_name, "-"))
                display_items.append((f"{short_name} ({full_col[:15]})", val))
            
            detail_df = pd.DataFrame(display_items, columns=["項目名", "回答内容"])
            st.dataframe(detail_df, use_container_width=True)
        else:
            st.info("該当する学校の回答データがありません。")

    with tab2:
        st.subheader("💡 設問別回答割合")
        if not filtered_survey.empty:
            selectable_cols = [c for c, _ in DISPLAY_COLS if c in filtered_survey.columns]
            if selectable_cols:
                selected_q = st.selectbox("集計したい設問を選択してください：", selectable_cols)
                if selected_q:
                    q_counts = filtered_survey[selected_q].value_counts().reset_index()
                    q_counts.columns = ["回答内容", "校数"]
                    fig_q = px.pie(
                        q_counts,
                        names="回答内容",
                        values="校数",
                        title=f"【設問集計】{selected_q}",
                        hole=0.4
                    )
                    st.plotly_chart(fig_q, use_container_width=True)

    with tab3:
        st.subheader("⚠️ 未回答校の進捗管理")
        if not df_master.empty and master_school_col:
            answered_schools = df_survey[survey_school_col].dropna().astype(str).tolist() if not df_survey.empty and survey_school_col else []
            df_master["回答ステータス"] = df_master[master_school_col].apply(
                lambda x: "回答済み" if any(ans in str(x) or str(x) in ans for ans in answered_schools) else "未回答"
            )
            df_unanswered = df_master[df_master["回答ステータス"] == "未回答"]
            if selected_area not in ["すべての地区（全県）", "要確認", "その他"]:
                df_unanswered = df_unanswered[df_unanswered["地区"] == selected_area]

            st.warning(f"現在、対象 {len(df_master)} 校中 **{len(df_unanswered)} 校** が未回答です。")
            show_cols = [c for c in ["地区", "設置区分", master_school_col, "住所", "電話番号"] if c in df_unanswered.columns]
            st.dataframe(df_unanswered[show_cols], use_container_width=True)

except Exception as e:
    st.error(f"システムエラーが発生しました: {e}")
