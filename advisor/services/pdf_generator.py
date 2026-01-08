"""
PDF Report Generator for Query Optimization Results.
Generates professional PDF reports with query analysis details.
"""
import io
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Preformatted, KeepTogether, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class PDFReportGenerator:
    """Generates PDF reports for query optimization results."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='Title2',
            parent=self.styles['Heading1'],
            fontSize=20,
            spaceAfter=20,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#0066ff'),
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=15,
            spaceAfter=10,
            textColor=colors.HexColor('#333333'),
        ))
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            spaceBefore=10,
            spaceAfter=5,
            textColor=colors.HexColor('#666666'),
        ))
        self.styles.add(ParagraphStyle(
            name='CodeStyle',
            fontName='Courier',
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#333333'),
            backColor=colors.HexColor('#f5f5f5'),
        ))
        self.styles.add(ParagraphStyle(
            name='MetaInfo',
            fontSize=9,
            textColor=colors.HexColor('#888888'),
            alignment=TA_CENTER,
        ))
    
    def generate_report(self, query_history, recommendations: List) -> io.BytesIO:
        """
        Generate a PDF report for query analysis results.
        
        Args:
            query_history: QueryHistory model instance
            recommendations: List of Recommendation model instances
            
        Returns:
            BytesIO buffer containing the PDF
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm,
        )
        
        story = []
        
        # Title
        story.append(Paragraph("Query Optimization Report", self.styles['Title2']))
        story.append(Spacer(1, 0.2*inch))
        
        # Meta information
        meta_text = f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Database: {query_history.connection.name}"
        story.append(Paragraph(meta_text, self.styles['MetaInfo']))
        story.append(Spacer(1, 0.3*inch))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dddddd')))
        story.append(Spacer(1, 0.2*inch))
        
        # Original Query Section
        story.append(Paragraph("Original Query", self.styles['SectionHeader']))
        story.append(self._create_stat_table([
            ("Execution Time", f"{query_history.original_execution_time:.2f} ms" if query_history.original_execution_time else "N/A"),
            ("Analysis Status", query_history.analysis_status.upper()),
        ]))
        story.append(Spacer(1, 0.15*inch))
        story.append(Paragraph("SQL Query:", self.styles['SubHeader']))
        story.append(self._create_code_block(query_history.original_query))
        story.append(Spacer(1, 0.2*inch))
        
        # Execution Plan Section (summarized)
        if query_history.original_plan:
            story.append(Paragraph("Execution Plan Summary", self.styles['SectionHeader']))
            plan_data = query_history.original_plan
            if isinstance(plan_data, list) and plan_data:
                plan = plan_data[0]
                plan_time = plan.get('Planning Time', 'N/A')
                exec_time = plan.get('Execution Time', 'N/A')
                story.append(self._create_stat_table([
                    ("Planning Time", f"{plan_time} ms" if plan_time != 'N/A' else 'N/A'),
                    ("Execution Time", f"{exec_time} ms" if exec_time != 'N/A' else 'N/A'),
                ]))
            story.append(Spacer(1, 0.2*inch))
        
        # Recommendations Section
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dddddd')))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Optimization Recommendations", self.styles['SectionHeader']))
        
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                rec_content = self._create_recommendation_block(rec, i, query_history.original_execution_time)
                story.append(KeepTogether(rec_content))
                story.append(Spacer(1, 0.15*inch))
        else:
            story.append(Paragraph("No recommendations generated.", self.styles['Normal']))
        
        # AI Provider info
        if query_history.ai_provider:
            story.append(Spacer(1, 0.2*inch))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#dddddd')))
            story.append(Spacer(1, 0.1*inch))
            ai_text = f"Powered by: {query_history.ai_provider.get('provider_name', 'AI')} ({query_history.ai_provider.get('model', 'unknown')})"
            story.append(Paragraph(ai_text, self.styles['MetaInfo']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def _create_stat_table(self, stats: List[tuple]) -> Table:
        """Create a table for displaying statistics."""
        data = [[s[0], s[1]] for s in stats]
        table = Table(data, colWidths=[2.5*inch, 3*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        return table
    
    def _create_code_block(self, code: str, max_lines: int = 20) -> Preformatted:
        """Create a styled code block."""
        lines = code.strip().split('\n')
        if len(lines) > max_lines:
            lines = lines[:max_lines] + [f'... ({len(lines) - max_lines} more lines)']
        code_text = '\n'.join(lines)
        return Preformatted(code_text, self.styles['CodeStyle'])
    
    def _create_recommendation_block(self, rec, index: int, original_time: float) -> List:
        """Create content block for a single recommendation."""
        elements = []
        
        # Header with type badge
        rec_type = rec.get_recommendation_type_display() if hasattr(rec, 'get_recommendation_type_display') else rec.recommendation_type
        header = f"Recommendation #{index}: {rec_type}"
        elements.append(Paragraph(header, self.styles['SubHeader']))
        
        # Description
        elements.append(Paragraph(rec.description, self.styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Performance stats
        tested_time = rec.tested_execution_time
        if tested_time and original_time:
            improvement = ((original_time - tested_time) / original_time) * 100
            perf_text = f"Tested: {tested_time:.2f} ms ({improvement:+.1f}% {'faster' if improvement > 0 else 'slower'})"
        elif tested_time:
            perf_text = f"Tested: {tested_time:.2f} ms"
        else:
            perf_text = "Not tested"
        elements.append(Paragraph(f"<b>Performance:</b> {perf_text}", self.styles['Normal']))
        elements.append(Spacer(1, 0.1*inch))
        
        # Suggested indexes
        if rec.suggested_indexes:
            elements.append(Paragraph("<b>Suggested Indexes:</b>", self.styles['Normal']))
            for idx in rec.suggested_indexes:
                elements.append(self._create_code_block(idx, max_lines=5))
                elements.append(Spacer(1, 0.05*inch))
        
        # Optimized query (if different)
        if rec.optimized_query and rec.optimized_query.strip():
            elements.append(Paragraph("<b>Optimized Query:</b>", self.styles['Normal']))
            elements.append(self._create_code_block(rec.optimized_query, max_lines=15))
        
        return elements


def generate_optimization_report(query_history, recommendations) -> io.BytesIO:
    """
    Convenience function to generate PDF report.
    
    Args:
        query_history: QueryHistory model instance
        recommendations: List of Recommendation instances
        
    Returns:
        BytesIO buffer containing PDF
    """
    generator = PDFReportGenerator()
    return generator.generate_report(query_history, recommendations)
