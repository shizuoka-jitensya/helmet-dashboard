# --- 1. 個別学校 回答PDF生成機能（A4縦 1枚・完全フィット版） ---
def generate_school_pdf(school_data):
    buffer = io.BytesIO()
    # 上下左右の余白を最小限（15pt）に設定
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=15, leftMargin=15, topMargin=15, bottomMargin=15
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('JP_Title', parent=styles['Heading1'], fontName=JAPANESE_FONT, fontSize=11, leading=13, alignment=1)
    sub_style = ParagraphStyle('JP_Sub', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=9, leading=11, alignment=1)
    lbl_style = ParagraphStyle('JP_Lbl', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=7, leading=8.5)
    body_style = ParagraphStyle('JP_Body', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=7, leading=8.5)
    header_style = ParagraphStyle('JP_Header', parent=styles['Normal'], fontName=JAPANESE_FONT, fontSize=7.5, leading=9.5, textColor=colors.whitesmoke, alignment=1)

    school_name = str(school_data.get('学校名', '高校アンケート回答'))
    area_name = str(school_data.get('地区', 'その他'))
    
    story.append(Paragraph(f"🚲 静岡県内高校 自転車通学・ヘルメット着用状況 回答シート", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(f"<b>【学校名】 {school_name} （所属地区：{area_name}地区）</b>", sub_style))
    story.append(Spacer(1, 3))

    table_data = [[Paragraph("<b>調査項目</b>", header_style), Paragraph("<b>学校の回答内容</b>", header_style)]]
    table_data.append([Paragraph("<b>所属地区</b>", lbl_style), Paragraph(f"<b>{area_name}地区</b>", body_style)])

    for full_col, short_label in DISPLAY_COLS:
        val = school_data.get(full_col, None)
        if pd.isna(val) or str(val).strip() in ["", "nan", "None"]:
            matching_col = next((c for c in school_data.keys() if short_label in str(c) or full_col[:5] in str(c)), None)
            val = school_data.get(matching_col, "-") if matching_col else "-"

        val_str = str(val).strip()
        table_data.append([
            Paragraph(f"<b>{short_label}</b>", lbl_style),
            Paragraph(val_str, body_style)
        ])

    # 幅合計: 565pt (A4幅595pt - 左右余白30pt)
    t = Table(table_data, colWidths=[130, 435])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.3, colors.grey),
        ('TOPPADDING', (0,0), (-1,-1), 1.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.2),
        ('LEFTPADDING', (0,0), (-1,-1), 3),
        ('RIGHTPADDING', (0,0), (-1,-1), 3),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer
