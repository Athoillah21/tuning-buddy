"""
Database connection manager for connecting to user's PostgreSQL databases.
Handles connection pooling and secure credential retrieval.
"""
import psycopg2
from psycopg2 import sql, errors
from contextlib import contextmanager
from typing import Optional, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails."""
    pass


class QueryExecutionError(Exception):
    """Raised when query execution fails."""
    pass


class DBConnector:
    """
    Manages connections to user's PostgreSQL databases.
    Uses context manager pattern for safe connection handling.
    """
    
    def __init__(self, connection_params: Dict[str, Any]):
        """
        Initialize with connection parameters.
        
        Args:
            connection_params: Dict with host, port, database, user, password, sslmode
        """
        self.connection_params = connection_params
        self._conn = None
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        Ensures connections are properly closed.
        """
        conn = None
        try:
            conn = psycopg2.connect(**self.connection_params)
            yield conn
        except psycopg2.OperationalError as e:
            error_msg = str(e)
            if 'timeout' in error_msg.lower():
                raise DatabaseConnectionError(f"Connection timeout: {error_msg}")
            elif 'authentication' in error_msg.lower():
                raise DatabaseConnectionError(f"Authentication failed: Invalid username or password")
            elif 'could not connect' in error_msg.lower():
                raise DatabaseConnectionError(f"Could not connect to host: {error_msg}")
            else:
                raise DatabaseConnectionError(f"Connection error: {error_msg}")
        except Exception as e:
            raise DatabaseConnectionError(f"Unexpected error: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def test_connection(self) -> Tuple[bool, str]:
        """
        Test if the connection can be established.
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    return True, f"Connected successfully!\nPostgreSQL: {version}"
        except DatabaseConnectionError as e:
            return False, str(e)
        except Exception as e:
            return False, f"Test failed: {str(e)}"
    
    def execute_explain_analyze(self, query: str, timeout_ms: int = 8000) -> Dict[str, Any]:
        """
        Execute EXPLAIN ANALYZE on a query and return the plan.
        
        Args:
            query: SQL query to analyze
            timeout_ms: Statement timeout in milliseconds
            
        Returns:
            Dict containing execution plan and metrics
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Set statement timeout
                    cur.execute(f"SET statement_timeout = {timeout_ms};")
                    
                    # Run EXPLAIN ANALYZE with JSON output
                    explain_query = f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {query}"
                    cur.execute(explain_query)
                    
                    result = cur.fetchone()[0]
                    
                    # Extract key metrics
                    plan = result[0] if result else {}
                    execution_time = plan.get('Execution Time', 0)
                    planning_time = plan.get('Planning Time', 0)
                    
                    return {
                        'success': True,
                        'plan': plan,
                        'execution_time': execution_time,
                        'planning_time': planning_time,
                        'total_time': execution_time + planning_time,
                    }
                    
        except errors.QueryCanceled:
            return {
                'success': False,
                'error': f'Query exceeded timeout of {timeout_ms}ms',
            }
        except psycopg2.Error as e:
            return {
                'success': False,
                'error': f'Query execution error: {str(e)}',
            }
        except Exception as e:
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
            }
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """
        Get information about a table including columns, indexes, and row count.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get column info
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = %s
                        ORDER BY ordinal_position;
                    """, (table_name,))
                    columns = cur.fetchall()
                    
                    # Get index info
                    cur.execute("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE tablename = %s;
                    """, (table_name,))
                    indexes = cur.fetchall()
                    
                    # Get approximate row count
                    cur.execute("""
                        SELECT reltuples::bigint
                        FROM pg_class
                        WHERE relname = %s;
                    """, (table_name,))
                    row_count = cur.fetchone()
                    
                    return {
                        'columns': [{'name': c[0], 'type': c[1], 'nullable': c[2]} for c in columns],
                        'indexes': [{'name': i[0], 'definition': i[1]} for i in indexes],
                        'row_count': row_count[0] if row_count else 0,
                    }
        except Exception as e:
            logger.error(f"Error getting table info: {e}")
            return {'error': str(e)}
    
    def create_temp_schema(self, schema_name: str) -> bool:
        """Create a temporary schema for testing optimizations."""
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(
                        sql.Identifier(schema_name)
                    ))
                    return True
        except Exception as e:
            logger.error(f"Error creating temp schema: {e}")
            return False
    
    def drop_temp_schema(self, schema_name: str) -> bool:
        """Drop a temporary schema and all its contents."""
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    cur.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                        sql.Identifier(schema_name)
                    ))
                    return True
        except Exception as e:
            logger.error(f"Error dropping temp schema: {e}")
            return False
    
    def clone_table_to_schema(self, source_table: str, target_schema: str, limit: int = 10000) -> bool:
        """
        Clone a table's structure and sample data to a temp schema.
        """
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Create table with data sample
                    target_table = f"{target_schema}.{source_table}"
                    cur.execute(sql.SQL("""
                        CREATE TABLE {} AS
                        SELECT * FROM {} LIMIT %s
                    """).format(
                        sql.Identifier(target_schema, source_table),
                        sql.Identifier(source_table)
                    ), (limit,))
                    return True
        except Exception as e:
            logger.error(f"Error cloning table: {e}")
            return False
    
    def create_index_on_temp(self, schema_name: str, index_statement: str) -> bool:
        """
        Create an index on a temp schema table.
        Modifies the index statement to use the temp schema.
        """
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Modify index statement to use temp schema
                    # This is a simplified approach
                    modified_statement = index_statement.replace(
                        "CREATE INDEX", f"CREATE INDEX"
                    ).replace(" ON ", f" ON {schema_name}.")
                    cur.execute(modified_statement)
                    return True
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            return False
