"""
AI client for query optimization recommendations.
Supports multiple providers with fallback: Gemini → DeepSeek → Groq
"""
import json
import logging
from typing import List, Dict, Any, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)

# Try importing providers
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


# Prompt template for query optimization
OPTIMIZATION_PROMPT = """You are a PostgreSQL performance expert. Analyze the following SQL query and its execution plan, then provide exactly 3 different optimization recommendations.

## Original Query:
```sql
{query}
```

## Current Table Structure:
{table_info}

## Current Execution Plan:
```json
{plan}
```

## Execution Time: {execution_time}ms

## Current Issues Detected:
{issues}

---

Based on the table structure above (including EXISTING indexes), provide exactly 3 optimization recommendations with different approaches. Each recommendation should be practical and testable.

IMPORTANT: Review the existing indexes before suggesting new ones. Only suggest indexes that don't already exist.

CRITICAL INDEX RULES (MUST FOLLOW):
1. **ABSOLUTELY NEVER** use INCLUDE clause - it causes "index row size exceeds maximum" errors
2. **ONLY CREATE INDEX statements** in suggested_indexes - NO ALTER TABLE, NO CREATE TABLE
3. Do NOT include large columns (JSON, JSONB, TEXT, BYTEA, or any column with large data) in indexes
4. Use expression indexes for extracting values from JSON: CREATE INDEX ... ON table((json_extract_path_text(col, 'key')))
5. If you need covering index, use composite index on extracted values only, NOT INCLUDE

WRONG (will fail):
- CREATE INDEX ... INCLUDE (fullobject) -- INCLUDE causes row size error
- CREATE INDEX ... INCLUDE (any_text_column) -- INCLUDE with large data fails
- ALTER TABLE ... -- Not allowed in suggested_indexes

CORRECT:
- CREATE INDEX ... ON table(objecttypes_id, (json_extract_path_text(fullobject, 'startTime')))

Return your response as a valid JSON array with exactly 3 objects. Each object must have:
- "type": one of "index", "rewrite", or "config"
- "description": clear explanation of what this optimization does and why it helps
- "optimized_query": the rewritten query (can be same as original if only index changes)
- "suggested_indexes": array of CREATE INDEX statements ONLY (no ALTER TABLE, no INCLUDE clause)
- "expected_improvement": "high", "medium", or "low"
- "explanation": technical explanation of why this helps

IMPORTANT: Return ONLY the JSON array, no additional text or markdown formatting.
"""

# Follow-up prompt for fixing seq scans and improving performance
SEQ_SCAN_FIX_PROMPT = """You are a PostgreSQL performance expert. The previous optimization recommendation did NOT meet our goals. We need:
1. Eliminate Sequential Scans (use Index Scans instead)
2. Achieve at least 50% performance improvement

## Original Query:
```sql
{query}
```

## Current Table Structure (with indexes created so far):
{current_table_info}

## Previous Failed Recommendation:
- Type: {prev_type}
- Description: {prev_description}
- Optimized Query: {prev_query}
- Suggested Indexes: {prev_indexes}

## Execution Plan (still needs improvement):
```json
{plan}
```

---

The previous recommendation did NOT achieve our goals. Review the CURRENT TABLE STRUCTURE above to see what indexes already exist.

Provide a BETTER recommendation that will:
1. Eliminate Sequential Scans (force Index Scan usage)
2. Achieve 50%+ performance improvement

Consider:
1. The index might need different columns or column order
2. The query might need restructuring (avoid functions on indexed columns, fix data types)
3. PostgreSQL might need hints via query restructuring (LIMIT, subqueries, CTEs)
4. Statistics might be stale (suggest ANALYZE on the table)
5. The existing indexes might not match the WHERE clause columns exactly

CRITICAL INDEX RULES (MUST FOLLOW):
1. **ABSOLUTELY NEVER** use INCLUDE clause - it causes "index row size exceeds maximum" errors
2. **ONLY CREATE INDEX statements** in suggested_indexes - NO ALTER TABLE, NO CREATE TABLE
3. Do NOT include large columns (JSON, JSONB, TEXT, BYTEA) in indexes - they will fail
4. Use expression indexes: CREATE INDEX ... ON table((json_extract_path_text(col, 'key')))

WRONG (will fail):
- INCLUDE (fullobject) or INCLUDE (any_column) -- All INCLUDE clauses fail
- ALTER TABLE ... -- Not allowed

CORRECT:
- CREATE INDEX idx ON table(objecttypes_id, (json_extract_path_text(fullobject, 'startTime')))

Return your response as a valid JSON object with:
- "type": one of "index", "rewrite", or "config"
- "description": clear explanation of what this NEW optimization does
- "optimized_query": the rewritten query
- "suggested_indexes": array of CREATE INDEX statements ONLY (no ALTER TABLE, no INCLUDE clause)
- "expected_improvement": "high", "medium", or "low"
- "explanation": why this approach will eliminate the Sequential Scan
- "seq_scan_fix_reason": explain what was wrong with the previous approach

IMPORTANT: Return ONLY the JSON object, no additional text or markdown formatting.
"""


