"""
PDF Generator — Creates government form PDFs with Telugu font support.

Uses WeasyPrint to render HTML → PDF with:
- AP Government header (Telugu + English)
- Noto Sans Telugu font
- Structured form layout
- QR code for verification (optional)
"""
import os
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.form import FormSubmission, FormTemplate

logger = structlog.get_logger()

# Google Fonts CDN for Telugu font
TELUGU_FONT_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Telugu:wght@400;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap');
"""

# PDF output directory
PDF_DIR = Path(tempfile.gettempdir()) / "sachivalayam_pdfs"
PDF_DIR.mkdir(exist_ok=True)


class PDFGenerator:
    """Generates government form PDFs with Telugu support."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate(self, submission_id: UUID) -> str | None:
        """Generate PDF for a form submission. Returns file path."""
        result = await self.db.execute(
            select(FormSubmission, FormTemplate)
            .join(FormTemplate, FormTemplate.id == FormSubmission.template_id)
            .where(FormSubmission.id == submission_id)
        )
        row = result.one_or_none()

        if not row:
            logger.error("Submission not found for PDF", submission_id=str(submission_id))
            return None

        submission, template = row

        # Build HTML
        html = self._build_html(template, submission)

        # Generate PDF
        pdf_path = str(PDF_DIR / f"{submission_id}.pdf")

        try:
            from weasyprint import HTML
            HTML(string=html).write_pdf(pdf_path)

            # Update submission with PDF path
            submission.pdf_url = pdf_path
            await self.db.flush()

            logger.info("PDF generated", submission_id=str(submission_id), path=pdf_path)
            return pdf_path

        except ImportError:
            logger.warning("WeasyPrint not installed, generating HTML fallback")
            html_path = str(PDF_DIR / f"{submission_id}.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            submission.pdf_url = html_path
            return html_path

    def _build_html(self, template: FormTemplate, submission: FormSubmission) -> str:
        """Build complete HTML document for the form."""
        now = datetime.now()
        date_str = now.strftime("%d-%m-%Y")
        time_str = now.strftime("%I:%M %p")

        # Build form fields table rows
        field_rows = self._build_field_rows(template.fields, submission.field_values)

        return f"""<!DOCTYPE html>
<html lang="te">
<head>
    <meta charset="UTF-8">
    <style>
        {TELUGU_FONT_CSS}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Noto Sans Telugu', 'Noto Sans', sans-serif;
            font-size: 11pt;
            color: #1a1a1a;
            padding: 25mm 20mm;
            line-height: 1.5;
        }}

        .header {{
            text-align: center;
            border-bottom: 3px double #1a5276;
            padding-bottom: 12px;
            margin-bottom: 15px;
        }}

        .header .emblem {{
            font-size: 28px;
            margin-bottom: 4px;
        }}

        .header .govt-name {{
            font-size: 16pt;
            font-weight: 700;
            color: #1a5276;
            margin: 3px 0;
        }}

        .header .dept-name {{
            font-size: 11pt;
            font-weight: 600;
            color: #2c3e50;
        }}

        .header .form-title {{
            font-size: 13pt;
            font-weight: 700;
            margin-top: 8px;
            color: #c0392b;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .meta-info {{
            display: flex;
            justify-content: space-between;
            font-size: 9pt;
            color: #666;
            margin-bottom: 12px;
            border-bottom: 1px solid #eee;
            padding-bottom: 6px;
        }}

        .form-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}

        .form-table td {{
            padding: 7px 10px;
            border: 1px solid #bdc3c7;
            vertical-align: top;
        }}

        .form-table .label {{
            background: #f8f9fa;
            font-weight: 600;
            width: 40%;
            color: #2c3e50;
            font-size: 10pt;
        }}

        .form-table .value {{
            font-size: 10.5pt;
            color: #1a1a1a;
        }}

        .form-table .value.empty {{
            color: #bbb;
            font-style: italic;
        }}

        .section-header {{
            background: #1a5276;
            color: white;
            font-weight: 700;
            text-align: center;
            font-size: 10pt;
            letter-spacing: 0.5px;
        }}

        .signature-section {{
            margin-top: 25px;
            display: flex;
            justify-content: space-between;
        }}

        .signature-box {{
            text-align: center;
            width: 40%;
        }}

        .signature-line {{
            border-top: 1px solid #333;
            margin-top: 40px;
            padding-top: 4px;
            font-size: 9pt;
            font-weight: 600;
        }}

        .footer {{
            margin-top: 20px;
            padding-top: 8px;
            border-top: 1px solid #ddd;
            font-size: 8pt;
            color: #888;
            text-align: center;
        }}

        .footer .ai-badge {{
            background: #eaf2f8;
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            color: #2980b9;
            font-weight: 600;
        }}

        @media print {{
            body {{ padding: 15mm; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="emblem">🏛️</div>
        <div class="govt-name">ఆంధ్రప్రదేశ్ ప్రభుత్వం</div>
        <div class="govt-name" style="font-size: 12pt;">Government of Andhra Pradesh</div>
        <div class="dept-name">{template.department}</div>
        <div class="form-title">{template.name_te}</div>
        <div class="form-title" style="font-size: 10pt; color: #666;">{template.name_en}</div>
    </div>

    <div class="meta-info">
        <span>Form: {template.gsws_form_code or 'N/A'}</span>
        <span>Ref: {str(submission.id)[:8].upper()}</span>
        <span>Date: {date_str} | Time: {time_str}</span>
    </div>

    <table class="form-table">
        <tr class="section-header">
            <td colspan="2">దరఖాస్తుదారు వివరాలు / Applicant Details</td>
        </tr>
        {field_rows}
    </table>

    <div class="signature-section">
        <div class="signature-box">
            <div class="signature-line">దరఖాస్తుదారు సంతకం<br/>Applicant Signature</div>
        </div>
        <div class="signature-box">
            <div class="signature-line">సచివాలయం అధికారి సంతకం<br/>Secretariat Official Signature</div>
        </div>
    </div>

    <div class="footer">
        <p>
            <span class="ai-badge">🤖 AI-Assisted</span>
            Generated by AP Sachivalayam AI Copilot | {date_str}
        </p>
        <p>This form was auto-filled using AI. Please verify all details before submission.</p>
        <p>ఈ ఫారం AI ద్వారా auto-fill చేయబడింది. దయచేసి submit చేసే ముందు అన్ని details verify చేయండి.</p>
    </div>
</body>
</html>"""

    def _build_field_rows(self, template_fields: dict, field_values: dict) -> str:
        """Build HTML table rows for form fields."""
        rows = []
        for field_name, defn in template_fields.items():
            if isinstance(defn, dict):
                label_te = defn.get("label_te", field_name)
                label_en = defn.get("label_en", "")
                label = f"{label_te}<br/><span style='font-size:8pt;color:#888'>{label_en}</span>"
            else:
                label = str(defn)

            value = field_values.get(field_name, "")
            value_class = "value" if value else "value empty"
            display_value = str(value) if value else "—"

            rows.append(
                f'<tr><td class="label">{label}</td>'
                f'<td class="{value_class}">{display_value}</td></tr>'
            )
        return "\n".join(rows)
