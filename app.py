import streamlit as st
import pandas as pd
import plotly.express as px
import io
import os
import requests
from datetime import datetime, timezone, timedelta

# 日本時間（JST: UTC+9）の定義
JST = timezone(timedelta(hours=9))

# ReportLab関連ライブラリ（日本語フォント設定・レイアウト用）
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# 日本語CIDフォントの登録（ReportLab標準組み込み）
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

EXCLUDE_KEYS = [
    "ご回答者様のお名前（役職・氏名）", "役職", "役職２",
    "ご連絡先（TEL）", "メールアドレス",
    "タイムスタンプ", "データの最終確認日"
]

def record_login_to_gas(store_id, store_name, timestamp):
    """Google Apps Scriptへログインログを自動送信（アクセスログ追記＋マスター更新）"""
    log_api_url = st.secrets.get("LOG_API_URL")
    if log_api_url:
        try:
            payload = {
                "store_id": str(store_id).strip(),
                "store_name": str(store_name).strip(),
                "timestamp": str(timestamp)
            }
            requests.post(log_api_url, json=payload, timeout=3)
        except Exception:
            pass  # 通信エラー時もユーザー画面のログイン動作自体は阻害しない

def get_area_by_address_only(address_text):
    """学校住所から所属地区を判定する。未判定は要確認。"""
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
    """学校名の前後の空白、全角・半角スペースを除去して正規化"""
    if pd.isna(value):
        return ""
    name = str(value).strip()
    name = name.replace(" ", "").replace(" ", "")
    return name