class AIClientError(Exception):
    """Raised when AI API call fails."""
    pass


class AIClient:
    """
    AI Client with automatic fallback: Gemini → DeepSeek → Groq
    If one provider fails, automatically tries the next available one.
    """
    
    PROVIDER_INFO = {
        'gemini': {'name': 'Google Gemini', 'color': '#4285F4'},
        'deepseek': {'name': 'DeepSeek', 'color': '#00D4AA'},
        'groq': {'name': 'Groq (Llama)', 'color': '#F55036'},
    }
    
    def __init__(self):
        """Initialize the AI client with available providers."""
        self.providers = []
        self._init_available_providers()
        
        if not self.providers:
            raise AIClientError("No AI provider configured. Set GEMINI_API_KEY, DEEPSEEK_API_KEY, or GROQ_API_KEY in .env")
    
    def _init_available_providers(self):
        """Initialize all available providers in priority order."""
        # Priority 1: Gemini (using new google.genai package)
        gemini_key = getattr(settings, 'GEMINI_API_KEY', '')
        if GENAI_AVAILABLE and gemini_key:
            self.providers.append({
                'name': 'gemini',
                'display_name': 'Google Gemini',
                'init': lambda: self._setup_gemini(gemini_key),
                'call': self._call_gemini,
            })
            logger.info("Gemini available as provider")
        
        # Priority 2: DeepSeek
        deepseek_key = getattr(settings, 'DEEPSEEK_API_KEY', '')
        if OPENAI_AVAILABLE and deepseek_key:
            self.providers.append({
                'name': 'deepseek',
                'display_name': 'DeepSeek V3',
                'init': lambda: self._setup_deepseek(deepseek_key),
                'call': self._call_deepseek,
            })
            logger.info("DeepSeek available as provider")
        
        # Priority 3: Groq
        groq_key = getattr(settings, 'GROQ_API_KEY', '')
        if GROQ_AVAILABLE and groq_key:
            self.providers.append({
                'name': 'groq',
                'display_name': 'Groq (Llama 3.3)',
                'init': lambda: self._setup_groq(groq_key),
                'call': self._call_groq,
            })
            logger.info("Groq available as provider")
    
    def _setup_gemini(self, api_key: str):
        """Setup Gemini client using new google.genai package."""
        self._gemini_client = genai.Client(api_key=api_key)
        self._gemini_model = getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')
    
    def _setup_deepseek(self, api_key: str):
        """Setup DeepSeek client."""
        self._deepseek_client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self._deepseek_model = "deepseek-chat"
    
    def _setup_groq(self, api_key: str):
        """Setup Groq client."""
        self._groq_client = Groq(api_key=api_key)
        self._groq_model = "llama-3.3-70b-versatile"
    
    def get_optimization_recommendations(
        self,
        query: str,
        plan: Dict[str, Any],
        execution_time: float,
        issues: List[str],
        table_info: Dict[str, Any] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Get optimization recommendations with automatic fallback.
        Tries each provider in order until one succeeds.
        """
        # Format table info for prompt
        table_info_str = self._format_table_info(table_info) if table_info else "No table information available"
        
        prompt = OPTIMIZATION_PROMPT.format(
            query=query,
            table_info=table_info_str,
            plan=json.dumps(plan, indent=2)[:4000],
            execution_time=execution_time,
            issues='\n'.join(f"- {issue}" for issue in issues) if issues else "No specific issues detected",
        )
        
        last_error = None
        
        for provider in self.providers:
            try:
                logger.info(f"Trying AI provider: {provider['name']}")
                
                # Initialize provider
                provider['init']()
                
                # Call provider
                recommendations = provider['call'](prompt, query)
                
                # Success! Return results with provider info
                provider_info = {
                    'provider': provider['name'],
                    'provider_name': provider['display_name'],
                    'model': self._get_model_name(provider['name']),
                    'color': self.PROVIDER_INFO.get(provider['name'], {}).get('color', '#666'),
                }
                
                logger.info(f"Successfully got recommendations from {provider['name']}")
                return recommendations, provider_info
                
            except Exception as e:
                last_error = e
                # Shorten verbose API errors (like Gemini quota errors)
                error_str = str(e)
                if len(error_str) > 150:
                    # Extract just the key part (error code/message)
                    if 'RESOURCE_EXHAUSTED' in error_str or '429' in error_str:
                        # Find retry delay if present
                        import re
                        retry_match = re.search(r'retry in (\d+\.?\d*)s', error_str, re.IGNORECASE)
                        retry_info = f", retry in {retry_match.group(1)}s" if retry_match else ""
                        error_str = f"429 Quota exceeded{retry_info}"
                    else:
                        error_str = error_str[:150] + "..."
                logger.warning(f"Provider {provider['name']} failed: {error_str}")
                # Continue to next provider
                continue
        
        # All providers failed
        raise AIClientError(f"All AI providers failed. Last error: {last_error}")
    
    def _format_table_info(self, table_info: Dict[str, Any]) -> str:
        """Format table info dictionary into a readable string for AI prompts."""
        if not table_info:
            return "No table information available"
        
        lines = []
        for table_name, info in table_info.items():
            if isinstance(info, dict) and 'error' not in info:
                lines.append(f"\n### Table: {table_name}")
                
                # Row count
                row_count = info.get('row_count', 0)
                lines.append(f"- Approximate rows: {row_count:,}")
                
                # Columns
                columns = info.get('columns', [])
                if columns:
                    lines.append("- Columns:")
                    for col in columns:
                        nullable = "NULL" if col.get('nullable') == 'YES' else "NOT NULL"
                        lines.append(f"  - {col['name']} ({col['type']}, {nullable})")
                
                # Existing indexes
                indexes = info.get('indexes', [])
                if indexes:
                    lines.append("- Existing Indexes:")
                    for idx in indexes:
                        lines.append(f"  - {idx['name']}: {idx['definition']}")
                else:
                    lines.append("- Existing Indexes: None")
        
        return '\n'.join(lines) if lines else "No table information available"
    
    def _get_model_name(self, provider: str) -> str:
        """Get the model name for a provider."""
        if provider == 'gemini':
            return getattr(self, '_gemini_model', 'gemini-2.0-flash')
        elif provider == 'deepseek':
            return getattr(self, '_deepseek_model', 'deepseek-chat')
        elif provider == 'groq':
            return getattr(self, '_groq_model', 'llama-3.3-70b-versatile')
        return 'unknown'
    
    def _call_gemini(self, prompt: str, original_query: str) -> List[Dict[str, Any]]:
        """Call Gemini API using new google.genai package."""
        response = self._gemini_client.models.generate_content(
            model=self._gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=4096,
            )
        )
        response_text = response.text.strip()
        return self._parse_response(response_text, original_query)
    
    def _call_deepseek(self, prompt: str, original_query: str) -> List[Dict[str, Any]]:
        """Call DeepSeek API."""
        response = self._deepseek_client.chat.completions.create(
            model=self._deepseek_model,
            messages=[
                {"role": "system", "content": "You are a PostgreSQL performance optimization expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        response_text = response.choices[0].message.content.strip()
        return self._parse_response(response_text, original_query)
    
    def _call_groq(self, prompt: str, original_query: str) -> List[Dict[str, Any]]:
        """Call Groq API."""
        response = self._groq_client.chat.completions.create(
            model=self._groq_model,
            messages=[
                {"role": "system", "content": "You are a PostgreSQL performance optimization expert. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        response_text = response.choices[0].message.content.strip()
        return self._parse_response(response_text, original_query)
    
    def _parse_response(self, response_text: str, original_query: str) -> List[Dict[str, Any]]:
        """Parse AI response into recommendations."""
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
        
        # Parse JSON
        try:
            recommendations = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {response_text[:500]}")
            raise AIClientError(f"Failed to parse AI response as JSON: {e}")
        
        if not isinstance(recommendations, list):
            raise AIClientError("Expected a list of recommendations")
        
        # Validate and normalize
        validated = []
        for i, rec in enumerate(recommendations[:3]):
            validated.append({
                'type': rec.get('type', 'rewrite'),
                'description': rec.get('description', 'No description provided'),
                'optimized_query': rec.get('optimized_query', original_query),
                'suggested_indexes': rec.get('suggested_indexes', []),
                'expected_improvement': rec.get('expected_improvement', 'medium'),
                'explanation': rec.get('explanation', ''),
                'rank': i + 1,
            })
        
        return validated
    
    def _parse_single_response(self, response_text: str, original_query: str) -> Dict[str, Any]:
        """Parse AI response for single recommendation (seq scan fix)."""
        # Clean up response - remove markdown code blocks if present
        if response_text.startswith('```'):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1].startswith('```') else lines[1:])
        
        # Parse JSON
        try:
            recommendation = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {response_text[:500]}")
            raise AIClientError(f"Failed to parse AI response as JSON: {e}")
        
        if not isinstance(recommendation, dict):
            raise AIClientError("Expected a single recommendation object")
        
        return {
            'type': recommendation.get('type', 'index'),
            'description': recommendation.get('description', 'No description provided'),
            'optimized_query': recommendation.get('optimized_query', original_query),
            'suggested_indexes': recommendation.get('suggested_indexes', []),
            'expected_improvement': recommendation.get('expected_improvement', 'high'),
            'explanation': recommendation.get('explanation', ''),
            'seq_scan_fix_reason': recommendation.get('seq_scan_fix_reason', ''),
        }
    
    def get_seq_scan_fix(
        self,
        query: str,
        previous_recommendation: Dict[str, Any],
        tested_plan: Dict[str, Any],
        current_table_info: Dict[str, Any] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, str]]:
        """
        Get a new recommendation to fix sequential scan issue.
        
        Args:
            query: Original SQL query
            previous_recommendation: The recommendation that still had seq scan
            tested_plan: The execution plan showing the seq scan
            current_table_info: Current table structure in temp schema (with indexes created so far)
            
        Returns:
            Tuple of (new_recommendation, provider_info)
        """
        # Format current table info
        current_table_info_str = self._format_table_info(current_table_info) if current_table_info else "Table structure not available"
        
        prompt = SEQ_SCAN_FIX_PROMPT.format(
            query=query,
            current_table_info=current_table_info_str,
            prev_type=previous_recommendation.get('type', 'unknown'),
            prev_description=previous_recommendation.get('description', ''),
            prev_query=previous_recommendation.get('optimized_query', query),
            prev_indexes=json.dumps(previous_recommendation.get('suggested_indexes', [])),
            plan=json.dumps(tested_plan, indent=2)[:4000],
        )
        
        last_error = None
        
        for provider in self.providers:
            try:
                logger.info(f"Trying AI provider for seq scan fix: {provider['name']}")
                
                # Initialize provider
                provider['init']()
                
                # Call provider with custom parsing
                if provider['name'] == 'gemini':
                    response = self._gemini_client.models.generate_content(
                        model=self._gemini_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            temperature=0.3,
                            max_output_tokens=4096,
                        )
                    )
                    response_text = response.text.strip()
                elif provider['name'] == 'deepseek':
                    response = self._deepseek_client.chat.completions.create(
                        model=self._deepseek_model,
                        messages=[
                            {"role": "system", "content": "You are a PostgreSQL performance optimization expert. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    response_text = response.choices[0].message.content.strip()
                elif provider['name'] == 'groq':
                    response = self._groq_client.chat.completions.create(
                        model=self._groq_model,
                        messages=[
                            {"role": "system", "content": "You are a PostgreSQL performance optimization expert. Always respond with valid JSON only."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,
                        max_tokens=4096,
                    )
                    response_text = response.choices[0].message.content.strip()
                else:
                    continue
                
                recommendation = self._parse_single_response(response_text, query)
                
                provider_info = {
                    'provider': provider['name'],
                    'provider_name': provider['display_name'],
                    'model': self._get_model_name(provider['name']),
                    'color': self.PROVIDER_INFO.get(provider['name'], {}).get('color', '#666'),
                }
                
                logger.info(f"Successfully got seq scan fix from {provider['name']}")
                return recommendation, provider_info
                
            except Exception as e:
                last_error = e
                # Shorten verbose API errors
                error_str = str(e)
                if len(error_str) > 150:
                    if 'RESOURCE_EXHAUSTED' in error_str or '429' in error_str:
                        import re
                        retry_match = re.search(r'retry in (\d+\.?\d*)s', error_str, re.IGNORECASE)
                        retry_info = f", retry in {retry_match.group(1)}s" if retry_match else ""
                        error_str = f"429 Quota exceeded{retry_info}"
                    else:
                        error_str = error_str[:150] + "..."
                logger.warning(f"Provider {provider['name']} failed: {error_str}")
                continue
        
        raise AIClientError(f"All AI providers failed for seq scan fix. Last error: {last_error}")


# Backward compatibility aliases
GeminiClient = AIClient
GeminiClientError = AIClientError
