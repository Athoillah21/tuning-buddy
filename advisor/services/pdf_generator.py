"""
PDF Report Generator for Query Optimization Results.
Generates professional PDF reports with query analysis details.
"""
import io
import json
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class PDFReportGenerator:
    """Generates PDF reports for query optimization results."""
    
    # Colors
    PRIMARY = colors.HexColor('#0066ff')
    SUCCESS = colors.HexColor('#00a854')
    WARNING = colors.HexColor('#faad14')
    DANGER = colors.HexColor('#f5222d')
    DARK = colors.HexColor('#1a1a1a')
    GRAY = colors.HexColor('#666666')
    LIGHT_GRAY = colors.HexColor('#f0f2f5')
    BORDER = colors.HexColor('#e8e8e8')
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.width, self.height = A4
        self.content_width = self.width - 4*cm
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=10,
            alignment=TA_CENTER,
            textColor=self.PRIMARY,
            fontName='Helvetica-Bold',
        ))
        # Subtitle
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            fontSize=11,
            textColor=self.GRAY,
            alignment=TA_CENTER,
            spaceAfter=20,
        ))
        # Section headers
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=self.DARK,
            fontName='Helvetica-Bold',
            borderPadding=(5, 0, 5, 0),
        ))
        # Sub headers
        self.styles.add(ParagraphStyle(
            name='SubHeader',
            parent=self.styles['Heading3'],
            fontSize=11,
            spaceBefore=12,
            spaceAfter=6,
            textColor=self.GRAY,
            fontName='Helvetica-Bold',
        ))
        # Code style with wrapping
        self.styles.add(ParagraphStyle(
            name='CodeParagraph',
            fontName='Courier',
            fontSize=8,
            leading=11,
            textColor=self.DARK,
            backColor=self.LIGHT_GRAY,
            borderPadding=8,
            wordWrap='CJK',  # Enable word wrapping
        ))
        # Normal text
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            fontSize=10,
            leading=14,
            textColor=self.DARK,
        ))
        # Metric value
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            fontSize=18,
            fontName='Helvetica-Bold',
            textColor=self.PRIMARY,
        ))
        # Small text
        self.styles.add(ParagraphStyle(
            name='Small',
            fontSize=8,
            textColor=self.GRAY,
        ))
    
    def generate_report(self, query_history, recommendations: List) -> io.BytesIO:
        """Generate a PDF report for query analysis results."""
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
        
        # Header Section
        story.extend(self._create_header(query_history))
        
        # Summary Metrics
        story.extend(self._create_metrics_section(query_history, recommendations))
        
        # Original Query Section
        story.extend(self._create_query_section(query_history))
        
        # Execution Plan Section
        if query_history.original_plan:
            story.extend(self._create_execution_plan_section(query_history.original_plan))
        
        # Recommendations Section
        story.extend(self._create_recommendations_section(recommendations, query_history.original_execution_time))
        
        # Footer
        story.extend(self._create_footer(query_history))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def _create_header(self, query_history) -> List:
        """Create report header."""
        elements = []
        
        # Title
        elements.append(Paragraph("🔍 Query Optimization Report", self.styles['ReportTitle']))
        
        # Subtitle with metadata
        subtitle = f"Database: {query_history.connection.name} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        elements.append(Paragraph(subtitle, self.styles['Subtitle']))
        
        # Divider
        elements.append(HRFlowable(width="100%", thickness=2, color=self.PRIMARY, spaceAfter=20))
        
        return elements
    
    def _create_metrics_section(self, query_history, recommendations) -> List:
        """Create summary metrics cards."""
        elements = []
        
        exec_time = query_history.original_execution_time or 0
        rec_count = len(recommendations)
        
        # Find best improvement
        best_improvement = 0
        for rec in recommendations:
            if rec.tested_execution_time and exec_time:
                imp = ((exec_time - rec.tested_execution_time) / exec_time) * 100
                if imp > best_improvement:
                    best_improvement = imp
        
        # Create metrics table
        metrics_data = [
            ['Original Execution Time', 'Recommendations', 'Best Improvement'],
            [
                f"{exec_time:.2f} ms" if exec_time else "N/A",
                str(rec_count),
                f"{best_improvement:.1f}%" if best_improvement > 0 else "N/A"
            ]
        ]
        
        metrics_table = Table(metrics_data, colWidths=[self.content_width/3]*3)
        metrics_table.setStyle(TableStyle([
            # Header row
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.GRAY),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            # Value row
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (-1, 1), 16),
            ('TEXTCOLOR', (0, 1), (0, 1), self.DANGER if exec_time > 100 else self.SUCCESS),
            ('TEXTCOLOR', (1, 1), (1, 1), self.PRIMARY),
            ('TEXTCOLOR', (2, 1), (2, 1), self.SUCCESS if best_improvement > 0 else self.GRAY),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            # Background
            ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
            ('ROUNDEDCORNERS', [8, 8, 8, 8]),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        elements.append(metrics_table)
        elements.append(Spacer(1, 20))
        
        return elements
    
    def _create_query_section(self, query_history) -> List:
        """Create original query section with full wrapped text."""
        elements = []
        
        elements.append(Paragraph("📝 Original Query", self.styles['SectionHeader']))
        
        # Query in a styled box - using Paragraph for proper wrapping
        query_text = query_history.original_query.strip()
        # Escape HTML special characters and preserve whitespace
        query_text = query_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        query_text = query_text.replace('\n', '<br/>')
        query_text = query_text.replace('  ', '&nbsp;&nbsp;')
        
        # Create wrapped code paragraph
        query_para = Paragraph(f"<font face='Courier' size='9'>{query_text}</font>", self.styles['CodeParagraph'])
        
        # Wrap in table for background styling
        query_table = Table([[query_para]], colWidths=[self.content_width])
        query_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
            ('BOX', (0, 0), (-1, -1), 1, self.BORDER),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        
        elements.append(query_table)
        elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_execution_plan_section(self, plan_data) -> List:
        """Create execution plan section with summary (truncated to fit page)."""
        elements = []
        
        elements.append(Paragraph("📊 Execution Plan", self.styles['SectionHeader']))
        
        # Handle different plan data formats
        plan = None
        if isinstance(plan_data, list) and plan_data:
            plan = plan_data[0]
        elif isinstance(plan_data, dict):
            plan = plan_data
        
        if plan:
            # Summary metrics
            planning_time = plan.get('Planning Time', 'N/A')
            execution_time = plan.get('Execution Time', 'N/A')
            
            summary_data = [
                ['Planning Time', 'Execution Time'],
                [
                    f"{planning_time} ms" if isinstance(planning_time, (int, float)) else str(planning_time),
                    f"{execution_time} ms" if isinstance(execution_time, (int, float)) else str(execution_time)
                ]
            ]
            
            summary_table = Table(summary_data, colWidths=[self.content_width/2]*2)
            summary_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('TEXTCOLOR', (0, 0), (-1, 0), self.GRAY),
                ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 1), (-1, 1), 12),
                ('TEXTCOLOR', (0, 1), (-1, 1), self.DARK),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(summary_table)
            elements.append(Spacer(1, 10))
            
            # Extract key plan info for summary display
            plan_info = plan.get('Plan', plan)
            if isinstance(plan_info, dict):
                # Get key metrics
                node_type = plan_info.get('Node Type', 'Unknown')
                total_cost = plan_info.get('Total Cost', 'N/A')
                actual_rows = plan_info.get('Actual Rows', plan_info.get('Plan Rows', 'N/A'))
                
                elements.append(Paragraph("Plan Summary:", self.styles['SubHeader']))
                
                plan_summary = f"""<b>Node Type:</b> {node_type}<br/>
<b>Total Cost:</b> {total_cost}<br/>
<b>Rows:</b> {actual_rows}"""
                
                elements.append(Paragraph(plan_summary, self.styles['Normal']))
                elements.append(Spacer(1, 8))
            
            # Show truncated plan (max 30 lines to fit on page)
            elements.append(Paragraph("Plan Details (truncated):", self.styles['SubHeader']))
            
            plan_json = json.dumps(plan, indent=2, default=str)
            lines = plan_json.split('\n')
            if len(lines) > 30:
                lines = lines[:30]
                lines.append('... (full plan available in database)')
            plan_json = '\n'.join(lines)
            
            plan_json = plan_json.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            plan_json = plan_json.replace('\n', '<br/>')
            plan_json = plan_json.replace('  ', '&nbsp;&nbsp;')
            
            plan_para = Paragraph(f"<font face='Courier' size='7'>{plan_json}</font>", self.styles['CodeParagraph'])
            
            plan_table = Table([[plan_para]], colWidths=[self.content_width])
            plan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
                ('BOX', (0, 0), (-1, -1), 1, self.BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            
            elements.append(plan_table)
        else:
            elements.append(Paragraph("Execution plan data not available.", self.styles['Normal']))
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_recommendations_section(self, recommendations, original_time) -> List:
        """Create recommendations section."""
        elements = []
        
        elements.append(Paragraph("💡 Recommendations", self.styles['SectionHeader']))
        
        if not recommendations:
            elements.append(Paragraph("No recommendations were generated for this query.", self.styles['Normal']))
            return elements
        
        for i, rec in enumerate(recommendations, 1):
            elements.extend(self._create_recommendation_card(rec, i, original_time))
            elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_recommendation_card(self, rec, index: int, original_time: float) -> List:
        """Create a styled recommendation card."""
        elements = []
        
        # Determine improvement color
        tested_time = rec.tested_execution_time
        if tested_time and original_time:
            improvement = ((original_time - tested_time) / original_time) * 100
            if improvement > 0:
                perf_color = self.SUCCESS
                perf_text = f"✓ {improvement:.1f}% faster ({tested_time:.2f} ms)"
            else:
                perf_color = self.DANGER
                perf_text = f"✗ {abs(improvement):.1f}% slower ({tested_time:.2f} ms)"
        elif tested_time:
            perf_color = self.GRAY
            perf_text = f"{tested_time:.2f} ms"
        else:
            perf_color = self.GRAY
            perf_text = "Not tested"
        
        # Get recommendation type
        rec_type = rec.get_recommendation_type_display() if hasattr(rec, 'get_recommendation_type_display') else rec.recommendation_type
        
        # Card header
        header_text = f"<b>#{index} {rec_type.upper()}</b>"
        header = Paragraph(header_text, ParagraphStyle(
            'RecHeader',
            fontSize=11,
            fontName='Helvetica-Bold',
            textColor=self.PRIMARY,
        ))
        
        # Performance badge
        perf_badge = Paragraph(perf_text, ParagraphStyle(
            'PerfBadge',
            fontSize=10,
            textColor=perf_color,
            fontName='Helvetica-Bold',
        ))
        
        # Header row
        header_table = Table([[header, perf_badge]], colWidths=[self.content_width*0.6, self.content_width*0.4])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 6))
        
        # Description
        desc_text = rec.description
        elements.append(Paragraph(desc_text, self.styles['Normal']))
        elements.append(Spacer(1, 8))
        
        # Suggested indexes
        if rec.suggested_indexes:
            elements.append(Paragraph("<b>Suggested Indexes:</b>", self.styles['Small']))
            for idx in rec.suggested_indexes:
                idx_text = idx.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                idx_para = Paragraph(f"<font face='Courier' size='8'>{idx_text}</font>", self.styles['CodeParagraph'])
                idx_table = Table([[idx_para]], colWidths=[self.content_width])
                idx_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
                    ('BOX', (0, 0), (-1, -1), 1, self.BORDER),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ]))
                elements.append(idx_table)
                elements.append(Spacer(1, 4))
        
        # Optimized query
        if rec.optimized_query and rec.optimized_query.strip():
            elements.append(Paragraph("<b>Optimized Query:</b>", self.styles['Small']))
            opt_text = rec.optimized_query.strip()
            opt_text = opt_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            opt_text = opt_text.replace('\n', '<br/>')
            opt_text = opt_text.replace('  ', '&nbsp;&nbsp;')
            
            opt_para = Paragraph(f"<font face='Courier' size='8'>{opt_text}</font>", self.styles['CodeParagraph'])
            opt_table = Table([[opt_para]], colWidths=[self.content_width])
            opt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), self.LIGHT_GRAY),
                ('BOX', (0, 0), (-1, -1), 1, self.BORDER),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elements.append(opt_table)
        
        # Divider
        elements.append(Spacer(1, 5))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=self.BORDER))
        
        return elements
    
    def _create_footer(self, query_history) -> List:
        """Create report footer."""
        elements = []
        
        elements.append(Spacer(1, 30))
        elements.append(HRFlowable(width="100%", thickness=1, color=self.BORDER))
        elements.append(Spacer(1, 10))
        
        # AI Provider info
        if query_history.ai_provider:
            provider = query_history.ai_provider.get('provider_name', 'AI')
            model = query_history.ai_provider.get('model', 'unknown')
            ai_text = f"Powered by {provider} ({model})"
        else:
            ai_text = "Powered by AI"
        
        footer_text = f"{ai_text} | Generated by Tuning Buddy"
        elements.append(Paragraph(footer_text, ParagraphStyle(
            'Footer',
            fontSize=9,
            textColor=self.GRAY,
            alignment=TA_CENTER,
        )))
        
        return elements


def generate_optimization_report(query_history, recommendations) -> io.BytesIO:
    """Convenience function to generate PDF report."""
    generator = PDFReportGenerator()
    return generator.generate_report(query_history, recommendations)