# --- 1. 個別学校 回答PDF生成機能 ---
def generate_school_pdf(school_data):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('JP_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=14, leading=18, alignment=1)
    sub_style = ParagraphStyle('JP_Sub', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=11, leading=15, alignment=1)
    body_style = ParagraphStyle('JP_Body', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8, leading=11)
    header_style = ParagraphStyle('JP_Header', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8, leading=11, textColor=colors.whitesmoke)

    school_name = str(school_data.get('学校名', '高校アンケート回答'))
    area_name = str(school_data.get('地区', 'その他'))
    
    story.append(Paragraph(f"🚲 静岡県内高校 自転車通学・ヘルメット着用状況 回答シート", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>【学校名】 {school_name} （地区：{area_name}地区）</b>", sub_style))
    story.append(Spacer(1, 8))

    table_data = [[Paragraph("<b>項目 / 設問</b>", header_style), Paragraph("<b>回答内容</b>", header_style)]]
    table_data.append([Paragraph("所属地区（住所より自動判定）", body_style), Paragraph(f"<b>{area_name}地区</b>", body_style)])

    for key, val in school_data.items():
        if key == "地区" or any(ex in str(key) for ex in EXCLUDE_KEYS) or pd.isna(val):
            continue
        q_text = Paragraph(str(key), body_style)
        a_text = Paragraph(str(val), body_style)
        table_data.append([q_text, a_text])

    t = Table(table_data, colWidths=[190, 330])
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

# --- 2. FAX用 地区別2枚まとめPDF生成機能 ---
def generate_district_fax_pdf(area_name, district_df, total_master_count):
    buffer = io.BytesIO()
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('D_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=14, leading=18, alignment=1)
    subtitle_style = ParagraphStyle('D_SubTitle', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=10, leading=14, alignment=1)
    body_style = ParagraphStyle('D_Body', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8.5, leading=12)
    hdr_style = ParagraphStyle('D_Hdr', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8, leading=10, textColor=colors.whitesmoke, alignment=1)
    cell_style = ParagraphStyle('D_Cell', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=6.5, leading=8.5)
    
    story = []

    doc_p1 = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    
    story.append(Paragraph(f"🚲 【組合員限定・非公表】 {area_name}地区 高校自転車通学・ヘルメット着用状況", title_style))
    story.append(Paragraph(f"（FAX送信用 地区集計サマリー）", subtitle_style))
    story.append(Spacer(1, 15))

    ans_count = len(district_df)
    rate_str = f"{int((ans_count/total_master_count)*100)}%" if total_master_count > 0 else "-"
    summary_text = f"<b>■ {area_name}地区の回答状況</b><br/>" \
                   f"・地区内対象高校数：{total_master_count} 校<br/>" \
                   f"・回答済み高校数 ：{ans_count} 校（回答率: {rate_str}）<br/>"
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>■ 主要設問の地区内回答傾向</b>", body_style))
    story.append(Spacer(1, 5))

    summary_table_data = [[Paragraph("<b>集計設問</b>", hdr_style), Paragraph("<b>地区内での主な傾向・回答内訳</b>", hdr_style)]]
    
    key_qs = [
        ("Q1. 自転車通学の許可", "Q1"),
        ("Q3. 通学許可基準の有無", "Q3"),
        ("Q5. 点検自転車店の指定", "Q5"),
        ("Q18-1. ヘルメット義務化への対応", "Q18-1"),
        ("Q19. TSマーク・保険の扱い", "Q19")
    ]

    for label, q_code in key_qs:
        matching_col = next((c for c in district_df.columns if q_code in c), None)
        if matching_col and not district_df.empty:
            vc = district_df[matching_col].value_counts()
            trend_str = " / ".join([f"{k}: {v}校" for k, v in vc.items()])
        else:
            trend_str = "回答データなし"
        summary_table_data.append([Paragraph(label, body_style), Paragraph(trend_str, body_style)])

    st_table = Table(summary_table_data, colWidths=[180, 340])
    st_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(st_table)
    
    story.append(PageBreak())

    target_q_codes = [
        ("学校名", "学校"), ("地区", "地区"), ("Q1", "Q1."), ("Q2", "Q2."), ("Q3", "Q3."),
        ("Q10", "Q10."), ("Q11", "Q11."), ("Q12", "Q12."), ("Q13", "Q13."),
        ("Q14", "Q14."), ("Q16", "Q16."), ("Q18-1", "Q18-1"), ("Q18-2", "Q18-2"),
        ("Q18-3", "Q18-3"), ("Q19", "Q19")
    ]

    matrix_hdr = [Paragraph(f"<b>{title}</b>", hdr_style) for title, _ in target_q_codes]
    matrix_data = [matrix_hdr]

    for _, row in district_df.iterrows():
        row_cells = []
        for title, code in target_q_codes:
            if title == "地区":
                val = str(row.get("地区", "その他"))
            else:
                col_name = next((c for c in district_df.columns if code in c), None)
                val = str(row[col_name]) if col_name and pd.notna(row[col_name]) else "-"
            
            val_short = val.replace("（「自転車安全整備店の章」を有する自転車店）", "")\
                           .replace("変形ハンドルは一切禁止（極端なアップハンドル、カマキリ型、ドロップハンドルなど）", "変形禁止")\
                           .replace("両立スタンド（Wスタンド）を推奨もしくは、望ましい", "Wスタンド推奨")\
                           .replace("二重施錠（Wロック／ツーロック）を義務付けている", "二重施錠義務")
            
            row_cells.append(Paragraph(val_short, cell_style))
        matrix_data.append(row_cells)

    col_w = [75, 45] + [52] * 13
    m_table = Table(matrix_data, colWidths=col_w, repeatRows=1)
    m_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
    ]))

    story.append(Paragraph(f"<b>【{area_name}地区】 各高校の回答状況一覧（13項目）</b>", title_style))
    story.append(Spacer(1, 8))
    story.append(m_table)

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- データの読み込み＆メイン処理 ---
try:
    upload_url = st.secrets.get("SPREADSHEET_URL")
    raw_url = st.secrets.get("RAW_SPREADSHEET_URL")
    master_url = st.secrets.get("MASTER_SPREADSHEET_URL")
    store_url = st.secrets.get("STORE_SPREADSHEET_URL")

    df_survey = pd.DataFrame()
    df_raw = pd.DataFrame()
    df_master = pd.DataFrame()
    df_stores = pd.DataFrame()

    if upload_url:
        try:
            df_survey = pd.read_csv(upload_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass

    if raw_url:
        try:
            df_raw = pd.read_csv(raw_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass

    if master_url:
        try:
            df_master = pd.read_csv(master_url).dropna(how='all').reset_index(drop=True)
        except Exception:
            pass
    if df_master.empty:
        local_master_file = "高校自転車通学_ヘルメットアンケート集計閲覧システム_システ_送付先学校一覧.csv"
        if os.path.exists(local_master_file):
            try:
                df_master = pd.read_csv(local_master_file).dropna(how='all').reset_index(drop=True)
            except Exception:
                pass

    store_load_error = None
    if not store_url:
        store_load_error = "STORE_SPREADSHEET_URL が Secrets に設定されていません。"
    else:
        try:
            df_stores = pd.read_csv(store_url).dropna(how="all")
            df_stores.columns = [str(c).strip().lstrip("\ufeff") for c in df_stores.columns]
            df_stores = df_stores.reset_index(drop=True)
            if df_stores.empty:
                store_load_error = "CSVは取得できましたが、データ行がありません。"
        except Exception as e:
            store_load_error = f"URL読み込みエラー: {type(e).__name__}: {e}"
            df_stores = pd.DataFrame()

    if df_stores.empty:
        local_store_file = "高校自転車通学_ヘルメットアンケート集計閲覧システム_システ_店舗マスター.csv"
        if os.path.exists(local_store_file):
            try:
                df_stores = pd.read_csv(local_store_file).dropna(how="all")
                df_stores.columns = [str(c).strip().lstrip("\ufeff") for c in df_stores.columns]
                df_stores = df_stores.reset_index(drop=True)
            except Exception as e:
                store_load_error = f"ローカルCSV読み込みエラー: {type(e).__name__}: {e}"

    if not df_master.empty:
        df_master.columns = [str(c).strip().lstrip("\ufeff") for c in df_master.columns]
    if not df_survey.empty:
        df_survey.columns = [str(c).strip().lstrip("\ufeff") for c in df_survey.columns]

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
                        
                        # GASを介してアクセスログの積載と回数更新を実行
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

    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None) or (df_survey.columns[1] if not df_survey.empty else None)
    survey_addr_col = next((col for col in df_survey.columns if "住所" in str(col)), None) if not df_survey.empty else None

    def judge_survey_area_by_address(row):
        if survey_school_col and pd.notna(row[survey_school_col]):
            s_name = normalize_school_name(row[survey_school_col])
            
            if s_name in school_area_map and school_area_map[s_name] in AREA_RULES_ADDR:
                return school_area_map[s_name]
            
            if s_name in school_address_map:
                return get_area_by_address_only(school_address_map[s_name])
            
            matches = [m_addr for m_name, m_addr in school_address_map.items() if s_name in m_name or m_name in s_name]
            if len(matches) == 1:
                return get_area_by_address_only(matches[0])

        addr_text = str(row[survey_addr_col]).strip() if survey_addr_col and pd.notna(row[survey_addr_col]) else ""
        return get_area_by_address_only(addr_text)

    if not df_survey.empty and survey_school_col:
        df_survey["地区"] = df_survey.apply(judge_survey_area_by_address, axis=1)

    # ================= 事務局（Z001）専用 管理モード・警告 ＆ セキュリティ監視 =================
    is_admin = store_id.upper() == "Z001" or access_key in ["Z001", "HV4F6HB", "ADMIN123"]
    if is_admin:
        st.info("🛠 **【事務局管理者モード】** ログイン中")
        
        # 年1回のアクセスキー更新案内メッセージ
        st.warning(
            "🔑 **【セキュリティ運用案内】**\n\n"
            "セキュリティ維持のため、**年に1回（新年度開始時など）** アクセスキーの一括再発行・交換を推奨しています。\n\n"
            "※再発行は Google スプレッドシートの Apps Script 内 `generateNewAccessKeys` を手動実行することで一括更新できます。",
            icon="💡"
        )
        
        # 1. 事務局自身のアクセス履歴表示（補正処理付き）
        if not df_stores.empty:
            z001_row = df_stores[
                df_stores["店舗ID"].astype(str).str.upper().str.contains("Z001") | 
                df_stores["アクセスキー"].astype(str).str.upper().str.contains("HV4F6HB")
            ]
            if not z001_row.empty:
                z_cnt_raw = z001_row.iloc[0].get("ログイン回数", None)
                z_time_raw = z001_row.iloc[0].get("最終ログイン日時", None)
                
                z_cnt = "0" if pd.isna(z_cnt_raw) or str(z_cnt_raw).lower() in ["nan", "none", ""] else str(z_cnt_raw).replace(".0", "")
                z_time = st.session_state.store_info.get("最終ログイン日時", "未ログイン") if pd.isna(z_time_raw) or str(z_time_raw).lower() in ["nan", "none", ""] else str(z_time_raw)
                
                st.caption(f"🏢 **事務局（Z001）アクセス履歴**: 累計ログイン回数 **{z_cnt} 回** ｜ 最終ログイン日時: **{z_time}**")

        # 2. 精査漏れ警告
        if not df_raw.empty and not df_survey.empty:
            raw_school_col = next((c for c in df_raw.columns if "学校" in str(c)), None)
            uploaded_school_col = next((c for c in df_survey.columns if "学校" in str(c)), None)
            
            if raw_school_col and uploaded_school_col:
                raw_schools = set(df_raw[raw_school_col].dropna().astype(str).str.strip().unique())
                uploaded_schools = set(df_survey[uploaded_school_col].dropna().astype(str).str.strip().unique())
                
                unprocessed = list(raw_schools - uploaded_schools)
                
                if unprocessed:
                    st.warning(
                        f"🚨 **【精査・移動漏れ警告】** 「アンケート集計」シートに回答が届いていますが、\n\nまだ「アップロード用」シートへ反映されていない学校が **{len(unprocessed)} 件** あります！\n\n"
                        f"**未反映の学校:** {', '.join(unprocessed)}",
                        icon="⚠️"
                    )
                else:
                    st.success("✅ すべての回答が精査済みです（「アップロード用」シートに全件反映完了）。")

        # 3. 店舗アクセス状況ログ一覧（None/NaNの全件補正表示）
        with st.expander("📊 全店舗のアクセスログ・ログイン履歴一覧", expanded=True):
            if df_stores.empty:
                st.error("店舗マスターが空です。")
                if store_load_error:
                    st.code(store_load_error)
            else:
                st.caption(f"店舗マスター読み込み成功：{len(df_stores)} 件")
                
                # 専門家指摘の None / NaN 自動補正処理
                df_display_stores = df_stores.copy()
                if "ログイン回数" in df_display_stores.columns:
                    df_display_stores["ログイン回数"] = (
                        pd.to_numeric(df_display_stores["ログイン回数"], errors="coerce")
                        .fillna(0)
                        .astype(int)
                    )
                if "最終ログイン日時" in df_display_stores.columns:
                    df_display_stores["最終ログイン日時"] = (
                        df_display_stores["最終ログイン日時"]
                        .fillna("未ログイン")
                        .astype(str)
                        .replace({"nan": "未ログイン", "None": "未ログイン", "": "未ログイン"})
                    )

                show_cols = [c for c in ["店舗ID", "店舗名", "地区", "ログイン回数", "最終ログイン日時"] if c in df_display_stores.columns]
                missing_cols = [c for c in ["店舗ID", "店舗名", "地区", "ログイン回数", "最終ログイン日時"] if c not in df_display_stores.columns]
                
                if missing_cols:
                    st.warning("店舗マスターに次の列が見つかりません：「" + "」、「".join(missing_cols) + "」")
                
                if show_cols:
                    st.dataframe(df_display_stores[show_cols], use_container_width=True, hide_index=True)
                else:
                    st.error("表示できる列がありません。店舗マスターの1行目が正しい列名になっているか確認してください。")

        st.markdown("---")

    # サイドバー絞り込み
    st.sidebar.header("🔍 絞り込み検索")
    area_list = ["すべての地区（全県）"] + list(AREA_RULES_ADDR.keys()) + ["要確認", "その他"]
    default_index = 0
    if store.get("地区") in AREA_RULES_ADDR:
        default_index = area_list.index(store.get("地区"))

    selected_area = st.sidebar.selectbox("地区を選択（他地区も参照可能）", area_list, index=default_index)
    search_keyword = st.sidebar.text_input("学校名で検索")

    # --------------------------------------------------
    # 📖 検索欄すぐ直下の組合員向けマニュアル（アコーディオン表示）
    # --------------------------------------------------
    with st.sidebar.expander("📖 ご利用ガイド・印刷方法"):
        st.markdown("""
        **【基本的な使い方】**
        1. **自地区のデータ表示**
           ログインすると、まず自店舗の地区の高校データが表示されます。
        2. **他地区の高校を探す**
           「地区を選択」で地区を切り替えるか、「学校名で検索」に学校名を入力してください。
        3. **PDFの保存・印刷（A4縦1枚）**
           画面中央の **「〇〇高校 回答PDFを保存・印刷」** ボタンを押すと、A4・1枚に整えられたPDFファイルがダウンロードされます。
        """)

    # フィルタリング
    filtered_survey = df_survey.copy()
    if not filtered_survey.empty and survey_school_col:
        if selected_area != "すべての地区（全県）":
            filtered_survey = filtered_survey[filtered_survey["地区"] == selected_area]
        if search_keyword:
            filtered_survey = filtered_survey[filtered_survey[survey_school_col].astype(str).str.contains(search_keyword, na=False)]

    # 上部サマリーカード
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
        st.subheader("📄 PDF印刷・出力（個別の学校 ＆ FAX用地区別2枚まとめ）")
        
        # 1. 地区別まとめFAX PDFダウンロード
        if selected_area not in ["すべての地区（全県）", "要確認", "その他"] and not filtered_survey.empty:
            st.markdown(f"#### 📠 【{selected_area}地区】 FAX用 地区集計・一覧2枚まとめPDF")
            st.caption("※1枚目：地区集計サマリー / 2枚目：地区内全校の13項目一覧表（A4横）")
            
            if not df_master.empty:
                district_master_count = len(df_master[df_master["地区"] == selected_area])
            else:
                district_master_count = len(filtered_survey)

            fax_pdf_bytes = generate_district_fax_pdf(selected_area, filtered_survey, district_master_count)
            st.download_button(
                label=f"📥 【{selected_area}地区】 FAX用まとめPDF（2枚）をダウンロード",
                data=fax_pdf_bytes,
                file_name=f"{selected_area}地区_FAX用集計・一覧まとめ.pdf",
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
            display_items = [("所属地区（住所より判定）", f"{school_data.get('地区', '要確認')}地区")]
            for k, v in school_data.items():
                if k != "地区" and not any(ex in str(k) for ex in EXCLUDE_KEYS):
                    display_items.append((k, v))
            
            detail_df = pd.DataFrame(display_items, columns=["項目・設問", "回答内容"])
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
            answered_schools = df_survey[survey_school_col].dropna().astype(str).tolist() if not df_survey.empty and survey_school_col else []
            
            df_master["回答ステータス"] = df_master[master_school_col].apply(
                lambda x: "回答済み" if any(ans in str(x) or str(x) in ans for ans in answered_schools) else "未回答"
            )
            df_unanswered = df_master[df_master["回答ステータス"] == "未回答"]
            
            if selected_area not in ["すべての地区（全県）", "要確認", "その他"]:
                df_unanswered = df_unanswered[df_unanswered["地区"] == selected_area]

            st.warning(f"現在、対象 {len(df_master)} 校中 **{len(df_unanswered)} 校** が未回答です。")
            show_cols = [c for c in ["地区", "設置区分", master_school_col, "住所", "電話番号", "メールアドレス / 連絡先状況"] if c in df_unanswered.columns]
            st.dataframe(df_unanswered[show_cols], use_container_width=True)
        else:
            st.info("💡 送付先マスターが連携されると、未回答校リストが自動表示されます。")

except Exception as e:
    st.error(f"システムエラーが発生しました: {e}")
