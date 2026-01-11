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
    
    def execute_explain_analyze(self, query: str, timeout_ms: int = 300000) -> Dict[str, Any]:
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
    
    def get_schema_table_info(self, schema_name: str, table_name: str) -> Dict[str, Any]:
        """
        Get information about a table in a specific schema including columns, indexes, and row count.
        Useful for getting temp table structure.
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Get column info for specific schema
                    cur.execute("""
                        SELECT column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                        ORDER BY ordinal_position;
                    """, (schema_name, table_name))
                    columns = cur.fetchall()
                    
                    # Get index info for specific schema
                    cur.execute("""
                        SELECT indexname, indexdef
                        FROM pg_indexes
                        WHERE schemaname = %s AND tablename = %s;
                    """, (schema_name, table_name))
                    indexes = cur.fetchall()
                    
                    # Get approximate row count
                    cur.execute("""
                        SELECT reltuples::bigint
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = %s AND c.relname = %s;
                    """, (schema_name, table_name))
                    row_count = cur.fetchone()
                    
                    return {
                        'table': f"{schema_name}.{table_name}",
                        'columns': [{'name': c[0], 'type': c[1], 'nullable': c[2]} for c in columns],
                        'indexes': [{'name': i[0], 'definition': i[1]} for i in indexes],
                        'row_count': row_count[0] if row_count else 0,
                    }
        except Exception as e:
            logger.error(f"Error getting schema table info: {e}")
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
    
    def clone_table_to_schema(self, source_table: str, target_schema: str, source_schema: str = None, limit: int = None) -> bool:
        """
        Clone a table's structure and data to a temp schema.
        Uses LIKE ... INCLUDING STORAGE to preserve TOAST settings for large columns.
        
        Args:
            source_table: Name of the table to clone (without schema prefix)
            target_schema: Target schema name
            source_schema: Source schema name (e.g., 'openidm'). If None, assumes public.
            limit: Optional row limit. If None, copies ALL data for realistic testing.
        """
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    # Build source table reference
                    if source_schema:
                        source_ref = f'"{source_schema}"."{source_table}"'
                    else:
                        source_ref = f'"{source_table}"'
                    
                    target_ref = f'"{target_schema}"."{source_table}"'
                    
                    # Step 1: Create table structure with storage settings
                    # Use INCLUDING DEFAULTS INCLUDING STORAGE (not ALL to avoid generated columns)
                    cur.execute(f"""
                        CREATE TABLE {target_ref} (
                            LIKE {source_ref} INCLUDING DEFAULTS INCLUDING STORAGE
                        )
                    """)
                    
                    # Step 2: Get non-generated columns for INSERT
                    cur.execute("""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_schema = %s 
                          AND table_name = %s 
                          AND is_generated = 'NEVER'
                        ORDER BY ordinal_position
                    """, (source_schema or 'public', source_table))
                    columns = [row[0] for row in cur.fetchall()]
                    
                    if columns:
                        cols_str = ', '.join(f'"{c}"' for c in columns)
                        
                        # Step 3: Insert data (with optional limit)
                        if limit:
                            cur.execute(f"""
                                INSERT INTO {target_ref} ({cols_str})
                                SELECT {cols_str} FROM {source_ref} LIMIT %s
                            """, (limit,))
                        else:
                            cur.execute(f"""
                                INSERT INTO {target_ref} ({cols_str})
                                SELECT {cols_str} FROM {source_ref}
                            """)
                    
                    return True
        except Exception as e:
            logger.error(f"Error cloning table: {e}")
            return False
    
    def create_index_on_temp(self, schema_name: str, index_statement: str, source_tables: list = None) -> bool:
        """
        Create an index on a temp schema table.
        Modifies the index statement to use the temp schema.
        
        Args:
            schema_name: Temp schema name
            index_statement: CREATE INDEX statement (may have original schema like openidm.tablename)
            source_tables: List of original table references to replace (e.g., ['openidm.genericobjects'])
        """
        try:
            with self.get_connection() as conn:
                conn.autocommit = True
                with conn.cursor() as cur:
                    modified_statement = index_statement
                    
                    # Replace any schema-qualified table names with temp schema
                    if source_tables:
                        for table in source_tables:
                            if '.' in table:
                                original_schema, table_name = table.split('.', 1)
                                # Replace original schema reference with temp schema
                                modified_statement = modified_statement.replace(
                                    f"{original_schema}.{table_name}", f"{schema_name}.{table_name}"
                                )
                                # Also handle just table name after ON
                                modified_statement = modified_statement.replace(
                                    f" ON {table_name}", f" ON {schema_name}.{table_name}"
                                )
                    else:
                        # Fallback: Just add schema to ON clause if not already qualified
                        if " ON " in modified_statement and f" ON {schema_name}." not in modified_statement:
                            # Check if it's already schema-qualified
                            import re
                            # Match "ON schema.table" or "ON table"
                            on_match = re.search(r' ON\s+(\w+)\.(\w+)', modified_statement)
                            if on_match:
                                # Already has a schema, replace it
                                old_ref = f"{on_match.group(1)}.{on_match.group(2)}"
                                new_ref = f"{schema_name}.{on_match.group(2)}"
                                modified_statement = modified_statement.replace(old_ref, new_ref)
                            else:
                                # No schema, add temp schema
                                modified_statement = modified_statement.replace(" ON ", f" ON {schema_name}.")
                    
                    logger.info(f"Creating index on temp table - modified: {modified_statement[:200]}...")
                    cur.execute(modified_statement)
                    return True
        except Exception as e:
            logger.error(f"Error creating index: {e}")
            logger.error(f"Original statement: {index_statement[:200]}...")
            logger.error(f"Modified statement: {modified_statement[:200]}...")
            return False
