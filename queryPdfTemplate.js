/**
 * Query PDF Generator - Standalone Template
 * Generates styled PDF for a single query with AI analysis
 * 
 * Usage with Puppeteer:
 *   import puppeteer from 'puppeteer';
 *   const html = generateQueryPdfHtml(query, analysis);
 *   // Then use puppeteer to convert HTML to PDF
 */

/**
 * Generate HTML template for query PDF with AI analysis
 * 
 * @param {Object} query - The query object
 * @param {number} query.rank - Query rank
 * @param {string} query.queryText - The SQL query text
 * @param {number} query.executionCount - Number of executions
 * @param {string} query.totalDuration - Total duration
 * @param {string} query.avgDuration - Average duration
 * @param {string} query.minDuration - Minimum duration
 * @param {string} query.maxDuration - Maximum duration
 * @param {string} query.database - Database name
 * @param {string} query.user - User name
 * 
 * @param {Object} analysis - The AI analysis object
 * @param {string} analysis.provider - AI provider (e.g., 'deepseek', 'groq')
 * @param {string} analysis.model - Model name
 * @param {Array} analysis.recommendations - Array of recommendations
 * @param {string} analysis.recommendations[].type - Type: 'query_rewrite', 'add_index', 'configuration_change'
 * @param {string} analysis.recommendations[].description - Description text
 * @param {boolean} analysis.recommendations[].is_best - Whether this is the best recommendation
 * @param {Array} analysis.recommendations[].suggested_indexes - Array of index SQL statements
 * @param {string} analysis.recommendations[].optimized_query - Optimized SQL query
 */
