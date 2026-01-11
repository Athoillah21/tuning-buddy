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
    
    # Colors - matching queryPdfTemplate.js design
    PRIMARY = colors.HexColor('#3b82f6')      # Modern blue
    SUCCESS = colors.HexColor('#22c55e')      # Green for success
    WARNING = colors.HexColor('#faad14')      # Amber warning
    DANGER = colors.HexColor('#f5222d')       # Red for errors
    DARK = colors.HexColor('#1e293b')         # Dark slate for text/code blocks
    TEXT_PRIMARY = colors.HexColor('#1a1a2e') # Primary text color
    GRAY = colors.HexColor('#64748b')         # Muted text
    LIGHT_GRAY = colors.HexColor('#f8fafc')   # Light background
    BORDER = colors.HexColor('#e2e8f0')       # Subtle border
    CODE_BG = colors.HexColor('#1e293b')      # Dark code block background
    CODE_TEXT = colors.HexColor('#e4e4e7')    # Light text for code blocks
    
    # Scan types to track
    SEQ_SCAN_TYPES = ['Seq Scan', 'Parallel Seq Scan']
    INDEX_SCAN_TYPES = ['Index Scan', 'Index Only Scan', 'Bitmap Index Scan', 'Bitmap Heap Scan']
    
    @staticmethod
    def _extract_scan_types(plan_data) -> dict:
        """
        Extract scan types from execution plan.
        Returns dict with: has_seq_scan, has_index_scan, scan_nodes list
        """
        result = {
            'has_seq_scan': False,
            'has_index_scan': False,
            'scan_nodes': [],
            'seq_scan_tables': [],
            'index_scan_tables': []
        }
        
        def traverse_plan(node):
            if isinstance(node, dict):
                node_type = node.get('Node Type', '')
                table_name = node.get('Relation Name', node.get('Alias', ''))
                
                if node_type in PDFReportGenerator.SEQ_SCAN_TYPES:
                    result['has_seq_scan'] = True
                    result['scan_nodes'].append(f"⚠️ {node_type}: {table_name}")
                    if table_name:
                        result['seq_scan_tables'].append(table_name)
                elif node_type in PDFReportGenerator.INDEX_SCAN_TYPES:
                    result['has_index_scan'] = True
                    index_name = node.get('Index Name', '')
                    result['scan_nodes'].append(f"✓ {node_type}: {table_name} ({index_name})")
                    if table_name:
                        result['index_scan_tables'].append(table_name)
                
                # Traverse child plans
                for child in node.get('Plans', []):
                    traverse_plan(child)
                # Also check 'Plan' key
                if 'Plan' in node:
                    traverse_plan(node['Plan'])
        
        # Handle different input formats
        if isinstance(plan_data, list) and plan_data:
            traverse_plan(plan_data[0])
        elif isinstance(plan_data, dict):
            traverse_plan(plan_data)
        
        return result
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
        self.width, self.height = A4
        self.content_width = self.width - 4*cm
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title - matching queryPdfTemplate.js header style
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceBefore=0,
            spaceAfter=12,
            alignment=TA_CENTER,
            textColor=self.DARK,
            fontName='Helvetica-Bold',
        ))
        # Subtitle - close to title
        self.styles.add(ParagraphStyle(
            name='Subtitle',
            fontSize=11,
            textColor=self.GRAY,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=15,
        ))
        # Section headers - tighter spacing
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=12,
            spaceAfter=6,
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
        # Code style with wrapping - dark theme like queryPdfTemplate.js
        self.styles.add(ParagraphStyle(
            name='CodeParagraph',
            fontName='Courier',
            fontSize=9,
            leading=12,
            textColor=self.CODE_TEXT,
            backColor=self.CODE_BG,
            borderPadding=10,
            wordWrap='CJK',  # Enable word wrapping
        ))
        # Smaller code style for recommendations
        self.styles.add(ParagraphStyle(
            name='CodeSmall',
            fontName='Courier',
            fontSize=8,
            leading=10,
            textColor=self.CODE_TEXT,
            backColor=self.CODE_BG,
            borderPadding=8,
            wordWrap='CJK',
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
        
        # Original Query Section
        story.extend(self._create_query_section(query_history))
        
        # Scan Type Analysis (extract for use in recommendations too)
        orig_plan = query_history.original_plan
        scan_info = {'has_seq_scan': False, 'has_index_scan': False}
        if orig_plan:
            scan_info = self._extract_scan_types(orig_plan)
        
        # Execution Plan Section
        if orig_plan:
            story.extend(self._create_execution_plan_section(orig_plan))
        
        # Recommendations Section
        story.extend(self._create_recommendations_section(recommendations, query_history.original_execution_time, scan_info))
        
        # Footer
        story.extend(self._create_footer(query_history))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def _create_header(self, query_history) -> List:
        """Create report header."""
        elements = []
        
        # Title - clean design without emoji (emojis render as squares in PDF)
        elements.append(Paragraph("Query Optimization Report", self.styles['ReportTitle']))
        
        # Subtitle with metadata
        subtitle = f"Database: {query_history.connection.name} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        elements.append(Paragraph(subtitle, self.styles['Subtitle']))
        
        # Blue accent divider like queryPdfTemplate.js
        elements.append(HRFlowable(width="100%", thickness=2, color=self.PRIMARY, spaceAfter=25))
        
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
        
        # Query in a styled dark box - like queryPdfTemplate.js
        query_text = query_history.original_query.strip()
        # Escape HTML special characters and preserve whitespace
        query_text = query_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        query_text = query_text.replace('\n', '<br/>')
        query_text = query_text.replace('  ', '&nbsp;&nbsp;')
        
        # Create wrapped code paragraph with dark theme
        query_para = Paragraph(f"<font face='Courier' size='9' color='#e4e4e7'>{query_text}</font>", self.styles['CodeParagraph'])
        
        # Wrap in table for dark background styling
        query_table = Table([[query_para]], colWidths=[self.content_width])
        query_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), self.CODE_BG),
            ('BOX', (0, 0), (-1, -1), 0, self.CODE_BG),
            ('LEFTPADDING', (0, 0), (-1, -1), 15),
            ('RIGHTPADDING', (0, 0), (-1, -1), 15),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('ROUNDEDCORNERS', [8, 8, 8, 8]),
        ]))
        
        elements.append(query_table)
        elements.append(Spacer(1, 8))
        
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
            
            # Summary metrics (Compact)
            planning_time = plan.get('Planning Time', 'N/A')
            execution_time = plan.get('Execution Time', 'N/A')
            
            p_time_str = f"{planning_time} ms" if isinstance(planning_time, (int, float)) else str(planning_time)
            e_time_str = f"{execution_time} ms" if isinstance(execution_time, (int, float)) else str(execution_time)
            
            metrics_text = f"<b>Planning Time:</b> {p_time_str} &nbsp;|&nbsp; <b>Execution Time:</b> {e_time_str}"
            elements.append(Paragraph(metrics_text, self.styles['Normal']))
            elements.append(Spacer(1, 6))
            
            # Scan Type Analysis
            scan_info = self._extract_scan_types(plan_data)
            
            elements.append(Paragraph("Scan Type Analysis:", self.styles['SubHeader']))
            
            if scan_info['has_seq_scan']:
                # Warning for Seq Scan
                seq_tables = ', '.join(scan_info['seq_scan_tables']) if scan_info['seq_scan_tables'] else 'tables'
                warning_text = f"<font color='#f5222d'><b>⚠️ WARNING: Sequential Scan detected on: {seq_tables}</b></font><br/>Sequential scans can be slow on large tables. Consider adding indexes."
                elements.append(Paragraph(warning_text, self.styles['Normal']))
            elif scan_info['has_index_scan']:
                # Good - using indexes
                success_text = "<font color='#00a854'><b>✓ GOOD: Query is using Index Scans</b></font><br/>The query is efficiently using indexes."
                elements.append(Paragraph(success_text, self.styles['Normal']))
            else:
                elements.append(Paragraph("No scan operations detected.", self.styles['Normal']))
            
            # Show scan nodes list
            if scan_info['scan_nodes']:
                elements.append(Spacer(1, 4))
                nodes_text = '<br/>'.join(scan_info['scan_nodes'][:5])  # Max 5 nodes
                elements.append(Paragraph(f"<font size='8'>{nodes_text}</font>", self.styles['Normal']))
            
            elements.append(Spacer(1, 6))
            
            # Extract key plan info for summary display
            plan_info = plan.get('Plan', plan)
            if isinstance(plan_info, dict):
                # Get key metrics
                node_type = plan_info.get('Node Type', 'Unknown')
                total_cost = plan_info.get('Total Cost', 'N/A')
                actual_rows = plan_info.get('Actual Rows', plan_info.get('Plan Rows', 'N/A'))
                
                plan_summary = f"<b>Plan Summary:</b> Node Type: {node_type} | Total Cost: {total_cost} | Rows: {actual_rows}"
                
                elements.append(Paragraph(plan_summary, self.styles['Normal']))
                elements.append(Spacer(1, 6))
            
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
            
            plan_para = Paragraph(f"<font face='Courier' size='7' color='#e4e4e7'>{plan_json}</font>", self.styles['CodeSmall'])
            
            plan_table = Table([[plan_para]], colWidths=[self.content_width])
            plan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), self.CODE_BG),
                ('BOX', (0, 0), (-1, -1), 0, self.CODE_BG),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            
            elements.append(plan_table)
        else:
            elements.append(Paragraph("Execution plan data not available.", self.styles['Normal']))
        
        elements.append(Spacer(1, 20))
        return elements
    
    def _create_recommendations_section(self, recommendations, original_time, scan_info=None) -> List:
        """Create recommendations section."""
        elements = []
        
        # Start Recommendations section on a new page
        elements.append(PageBreak())
        elements.append(Paragraph("💡 Recommendations", self.styles['SectionHeader']))
        
        if not recommendations:
            elements.append(Paragraph("No recommendations were generated for this query.", self.styles['Normal']))
            return elements
        
        for i, rec in enumerate(recommendations, 1):
            if i > 1:
                elements.append(PageBreak())
            elements.extend(self._create_recommendation_card(rec, i, original_time, scan_info))
            elements.append(Spacer(1, 15))
        
        return elements
    
    def _create_recommendation_card(self, rec, index: int, original_time: float, scan_info=None) -> List:
        """Create a styled recommendation card."""
        elements = []
        
        # Determine improvement color
        tested_time = rec.tested_execution_time
        is_faster = False
        if tested_time and original_time:
            improvement = ((original_time - tested_time) / original_time) * 100
            if improvement > 0:
                perf_color = self.SUCCESS
                perf_text = f"✓ Execution time : {tested_time:.2f} ms ({improvement:.1f}% faster)"
                is_faster = True
            else:
                perf_color = self.DANGER
                perf_text = f"✗ Execution time : {tested_time:.2f} ms ({abs(improvement):.1f}% slower)"
        elif tested_time:
            perf_color = self.GRAY
            perf_text = f"Execution time : {tested_time:.2f} ms"
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
        

        
        # Header row (Title only)
        header_table = Table([[header]], colWidths=[self.content_width])
        header_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(header_table)
        elements.append(Spacer(1, 6))
        
        # Description
        desc_text = rec.description
        elements.append(Paragraph(desc_text, self.styles['Normal']))
        elements.append(Spacer(1, 8))
        
        # Performance/Execution Time (Moved to body)
        # Create a new style for body performance text if needed, or reuse PerfBadge with adjustments
        perf_para = Paragraph(perf_text, ParagraphStyle(
            'PerfBody',
            parent=self.styles['Normal'],
            textColor=perf_color,
            fontName='Helvetica-Bold',
            fontSize=10,
        ))
        elements.append(perf_para)
        elements.append(Spacer(1, 8))
        
        # Scan Type Improvement Analysis
        if scan_info and scan_info.get('has_seq_scan'):
            # Check if we have a tested plan to confirm
            if hasattr(rec, 'tested_plan') and rec.tested_plan:
                tested_scan_info = self._extract_scan_types(rec.tested_plan)
                
                if not tested_scan_info['has_seq_scan']:
                    # Confirmed Resolution
                    scan_res_text = "<font color='#00a854'><b>✓ Confirmed: Seq Scan replaced by Index Scan</b></font>"
                    elements.append(Paragraph(scan_res_text, self.styles['Small']))
                else:
                    # Persists
                    scan_res_text = "<font color='#faad14'><b>⚠️ Warning: Sequential Scan persists in tested plan</b></font>"
                    elements.append(Paragraph(scan_res_text, self.styles['Small']))
                elements.append(Spacer(1, 8))
            
            # Fallback to inference if no tested plan (legacy support)
            elif is_faster and rec.suggested_indexes:
                scan_res_text = "<font color='#00a854'><b>✓ Potential Scan Improvement:</b> Likely resolved to Index Scan (inferred)</font>"
                elements.append(Paragraph(scan_res_text, self.styles['Small']))
                elements.append(Spacer(1, 8))
        
        # Optimization attempts info (if iterative)
        attempts = getattr(rec, 'optimization_attempts', None) or 1
        if attempts and attempts > 1:
            attempts_text = f"<font color='#666666'><b>🔄 Optimization Iterations:</b> {attempts} attempts to meet goals</font>"
            elements.append(Paragraph(attempts_text, self.styles['Small']))
            elements.append(Spacer(1, 4))
        
        # All indexes that were applied (accumulated from all iterations)
        all_indexes = getattr(rec, 'all_indexes_applied', None) or rec.suggested_indexes
        if all_indexes:
            if attempts and attempts > 1:
                elements.append(Paragraph("<b>All Indexes Applied (accumulated):</b>", self.styles['Small']))
            else:
                elements.append(Paragraph("<b>Suggested Indexes:</b>", self.styles['Small']))
            
            for idx in all_indexes:
                idx_text = idx.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                idx_para = Paragraph(f"<font face='Courier' size='8' color='#e4e4e7'>{idx_text}</font>", self.styles['CodeSmall'])
                idx_table = Table([[idx_para]], colWidths=[self.content_width])
                idx_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), self.CODE_BG),
                    ('BOX', (0, 0), (-1, -1), 0, self.CODE_BG),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                    ('ROUNDEDCORNERS', [6, 6, 6, 6]),
                ]))
                elements.append(idx_table)
                elements.append(Spacer(1, 6))
        
        # Final optimized query (use accumulated version if available)
        final_query = getattr(rec, 'final_optimized_query', None) or rec.optimized_query
        query_was_rewritten = getattr(rec, 'query_was_rewritten', False)
        
        if final_query and final_query.strip():
            if query_was_rewritten:
                elements.append(Paragraph("<b>Final Optimized Query (rewritten):</b>", self.styles['Small']))
            else:
                elements.append(Paragraph("<b>Optimized Query:</b>", self.styles['Small']))
            
            opt_text = final_query.strip()
            opt_text = opt_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            opt_text = opt_text.replace('\n', '<br/>')
            opt_text = opt_text.replace('  ', '&nbsp;&nbsp;')
            
            opt_para = Paragraph(f"<font face='Courier' size='8' color='#e4e4e7'>{opt_text}</font>", self.styles['CodeSmall'])
            opt_table = Table([[opt_para]], colWidths=[self.content_width])
            opt_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), self.CODE_BG),
                ('BOX', (0, 0), (-1, -1), 0, self.CODE_BG),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            elements.append(opt_table)
            elements.append(Spacer(1, 6))
        
        # Tested Execution Plan
        if hasattr(rec, 'tested_plan') and rec.tested_plan:
            elements.append(Paragraph("<b>Optimized Execution Plan:</b>", self.styles['Small']))
            
            # Use same truncation logic as main execution plan
            plan_json = json.dumps(rec.tested_plan, indent=2, default=str)
            lines = plan_json.split('\n')
            if len(lines) > 20: 
                lines = lines[:20]
                lines.append('... (full plan available in database)')
            plan_json = '\n'.join(lines)
            
            plan_json = plan_json.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            plan_json = plan_json.replace('\n', '<br/>')
            plan_json = plan_json.replace('  ', '&nbsp;&nbsp;')
            
            plan_para = Paragraph(f"<font face='Courier' size='8' color='#e4e4e7'>{plan_json}</font>", self.styles['CodeSmall'])
            plan_table = Table([[plan_para]], colWidths=[self.content_width])
            plan_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), self.CODE_BG),
                ('BOX', (0, 0), (-1, -1), 0, self.CODE_BG),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('ROUNDEDCORNERS', [6, 6, 6, 6]),
            ]))
            elements.append(plan_table)
        
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
