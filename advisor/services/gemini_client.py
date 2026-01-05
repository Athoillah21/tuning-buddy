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

## Current Execution Plan:
```json
{plan}
```

## Execution Time: {execution_time}ms

## Current Issues Detected:
{issues}

---

Provide exactly 3 optimization recommendations with different approaches. Each recommendation should be practical and testable.

Return your response as a valid JSON array with exactly 3 objects. Each object must have:
- "type": one of "index", "rewrite", or "config"
- "description": clear explanation of what this optimization does and why it helps
- "optimized_query": the rewritten query (can be same as original if only index changes)
- "suggested_indexes": array of CREATE INDEX statements (empty array if not applicable)
- "expected_improvement": "high", "medium", or "low"
- "explanation": technical explanation of why this helps

IMPORTANT: Return ONLY the JSON array, no additional text or markdown formatting.
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
        prompt = OPTIMIZATION_PROMPT.format(
            query=query,
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
                logger.warning(f"Provider {provider['name']} failed: {e}")
                # Continue to next provider
                continue
        
        # All providers failed
        raise AIClientError(f"All AI providers failed. Last error: {last_error}")
    
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


# Backward compatibility aliases
GeminiClient = AIClient
GeminiClientError = AIClientError
