"""
Report Generation Engine
Generates downloadable CSV and professional PDF Dossiers for individual students
and class/department-level attendance risk summaries.
"""

import io
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime


def generate_student_csv(student_summary: Dict[str, Any], risk_data: Dict[str, Any], subject_df: pd.DataFrame) -> bytes:
    """Generates a comprehensive CSV text export for a student."""
    output = io.StringIO()
    output.write("ACADEMIC ATTENDANCE PATTERN & RISK REPORT (STUDENT 360)\n")
    output.write(f"Generated On,{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    output.write("STUDENT PROFILE\n")
    output.write(f"Student ID,{student_summary.get('student_id','')}\n")
    output.write(f"Register Number,{student_summary.get('register_number','')}\n")
    output.write(f"Name,{student_summary.get('student_name','')}\n")
    output.write(f"Department,{student_summary.get('department','')}\n")
    output.write(f"Year,{student_summary.get('year','')}\n")
    output.write(f"Section,{student_summary.get('section','')}\n\n")

    output.write("ATTENDANCE & RISK METRICS\n")
    output.write(f"Overall Attendance Percentage,{student_summary.get('attendance_pct', 0.0)}%\n")
    output.write(f"Risk Score (0-100),{risk_data.get('risk_score', 0)}/100\n")
    output.write(f"Risk Level,{risk_data.get('risk_level', 'LOW')}\n")
    output.write(f"Trend Direction,{risk_data.get('trend_direction', 'Stable')}\n")
    output.write(f"Current Absence Streak,{risk_data.get('streaks', {}).get('current_absence_streak', 0)} classes\n")
    output.write(f"Consecutive Classes Needed for 75%,{risk_data.get('required_consecutive', 0)}\n\n")

    output.write("RISK SCORE 7-FACTOR BREAKDOWN\n")
    for factor, score in risk_data.get("factor_breakdown", {}).items():
        output.write(f"{factor},{score}\n")
    output.write("\n")

    output.write("EXPLAINABLE REASONS\n")
    for reason in risk_data.get("reasons", []):
        output.write(f"- \"{reason}\"\n")
    output.write("\n")

    output.write("RECOMMENDED FACULTY ACTIONS\n")
    for rec in risk_data.get("recommendations", []):
        output.write(f"- \"{rec}\"\n")
    output.write("\n")

    output.write("SUBJECT-WISE PERFORMANCE\n")
    if not subject_df.empty:
        subject_df.to_csv(output, index=False)

    return output.getvalue().encode("utf-8")


def generate_class_csv(cohort_risk_df: pd.DataFrame) -> bytes:
    """Exports the entire cohort risk registry to CSV."""
    output = io.StringIO()
    cohort_risk_df.to_csv(output, index=False)
    return output.getvalue().encode("utf-8")


def generate_student_pdf(student_summary: Dict[str, Any], risk_data: Dict[str, Any], subject_df: pd.DataFrame) -> bytes:
    """
    Generates a professional academic PDF dossier for a student using ReportLab.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#1E3A8A"),
            fontName="Helvetica-Bold",
            spaceAfter=4
        )
        
        sub_title_style = ParagraphStyle(
            'SubTitleStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#64748B"),
            spaceAfter=12
        )

        section_heading = ParagraphStyle(
            'SectionHeading',
            parent=styles['Heading2'],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold",
            spaceBefore=10,
            spaceAfter=6
        )

        body_style = ParagraphStyle(
            'BodyStyle',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#334155")
        )

        story = []

        # 1. Header
        story.append(Paragraph("ACADEMIC ATTENDANCE & RISK ANALYTICS DOSSIER", title_style))
        story.append(Paragraph(f"Institution Academic Faculty Monitoring System • Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}", sub_title_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3B82F6"), spaceAfter=10))

        # 2. Student Profile & Key Metrics Grid
        risk_lvl = risk_data.get('risk_level', 'LOW')
        risk_color_hex = "#EF4444" if risk_lvl in ["HIGH", "CRITICAL"] else ("#F59E0B" if risk_lvl == "MEDIUM" else "#10B981")

        info_data = [
            [
                Paragraph(f"<b>Student Name:</b> {student_summary.get('student_name')}", body_style),
                Paragraph(f"<b>Overall Attendance:</b> {student_summary.get('attendance_pct')}%", body_style)
            ],
            [
                Paragraph(f"<b>Register Number:</b> {student_summary.get('register_number')}", body_style),
                Paragraph(f"<b>Risk Score:</b> <b>{risk_data.get('risk_score')}/100</b> ({risk_lvl})", body_style)
            ],
            [
                Paragraph(f"<b>Department & Year:</b> {student_summary.get('department')} - Yr {student_summary.get('year')} (Sec {student_summary.get('section')})", body_style),
                Paragraph(f"<b>Trend Direction:</b> {risk_data.get('trend_direction')}", body_style)
            ],
            [
                Paragraph(f"<b>Total Classes Held:</b> {student_summary.get('total_classes')} (Attended: {student_summary.get('attended_classes')})", body_style),
                Paragraph(f"<b>Consecutive Req. for 75%:</b> {risk_data.get('required_consecutive')} classes", body_style)
            ]
        ]

        info_table = Table(info_data, colWidths=[270, 270])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#E2E8F0")),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(info_table)
        story.append(Spacer(1, 10))

        # 3. 7-Factor Risk Score Breakdown
        story.append(Paragraph("1. Explainable 7-Factor Risk Score Breakdown", section_heading))
        factor_items = list(risk_data.get("factor_breakdown", {}).items())
        factor_table_data = [["Risk Factor Dimension", "Points Assigned", "Status Impact"]]
        
        for factor_name, score in factor_items:
            impact = "High Impact" if score > 7 else ("Moderate" if score > 3 else "Low / Minimal")
            factor_table_data.append([factor_name, f"{score} pts", impact])

        factor_table = Table(factor_table_data, colWidths=[260, 140, 140])
        factor_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 8.5),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F1F5F9")]),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(factor_table)
        story.append(Spacer(1, 10))

        # 4. Explainable Risk Diagnostics
        story.append(Paragraph("2. Root-Cause Explanations & Behavioral Patterns", section_heading))
        for idx, reason in enumerate(risk_data.get("reasons", []), 1):
            story.append(Paragraph(f"• <b>Diagnostic {idx}:</b> {reason}", body_style))
        story.append(Spacer(1, 10))

        # 5. Faculty Action Plan
        story.append(Paragraph("3. Recommended Faculty Action Plan", section_heading))
        for idx, rec in enumerate(risk_data.get("recommendations", []), 1):
            story.append(Paragraph(f"▶ <b>Action {idx}:</b> {rec}", body_style))
        story.append(Spacer(1, 10))

        # 6. Subject-Wise Breakdown Table
        if not subject_df.empty:
            story.append(Paragraph("4. Course / Subject-Wise Performance", section_heading))
            sub_table_data = [["Code", "Subject Name", "Total", "Attended", "Attendance %", "Risk Level"]]
            for _, row in subject_df.iterrows():
                sub_table_data.append([
                    str(row.get("subject_code", "")),
                    str(row.get("subject_name", ""))[:28],
                    str(row.get("total_classes", "")),
                    str(row.get("attended", "")),
                    f"{row.get('attendance_pct', 0.0)}%",
                    str(row.get("risk_level", ""))
                ])
            sub_table = Table(sub_table_data, colWidths=[65, 205, 50, 60, 80, 80])
            sub_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#334155")),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 8),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
                ('TOPPADDING', (0,0), (-1,-1), 3),
                ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ]))
            story.append(sub_table)

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        return pdf_bytes

    except Exception as e:
        # Fallback to simple bytes report
        return f"PDF generation error: {str(e)}".encode("utf-8")
