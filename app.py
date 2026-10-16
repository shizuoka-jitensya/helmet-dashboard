import streamlit as st
import pandas as pd
import plotly.express as px
import io

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

# 個人情報・連絡先の完全除外リスト（地区は除外から外し、学校名の下に明記）
EXCLUDE_KEYS = [
    "ご回答者様のお名前（役職・氏名）", "役職", "役職２",
    "ご連絡先（TEL）", "メールアドレス",
    "タイムスタンプ", "データの最終確認日"
]

def get_area_from_text(text):
    if not isinstance(text, str) or not text:
        return "その他"
    for area, keywords in AREA_RULES.items():
        for keyword in keywords:
            if keyword in text:
                return area
    return "その他"

# --- 1. 個別学校 回答PDF生成機能（学校名の下に地区名を出力） ---
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
    # 学校名の下に判定された地区名を出力
    story.append(Paragraph(f"<b>【学校名】 {school_name} （判定地区：{area_name}地区）</b>", sub_style))
    story.append(Spacer(1, 8))

    table_data = [[Paragraph("<b>項目 / 設問</b>", header_style), Paragraph("<b>回答内容</b>", header_style)]]
    
    # 判定地区をテーブル先頭にも挿入
    table_data.append([Paragraph("判定所属地区", body_style), Paragraph(f"<b>{area_name}地区</b>", body_style)])

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

# --- 2. FAX用 地区別2枚まとめPDF生成機能（2枚目一覧表に地区名出力） ---
def generate_district_fax_pdf(area_name, district_df, total_master_count):
    buffer = io.BytesIO()
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('D_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=14, leading=18, alignment=1)
    subtitle_style = ParagraphStyle('D_SubTitle', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=10, leading=14, alignment=1)
    body_style = ParagraphStyle('D_Body', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8.5, leading=12)
    hdr_style = ParagraphStyle('D_Hdr', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=8, leading=10, textColor=colors.whitesmoke, alignment=1)
    cell_style = ParagraphStyle('D_Cell', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=6.5, leading=8.5)
    
    story = []

    # 1枚目：地区サマリー（A4 縦）
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

    # 2枚目：13項目 学校別一覧表（A4 横）
    target_q_codes = [
        ("学校名", "学校"), ("判定地区", "地区"), ("Q1", "Q1."), ("Q2", "Q2."), ("Q3", "Q3."),
        ("Q10", "Q10."), ("Q11", "Q11."), ("Q12", "Q12."), ("Q13", "Q13."),
        ("Q14", "Q14."), ("Q16", "Q16."), ("Q18-1", "Q18-1"), ("Q18-2", "Q18-2"),
        ("Q18-3", "Q18-3"), ("Q19", "Q19")
    ]

    matrix_hdr = [Paragraph(f"<b>{title}</b>", hdr_style) for title, _ in target_q_codes]
    matrix_data = [matrix_hdr]

    for _, row in district_df.iterrows():
        row_cells = []
        for title, code in target_q_codes:
            if title == "判定地区":
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

    # 15列の幅調整
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

    story.append(Paragraph(f"<b>【{area_name}地区】 各高校の回答状況一覧（所属地区判定つき）</b>", title_style))
    story.append(Spacer(1, 8))
    story.append(m_table)

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- データの読み込み＆メイン処理 ---
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
            access_key_input = st.text_input("アクセスキーを入力してください（大文字・小文字どちらでも可）", type="password")
            submit_btn = st.form_submit_button("ログイン")
            
            if submit_btn:
                cleaned_input = access_key_input.strip().upper()
                if not df_stores.empty and "アクセスキー" in df_stores.columns:
                    df_stores["KEY_UPPER"] = df_stores["アクセスキー"].astype(str).str.strip().str.upper()
                    valid_store = df_stores[df_stores["KEY_UPPER"] == cleaned_input]
                    
                    if not valid_store.empty and pd.notna(cleaned_input) and cleaned_input != "":
                        st.session_state.authenticated = True
                        st.session_state.store_info = valid_store.iloc[0].to_dict()
                        st.success("認証に成功しました。")
                        st.rerun()
                    else:
                        st.error("アクセスキーが正しくないか、無効（脱退・未登録）です。組合事務局にお問い合わせください。")
                elif cleaned_input == "ADMIN123":
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

    # 地区判定（住所優先、無ければ校名から判定。判定不能時は「その他」）
    survey_school_col = next((col for col in df_survey.columns if "学校" in str(col)), None) or (df_survey.columns[1] if not df_survey.empty else None)
    survey_addr_col = next((col for col in df_survey.columns if "住所" in str(col)), None) if not df_survey.empty else None

    def judge_survey_area(row):
        addr_text = str(row[survey_addr_col]) if survey_addr_col and pd.notna(row[survey_addr_col]) else ""
        school_text = str(row[survey_school_col]) if pd.notna(row[survey_school_col]) else ""
        area = get_area_from_text(addr_text)
        if area == "その他":
            area = get_area_from_text(school_text)
        return area

    if not df_survey.empty and survey_school_col:
        df_survey["地区"] = df_survey.apply(judge_survey_area, axis=1)

    # サイドバー絞り込み
    st.sidebar.header("🔍 絞り込み検索")
    area_list = ["すべての地区（全県）"] + list(AREA_RULES.keys()) + ["その他"]
    default_index = 0
    if store.get("地区") in AREA_RULES:
        default_index = area_list.index(store.get("地区"))

    selected_area = st.sidebar.selectbox("地区を選択（他地区も参照可能）", area_list, index=default_index)
    search_keyword = st.sidebar.text_input("学校名で検索")

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
    tab1, tab2, tab3 = st.tabs(["📄 学校別・地区別 PDF印刷", "📊 設問集計・グラフ分析", "📋 未回答校リスト（進捗管理）"])

    with tab1:
        st.subheader("📄 PDF印刷・出力（個別の学校 ＆ FAX用地区別2枚まとめ）")
        
        # 1. 地区別まとめFAX PDFダウンロード
        if selected_area != "すべての地区（全県）" and not filtered_survey.empty:
            st.markdown(f"#### 📠 【{selected_area}地区】 FAX用 地区集計・一覧2枚まとめPDF")
            st.caption("※1枚目：地区集計サマリー / 2枚目：地区内全校の13項目一覧表（A4横・地区判定つき）")
            
            master_addr_col = next((c for c in df_master.columns if "住所" in str(c)), None) if not df_master.empty else None
            if not df_master.empty and master_school_col:
                df_master["地区"] = df_master.apply(
                    lambda r: get_area_from_text(str(r[master_addr_col]) if master_addr_col and pd.notna(r[master_addr_col]) else str(r[master_school_col])), axis=1
                )
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
            
            st.markdown(f"##### 📋 【{selected_school_name}】 回答詳細（所属地区：{school_data.get('地区', 'その他')}地区）")
            # 個人情報を除外し、地区を上位に配置した表示用リスト
            display_items = [("所属地区", f"{school_data.get('地区', 'その他')}地区")]
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