function generateQueryPdfHtml(query, analysis) {
    const recsHtml = analysis?.recommendations?.map((rec, i) => `
    <div class="rec-card ${rec.is_best ? 'best' : ''}">
      <div class="rec-header">
        <span class="rec-num">#${i + 1}</span>
        <span class="rec-type">${rec.type?.replace('_', ' ').toUpperCase() || 'RECOMMENDATION'}</span>
        ${rec.is_best ? '<span class="best-badge">BEST</span>' : ''}
      </div>
      <p class="rec-desc">${escapeHtml(rec.description || '')}</p>
      ${rec.suggested_indexes?.length ? `
        <div class="rec-section">
          <strong>Suggested Indexes:</strong>
          ${rec.suggested_indexes.map(idx => `<pre class="sql-small">${escapeHtml(idx)}</pre>`).join('')}
        </div>
      ` : ''}
      ${rec.optimized_query ? `
        <div class="rec-section">
          <strong>Optimized Query:</strong>
          <pre class="sql-small">${escapeHtml(rec.optimized_query)}</pre>
        </div>
      ` : ''}
    </div>
  `).join('') || '<p class="no-analysis">No AI analysis available.</p>';

    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Query #${query.rank} Analysis</title>
  <style>
    /* Reset */
    * { margin: 0; padding: 0; box-sizing: border-box; }
    
    /* Base */
    body { 
      font-family: 'Segoe UI', Arial, sans-serif; 
      padding: 40px; 
      color: #1a1a2e; 
      background: #fff; 
      line-height: 1.5;
    }
    
    /* Header */
    .header { 
      margin-bottom: 30px; 
      padding-bottom: 20px; 
      border-bottom: 2px solid #3b82f6; 
    }
    .header h1 { 
      color: #1e293b; 
      font-size: 24px; 
      margin-bottom: 5px; 
    }
    .header p { 
      color: #64748b; 
      font-size: 13px; 
    }
    
    /* Badges */
    .badge { 
      display: inline-block; 
      padding: 4px 10px; 
      border-radius: 4px; 
      font-size: 12px; 
      font-weight: 600; 
      margin-right: 8px; 
    }
    .badge-duration { 
      background: rgba(59, 130, 246, 0.15); 
      color: #3b82f6; 
    }
    .badge-count { 
      background: rgba(30, 41, 59, 0.1); 
      color: #1e293b; 
    }
    
    /* Sections */
    .section { 
      margin-bottom: 25px; 
    }
    .section-title { 
      font-size: 16px; 
      color: #1e293b; 
      margin-bottom: 12px; 
      display: flex; 
      align-items: center; 
      gap: 8px; 
    }
    
    /* SQL Code Blocks */
    .sql { 
      font-family: 'Consolas', 'Monaco', monospace; 
      font-size: 12px; 
      background: #1e293b; 
      color: #e4e4e7; 
      padding: 15px; 
      border-radius: 8px; 
      overflow-x: auto; 
      white-space: pre-wrap; 
      word-break: break-all; 
    }
    .sql-small { 
      font-family: 'Consolas', 'Monaco', monospace; 
      font-size: 11px; 
      background: #1e293b; 
      color: #e4e4e7; 
      padding: 10px; 
      border-radius: 6px; 
      margin-top: 8px; 
      white-space: pre-wrap; 
      word-break: break-all; 
    }
    
    /* Stats Grid */
    .stats-grid { 
      display: grid; 
      grid-template-columns: repeat(2, 1fr); 
      gap: 10px; 
      margin-bottom: 25px; 
    }
    .stat-item { 
      display: flex; 
      justify-content: space-between; 
      padding: 10px 15px; 
      background: #f8fafc; 
      border-radius: 6px; 
      font-size: 13px; 
    }
    .stat-item span:first-child { color: #64748b; }
    .stat-item strong { color: #1a1a2e; }
    
    /* Recommendation Cards */
    .rec-card { 
      background: #f8fafc; 
      border: 1px solid #e2e8f0; 
      border-radius: 8px; 
      padding: 15px; 
      margin-bottom: 15px; 
      page-break-inside: avoid; 
    }
    .rec-card.best { 
      border-color: #22c55e; 
      background: rgba(34, 197, 94, 0.05); 
    }
    .rec-header { 
      display: flex; 
      align-items: center; 
      gap: 10px; 
      margin-bottom: 10px; 
    }
    .rec-num { 
      font-size: 18px; 
      font-weight: 700; 
      color: #64748b; 
    }
    .rec-type { 
      font-size: 10px; 
      font-weight: 600; 
      background: #3b82f6; 
      color: white; 
      padding: 3px 8px; 
      border-radius: 4px; 
    }
    .best-badge { 
      font-size: 10px; 
      font-weight: 600; 
      background: linear-gradient(135deg, #22c55e, #16a34a); 
      color: white; 
      padding: 3px 8px; 
      border-radius: 4px; 
      margin-left: auto; 
    }
    .rec-desc { 
      font-size: 13px; 
      color: #475569; 
      line-height: 1.6; 
      margin-bottom: 10px; 
    }
    .rec-section { 
      margin-top: 12px; 
      padding-top: 12px; 
      border-top: 1px solid #e2e8f0; 
    }
    .rec-section strong { 
      font-size: 11px; 
      color: #64748b; 
      text-transform: uppercase; 
      display: block; 
      margin-bottom: 5px; 
    }
    
    /* Empty State */
    .no-analysis { 
      text-align: center; 
      padding: 30px; 
      color: #64748b; 
    }
    
    /* Footer */
    .footer { 
      text-align: center; 
      margin-top: 30px; 
      padding-top: 20px; 
      border-top: 1px solid #e2e8f0; 
      font-size: 11px; 
      color: #64748b; 
    }
  </style>
</head>
<body>
  <div class="header">
    <h1>Query #${query.rank} Analysis</h1>
    <p>Database: ${query.database || '-'} • User: ${query.user || '-'}</p>
    <div style="margin-top: 10px;">
      <span class="badge badge-count">${query.executionCount} executions</span>
      <span class="badge badge-duration">${query.avgDuration || '-'} avg</span>
    </div>
  </div>
  
  <div class="section">
    <h2 class="section-title">SQL Query</h2>
    <pre class="sql">${escapeHtml(query.queryText)}</pre>
  </div>
  
  <div class="section">
    <h2 class="section-title">Statistics</h2>
    <div class="stats-grid">
      <div class="stat-item"><span>Total Duration</span><strong>${query.totalDuration || '-'}</strong></div>
      <div class="stat-item"><span>Min Duration</span><strong>${query.minDuration || '-'}</strong></div>
      <div class="stat-item"><span>Max Duration</span><strong>${query.maxDuration || '-'}</strong></div>
      <div class="stat-item"><span>Avg Duration</span><strong>${query.avgDuration || '-'}</strong></div>
    </div>
  </div>
  
  ${analysis ? `
  <div class="section">
    <h2 class="section-title">AI Recommendations (${analysis.provider} ${analysis.model})</h2>
    ${recsHtml}
  </div>
  ` : ''}
  
  <div class="footer">
    <p>Generated by Query Analyzer • ${new Date().toLocaleString()}</p>
  </div>
</body>
</html>
  `;
}

/**
 * Escape HTML special characters to prevent XSS
 */
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

/**
 * Example: Generate PDF with Puppeteer
 * 
 * async function generatePdf(query, analysis) {
 *     const puppeteer = require('puppeteer');
 *     const html = generateQueryPdfHtml(query, analysis);
 *     
 *     const browser = await puppeteer.launch({ headless: 'new' });
 *     const page = await browser.newPage();
 *     await page.setContent(html, { waitUntil: 'networkidle0' });
 *     
 *     const pdf = await page.pdf({
 *         format: 'A4',
 *         margin: { top: '20mm', right: '15mm', bottom: '20mm', left: '15mm' },
 *         printBackground: true
 *     });
 *     
 *     await browser.close();
 *     return pdf;
 * }
 */

// Export for use in other projects
module.exports = { generateQueryPdfHtml, escapeHtml };
// Or for ES modules:
// export { generateQueryPdfHtml, escapeHtml };
