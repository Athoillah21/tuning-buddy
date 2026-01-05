"""
Optimizer service that orchestrates the query optimization process.
Tests recommendations using temporary tables and compares execution times.
"""
import uuid
import logging
from typing import List, Dict, Any
from django.conf import settings

from .db_connector import DBConnector, DatabaseConnectionError
from .query_analyzer import QueryValidator, ExecutionPlanAnalyzer
from .gemini_client import GeminiClient, GeminiClientError

logger = logging.getLogger(__name__)


class OptimizationError(Exception):
    """Raised when optimization process fails."""
    pass


class QueryOptimizer:
    """
    Orchestrates the full query optimization workflow:
    1. Analyze original query
    2. Get recommendations from Gemini
    3. Test recommendations using temp tables
    4. Compare and rank results
    """
    
    def __init__(self, connection_params: Dict[str, Any]):
        """
        Initialize the optimizer.
        
        Args:
            connection_params: Database connection parameters
        """
        self.db = DBConnector(connection_params)
        self.gemini = GeminiClient()
        self.temp_schema = None
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Full analysis of a query including validation, execution, and plan analysis.
        
        Args:
            query: SQL query to analyze
            
        Returns:
            Dict with analysis results
        """
        # Step 1: Validate query
        validation = QueryValidator.validate(query)
        if not validation['is_valid']:
            return {
                'success': False,
                'stage': 'validation',
                'errors': validation['errors'],
            }
        
        # Step 2: Execute EXPLAIN ANALYZE
        result = self.db.execute_explain_analyze(
            query,
            timeout_ms=settings.QUERY_EXECUTION_TIMEOUT * 1000
        )
        
        if not result['success']:
            return {
                'success': False,
                'stage': 'execution',
                'error': result.get('error', 'Unknown error'),
            }
        
        # Step 3: Analyze the execution plan
        plan = result['plan']
        analysis = ExecutionPlanAnalyzer.analyze_plan(plan)
        
        # Step 4: Extract table info
        tables = QueryValidator.extract_tables(query)
        table_info = {}
        for table in tables:
            table_info[table] = self.db.get_table_info(table)
        
        return {
            'success': True,
            'query': query,
            'plan': plan,
            'execution_time': result['execution_time'],
            'planning_time': result['planning_time'],
            'analysis': analysis,
            'table_info': table_info,
            'warnings': validation.get('warnings', []),
        }
    
    def get_recommendations(self, analysis_result: Dict[str, Any]) -> tuple:
        """
        Get optimization recommendations from AI.
        
        Args:
            analysis_result: Result from analyze_query()
            
        Returns:
            Tuple of (recommendations, provider_info)
        """
        if not analysis_result.get('success'):
            raise OptimizationError("Cannot get recommendations for failed analysis")
        
        try:
            recommendations, provider_info = self.gemini.get_optimization_recommendations(
                query=analysis_result['query'],
                plan=analysis_result['plan'],
                execution_time=analysis_result['execution_time'],
                issues=analysis_result['analysis'].get('issues', []),
                table_info=analysis_result.get('table_info'),
            )
            return recommendations, provider_info
        except GeminiClientError as e:
            raise OptimizationError(f"Failed to get recommendations: {e}")
    
    def test_recommendation(
        self,
        original_query: str,
        recommendation: Dict[str, Any],
        tables: List[str]
    ) -> Dict[str, Any]:
        """
        Test a single recommendation using temp tables.
        
        Args:
            original_query: The original query
            recommendation: Recommendation dict from Gemini
            tables: List of tables used in the query
            
        Returns:
            Dict with test results
        """
        # Generate unique schema name
        schema_name = f"temp_test_{uuid.uuid4().hex[:8]}"
        
        try:
            # Create temp schema
            if not self.db.create_temp_schema(schema_name):
                return {
                    'success': False,
                    'error': 'Failed to create temp schema',
                }
            
            # Clone tables
            for table in tables:
                # Remove schema prefix if present
                table_name = table.split('.')[-1]
                if not self.db.clone_table_to_schema(table_name, schema_name):
                    logger.warning(f"Failed to clone table {table_name}")
            
            # Create suggested indexes
            for index_stmt in recommendation.get('suggested_indexes', []):
                if not self.db.create_index_on_temp(schema_name, index_stmt):
                    logger.warning(f"Failed to create index: {index_stmt}")
            
            # Modify query to use temp schema
            test_query = recommendation.get('optimized_query', original_query)
            for table in tables:
                table_name = table.split('.')[-1]
                # Simple replacement - might need more sophisticated handling
                test_query = test_query.replace(
                    f" {table_name} ",
                    f" {schema_name}.{table_name} "
                ).replace(
                    f" {table_name}\n",
                    f" {schema_name}.{table_name}\n"
                ).replace(
                    f" {table_name};",
                    f" {schema_name}.{table_name};"
                )
            
            # Execute EXPLAIN ANALYZE on optimized query
            result = self.db.execute_explain_analyze(test_query)
            
            return {
                'success': result['success'],
                'execution_time': result.get('execution_time', 0),
                'planning_time': result.get('planning_time', 0),
                'plan': result.get('plan'),
                'error': result.get('error'),
            }
            
        except Exception as e:
            logger.error(f"Error testing recommendation: {e}")
            return {
                'success': False,
                'error': str(e),
            }
        finally:
            # Always cleanup
            self.db.drop_temp_schema(schema_name)
    
    def optimize(self, query: str, test_recommendations: bool = True) -> Dict[str, Any]:
        """
        Full optimization workflow.
        
        Args:
            query: SQL query to optimize
            test_recommendations: Whether to test recommendations with temp tables
            
        Returns:
            Complete optimization results
        """
        # Step 1: Analyze original query
        analysis = self.analyze_query(query)
        if not analysis['success']:
            return analysis
        
        # Step 2: Get recommendations from AI
        try:
            recommendations, provider_info = self.get_recommendations(analysis)
        except OptimizationError as e:
            return {
                'success': False,
                'stage': 'recommendations',
                'error': str(e),
                'analysis': analysis,
            }
        
        # Step 3: Test recommendations (if enabled)
        if test_recommendations:
            tables = QueryValidator.extract_tables(query)
            for rec in recommendations:
                test_result = self.test_recommendation(query, rec, tables)
                rec['test_result'] = test_result
                
                if test_result['success']:
                    original_time = analysis['execution_time']
                    tested_time = test_result['execution_time']
                    if original_time > 0:
                        improvement = ((original_time - tested_time) / original_time) * 100
                        rec['improvement_percentage'] = round(improvement, 2)
                        rec['tested_execution_time'] = tested_time
        
        # Step 4: Rank recommendations by improvement
        recommendations.sort(
            key=lambda r: r.get('improvement_percentage', 0),
            reverse=True
        )
        for i, rec in enumerate(recommendations):
            rec['rank'] = i + 1
        
        return {
            'success': True,
            'original_query': query,
            'original_execution_time': analysis['execution_time'],
            'original_plan': analysis['plan'],
            'analysis': analysis['analysis'],
            'recommendations': recommendations,
            'tables_analyzed': list(analysis.get('table_info', {}).keys()),
            'ai_provider': provider_info,
        }
