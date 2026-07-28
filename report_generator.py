import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute total page count and add headers/footers.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Bottom footer line
        page_width, page_height = A4
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 40, page_width - 36, 40)
        
        # Footer branding & Page X of Y
        self.drawString(36, 26, "Generated dynamically by IMS Attendance Tracker | Madanapalle Institute of Technology & Science")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(page_width - 36, 26, page_str)
        self.restoreState()


def get_status_info(percentage):
    """
    Returns label and Hex Color based on attendance percentage:
    - Green (>=85%)
    - Blue (70-84%)
    - Orange (60-69%)
    - Red (<60%)
    """
    try:
        val = float(percentage)
    except (ValueError, TypeError):
        val = 0.0

    if val >= 85.0:
        return "Safe (>=85%)", colors.HexColor("#059669"), colors.HexColor("#ECFDF5")
    elif val >= 70.0:
        return "Good (70-84%)", colors.HexColor("#2563EB"), colors.HexColor("#EFF6FF")
    elif val >= 60.0:
        return "Warning (60-69%)", colors.HexColor("#D97706"), colors.HexColor("#FFFBEB")
    else:
        return "Critical (<60%)", colors.HexColor("#DC2626"), colors.HexColor("#FEF2F2")


def generate_pdf_report(student_name, register_number, attendance_data, timestamp_str=None):
    """
    Generates a professional A4 vector PDF report buffer (Attendance_Report.pdf).
    """
    buffer = io.BytesIO()

    if not timestamp_str:
        timestamp_str = datetime.now().strftime("%d %b %Y, %I:%M %p")

    student_name = student_name or "Student"
    register_number = str(register_number or "N/A").upper()

    # Calculate overall stats
    total_attended = 0
    total_conducted = 0
    for item in attendance_data:
        try:
            total_attended += int(item.get("attended", 0))
            total_conducted += int(item.get("total", 0))
        except (ValueError, TypeError):
            pass

    overall_perc = (total_attended / total_conducted * 100.0) if total_conducted > 0 else 0.0
    overall_perc_str = f"{overall_perc:.2f}%"

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A")
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569")
    )

    label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#334155")
    )

    val_style = ParagraphStyle(
        'FieldValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#0F172A")
    )

    tbl_header_style = ParagraphStyle(
        'TblHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white,
        alignment=1 # Centered
    )

    tbl_cell_style = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A")
    )

    tbl_cell_center = ParagraphStyle(
        'TblCellCenter',
        parent=tbl_cell_style,
        alignment=1
    )

    story = []

    # 1. Header with Logo & Institution Title
    logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "logo.png")
    header_data = []
    
    header_text_cell = [
        Paragraph("MADANAPALLE INSTITUTE OF TECHNOLOGY & SCIENCE", title_style),
        Spacer(1, 3),
        Paragraph("Official Student Attendance Report | IMS Attendance Tracker", subtitle_style)
    ]

    if os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=44, height=44)
            header_data.append([img, header_text_cell])
            header_table = Table(header_data, colWidths=[52, 470])
            header_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            story.append(header_table)
        except Exception:
            story.extend(header_text_cell)
    else:
        story.extend(header_text_cell)

    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#6366F1"), spaceBefore=0, spaceAfter=12))

    # 2. Student Info Grid
    info_data = [
        [
            Paragraph("Student Name:", label_style), Paragraph(student_name, val_style),
            Paragraph("Register Number:", label_style), Paragraph(register_number, val_style)
        ],
        [
            Paragraph("Classes Attended:", label_style), Paragraph(str(total_attended), val_style),
            Paragraph("Classes Conducted:", label_style), Paragraph(str(total_conducted), val_style)
        ],
        [
            Paragraph("Generated Date:", label_style), Paragraph(timestamp_str, val_style),
            Paragraph("Total Subjects:", label_style), Paragraph(str(len(attendance_data)), val_style)
        ]
    ]


    info_table = Table(info_data, colWidths=[90, 170, 100, 162])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # 3. Overall Attendance KPI Summary Banner
    overall_status_label, overall_status_color, overall_status_bg = get_status_info(overall_perc)
    
    kpi_title_style = ParagraphStyle('KPITitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#475569"))
    kpi_val_style = ParagraphStyle('KPIVal', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, textColor=overall_status_color)
    kpi_sub_style = ParagraphStyle('KPISub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, textColor=colors.HexColor("#334155"))

    kpi_cell = [
        Paragraph("OVERALL ATTENDANCE SUMMARY", kpi_title_style),
        Spacer(1, 4),
        Paragraph(f"{overall_perc_str}  <font size=10 color='{overall_status_color.hexval()}'>({overall_status_label})</font>", kpi_val_style),
        Spacer(1, 2),
        Paragraph(f"Attended <b>{total_attended}</b> out of <b>{total_conducted}</b> Total Conducted Classes", kpi_sub_style)
    ]

    kpi_table = Table([[kpi_cell]], colWidths=[522])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), overall_status_bg),
        ('BOX', (0, 0), (-1, -1), 1, overall_status_color),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 16))

    # 4. Subject-wise Attendance Table
    table_rows = [
        [
            Paragraph("S.No", tbl_header_style),
            Paragraph("Subject Name / Code", tbl_header_style),
            Paragraph("Attended", tbl_header_style),
            Paragraph("Conducted", tbl_header_style),
            Paragraph("Percentage", tbl_header_style),
            Paragraph("Status", tbl_header_style)
        ]
    ]

    table_style_cmd = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#4F46E5")),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]

    for idx, row in enumerate(attendance_data, start=1):
        subj = str(row.get("subject", "N/A"))
        att = str(row.get("attended", "0"))
        tot = str(row.get("total", "0"))
        perc_val = row.get("percentage", "0.0")
        
        try:
            perc_num = float(str(perc_val).replace("%", "").strip())
        except (ValueError, TypeError):
            perc_num = 0.0

        status_text, status_clr, status_bg = get_status_info(perc_num)

        # Status paragraph style for table
        status_cell_style = ParagraphStyle(
            f'StatusCell_{idx}',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=status_clr,
            alignment=1
        )

        table_rows.append([
            Paragraph(str(idx), tbl_cell_center),
            Paragraph(subj, tbl_cell_style),
            Paragraph(att, tbl_cell_center),
            Paragraph(tot, tbl_cell_center),
            Paragraph(f"{perc_num:.1f}%", tbl_cell_center),
            Paragraph(status_text, status_cell_style)
        ])

        # Zebra striping
        if idx % 2 == 0:
            table_style_cmd.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#F8FAFC")))

    # Col Widths: Total 522 pt
    subj_table = Table(table_rows, colWidths=[32, 230, 60, 65, 65, 70])
    subj_table.setStyle(TableStyle(table_style_cmd))
    story.append(subj_table)

    # Build PDF using NumberedCanvas
    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_txt_report(student_name, register_number, attendance_data, timestamp_str=None):
    """
    Generates a clean, plain-text attendance report (Attendance_Report.txt).
    """
    if not timestamp_str:
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    student_name = student_name or "Student"
    register_number = str(register_number or "N/A").upper()

    total_attended = 0
    total_conducted = 0
    for item in attendance_data:
        try:
            total_attended += int(item.get("attended", 0))
            total_conducted += int(item.get("total", 0))
        except (ValueError, TypeError):
            pass

    overall_perc = (total_attended / total_conducted * 100.0) if total_conducted > 0 else 0.0

    lines = []
    lines.append("=========================================================================")
    lines.append("        MADANAPALLE INSTITUTE OF TECHNOLOGY & SCIENCE (MITS)")
    lines.append("                     IMS ATTENDANCE REPORT")
    lines.append("=========================================================================")
    lines.append("")
    lines.append(f" Student Name          : {student_name}")
    lines.append(f" Register Number       : {register_number}")
    lines.append(f" Generated Date & Time : {timestamp_str}")
    lines.append("")
    lines.append("-------------------------------------------------------------------------")
    lines.append(" OVERALL SUMMARY")
    lines.append("-------------------------------------------------------------------------")
    lines.append(f" Overall Attendance %  : {overall_perc:.2f}%")
    lines.append(f" Total Classes Attended: {total_attended}")
    lines.append(f" Total Classes Conducted: {total_conducted}")
    lines.append("")
    lines.append("-------------------------------------------------------------------------")
    lines.append(" SUBJECT-WISE ATTENDANCE BREAKDOWN")
    lines.append("-------------------------------------------------------------------------")
    lines.append(f" {'S.No':<5} | {'Subject Name / Code':<32} | {'Attended':<8} | {'Total':<6} | {'Perc %':<7} | Status")
    lines.append("-------------------------------------------------------------------------")

    for idx, row in enumerate(attendance_data, start=1):
        subj = str(row.get("subject", "N/A"))
        if len(subj) > 32:
            subj = subj[:29] + "..."
        att = str(row.get("attended", "0"))
        tot = str(row.get("total", "0"))
        perc_val = row.get("percentage", "0.0")
        try:
            perc_num = float(str(perc_val).replace("%", "").strip())
        except (ValueError, TypeError):
            perc_num = 0.0

        if perc_num >= 85.0:
            status = "Safe"
        elif perc_num >= 70.0:
            status = "Good"
        elif perc_num >= 60.0:
            status = "Warning"
        else:
            status = "Critical"

        lines.append(f" {idx:<5} | {subj:<32} | {att:<8} | {tot:<6} | {perc_num:>5.1f}% | {status}")

    lines.append("-------------------------------------------------------------------------")
    lines.append("")
    lines.append(" Color-Coded Status Legend:")
    lines.append("   - Safe     : >= 85%")
    lines.append("   - Good     : 70% - 84%")
    lines.append("   - Warning  : 60% - 69%")
    lines.append("   - Critical : < 60%")
    lines.append("")
    lines.append("=========================================================================")
    lines.append(" Generated automatically by MITS IMS Attendance Tracker.")
    lines.append("=========================================================================")

    return "\n".join(lines).encode("utf-8")
