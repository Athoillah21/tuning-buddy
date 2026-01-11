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
                # Clone full dataset for realistic performance testing
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
    
    def optimize(self, query: str, test_recommendations: bool = True, max_seq_scan_attempts: int = 5) -> Dict[str, Any]:
        """
        Full optimization workflow with iterative seq scan elimination.
        
        Args:
            query: SQL query to optimize
            test_recommendations: Whether to test recommendations with temp tables
            max_seq_scan_attempts: Maximum attempts to eliminate seq scans per recommendation
            
        Returns:
            Complete optimization results
        """
        # Step 1: Analyze original query
        analysis = self.analyze_query(query)
        if not analysis['success']:
            return analysis
        
        # Check if original query has seq scan (we need to eliminate it)
        original_has_seq_scan = ExecutionPlanAnalyzer.has_seq_scan(analysis['plan'])
        
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
            total_recs = len(recommendations)
            
            for rec_index, rec in enumerate(recommendations, 1):
                rec_type = rec.get('type', 'unknown')
                logger.info(f"=== Testing Recommendation {rec_index}/{total_recs}: {rec_type.upper()} ===")
                
                current_rec = rec
                attempt = 0
                optimization_history = []
                schema_name = None
                all_indexes_created = []  # Track ALL indexes across iterations
                final_optimized_query = rec.get('optimized_query', query)  # Track final query
                
                try:
                    while attempt < max_seq_scan_attempts:
                        attempt += 1
                        logger.info(f"Recommendation {rec_index}/{total_recs}: Attempt {attempt}/{max_seq_scan_attempts}")
                        
                        # For first attempt, create new schema; for subsequent, reuse
                        if schema_name is None:
                            schema_name = f"temp_test_{uuid.uuid4().hex[:8]}"
                            if not self.db.create_temp_schema(schema_name):
                                break
                            # Clone tables - handle schema-qualified names like openidm.genericobjects
                            for table in tables:
                                if '.' in table:
                                    source_schema, table_name = table.split('.', 1)
                                else:
                                    source_schema, table_name = None, table
                                self.db.clone_table_to_schema(table_name, schema_name, source_schema=source_schema)
                        
                        # Create suggested indexes (accumulates over iterations)
                        for index_stmt in current_rec.get('suggested_indexes', []):
                            if index_stmt not in all_indexes_created:  # Avoid duplicates
                                if self.db.create_index_on_temp(schema_name, index_stmt, source_tables=tables):
                                    all_indexes_created.append(index_stmt)
                                else:
                                    logger.warning(f"Failed to create index: {index_stmt}")
                        
                        # Track the current optimized query
                        final_optimized_query = current_rec.get('optimized_query', final_optimized_query)
                        
                        # Modify query to use temp schema
                        test_query = current_rec.get('optimized_query', query)
                        for table in tables:
                            # Handle schema-qualified names: replace "schema.table" with "temp_schema.table"
                            if '.' in table:
                                original_schema, table_name = table.split('.', 1)
                                # Replace schema-qualified reference
                                test_query = test_query.replace(
                                    f"{original_schema}.{table_name}", f"{schema_name}.{table_name}"
                                )
                            else:
                                table_name = table
                                # Replace non-qualified references
                                test_query = test_query.replace(
                                    f" {table_name} ", f" {schema_name}.{table_name} "
                                ).replace(
                                    f" {table_name}\n", f" {schema_name}.{table_name}\n"
                                ).replace(
                                    f" {table_name};", f" {schema_name}.{table_name};"
                                )
                        
                        # Execute EXPLAIN ANALYZE
                        result = self.db.execute_explain_analyze(test_query)
                        test_result = {
                            'success': result['success'],
                            'execution_time': result.get('execution_time', 0),
                            'planning_time': result.get('planning_time', 0),
                            'plan': result.get('plan'),
                            'error': result.get('error'),
                        }
                        
                        if not test_result['success']:
                            break
                        
                        tested_plan = test_result.get('plan', {})
                        still_has_seq_scan = ExecutionPlanAnalyzer.has_seq_scan(tested_plan)
                        
                        # Calculate improvement percentage
                        tested_time = test_result.get('execution_time', 0)
                        original_time = analysis['execution_time']
                        if original_time > 0:
                            improvement = ((original_time - tested_time) / original_time) * 100
                        else:
                            improvement = 0
                        
                        # Check if we need to iterate:
                        # 1. Still has seq scan (if original had one)
                        # 2. Improvement is less than 50%
                        needs_seq_scan_fix = original_has_seq_scan and still_has_seq_scan
                        needs_more_improvement = improvement < 50
                        
                        if (needs_seq_scan_fix or needs_more_improvement) and attempt < max_seq_scan_attempts:
                            reason = []
                            if needs_seq_scan_fix:
                                reason.append("still has seq scan")
                            if needs_more_improvement:
                                reason.append(f"only {improvement:.1f}% improvement (need 50%+)")
                            
                            logger.info(f"Recommendation needs improvement: {', '.join(reason)}, attempt {attempt}/{max_seq_scan_attempts}")
                            
                            # Get current temp table structure for the AI
                            current_table_info = {}
                            for table in tables:
                                table_name = table.split('.')[-1]
                                info = self.db.get_schema_table_info(schema_name, table_name)
                                current_table_info[table_name] = info
                            
                            # Record this attempt
                            optimization_history.append({
                                'attempt': attempt,
                                'recommendation': {
                                    'type': current_rec.get('type'),
                                    'description': current_rec.get('description'),
                                    'suggested_indexes': current_rec.get('suggested_indexes', []),
                                },
                                'still_has_seq_scan': still_has_seq_scan,
                                'improvement_percentage': round(improvement, 2),
                                'reason': reason,
                            })
                            
                            # Ask AI for a fix with current table structure
                            try:
                                new_rec, _ = self.gemini.get_seq_scan_fix(
                                    query=query,
                                    previous_recommendation=current_rec,
                                    tested_plan=tested_plan,
                                    current_table_info=current_table_info,
                                )
                                # Update current_rec with the fix
                                current_rec = {**current_rec, **new_rec}
                                current_rec['seq_scan_fix_attempt'] = attempt
                            except Exception as e:
                                logger.warning(f"Failed to get seq scan fix: {e}")
                                break
                        else:
                            # Goals met: no seq scan (or wasn't issue) AND 50%+ improvement, or max attempts
                            if improvement >= 50 and not needs_seq_scan_fix:
                                logger.info(f"✓ Recommendation {rec_index}/{total_recs}: Goals MET at attempt {attempt} - {improvement:.1f}% improvement")
                            else:
                                logger.info(f"Recommendation {rec_index}/{total_recs}: Max attempts reached at attempt {attempt}")
                            break
                finally:
                    # Always cleanup temp schema
                    if schema_name:
                        self.db.drop_temp_schema(schema_name)
                
                # Store final results in the recommendation
                rec.update(current_rec)
                rec['test_result'] = test_result
                rec['optimization_attempts'] = attempt
                rec['optimization_history'] = optimization_history
                rec['seq_scan_eliminated'] = original_has_seq_scan and not ExecutionPlanAnalyzer.has_seq_scan(test_result.get('plan', {}))
                
                # Store accumulated results for the report
                rec['all_indexes_applied'] = all_indexes_created  # All indexes that were successfully created
                rec['final_optimized_query'] = final_optimized_query  # The final query after all iterations
                rec['original_query'] = query  # Keep original for comparison
                rec['query_was_rewritten'] = final_optimized_query != query  # Flag if query changed
                
                if test_result['success']:
                    original_time = analysis['execution_time']
                    tested_time = test_result['execution_time']
                    if original_time > 0:
                        improvement = ((original_time - tested_time) / original_time) * 100
                        rec['improvement_percentage'] = round(improvement, 2)
                        rec['tested_execution_time'] = tested_time
        
        # Step 4: Rank recommendations by improvement (prioritize seq_scan_eliminated)
        recommendations.sort(
            key=lambda r: (
                r.get('seq_scan_eliminated', False),  # Priority 1: eliminated seq scan
                r.get('improvement_percentage', 0),   # Priority 2: performance improvement
            ),
            reverse=True
        )
        for i, rec in enumerate(recommendations):
            rec['rank'] = i + 1
        
        return {
            'success': True,
            'original_query': query,
            'original_execution_time': analysis['execution_time'],
            'original_plan': analysis['plan'],
            'original_has_seq_scan': original_has_seq_scan,
            'analysis': analysis['analysis'],
            'recommendations': recommendations,
            'tables_analyzed': list(analysis.get('table_info', {}).keys()),
            'ai_provider': provider_info,
        }
