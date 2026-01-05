"""
Database models for the Query Tuning Advisor.
Stores database connections, query history, and recommendations.
"""
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import json


class EncryptedFieldMixin:
    """Mixin for encrypting/decrypting field values."""
    
    @staticmethod
    def encrypt(value: str) -> str:
        """Encrypt a string value."""
        if not value or not settings.ENCRYPTION_KEY:
            return value
        try:
            f = Fernet(settings.ENCRYPTION_KEY.encode())
            return f.encrypt(value.encode()).decode()
        except Exception:
            return value
    
    @staticmethod
    def decrypt(value: str) -> str:
        """Decrypt an encrypted string value."""
        if not value or not settings.ENCRYPTION_KEY:
            return value
        try:
            f = Fernet(settings.ENCRYPTION_KEY.encode())
            return f.decrypt(value.encode()).decode()
        except Exception:
            return value


class Connection(models.Model, EncryptedFieldMixin):
    """
    Stores PostgreSQL database connection details.
    Sensitive fields (host, username, password) are encrypted.
    """
    SSL_MODES = [
        ('disable', 'Disable'),
        ('allow', 'Allow'),
        ('prefer', 'Prefer'),
        ('require', 'Require'),
        ('verify-ca', 'Verify CA'),
        ('verify-full', 'Verify Full'),
    ]
    
    name = models.CharField(max_length=100, help_text="Friendly name for this connection")
    host = models.TextField(help_text="Database host (encrypted)")
    port = models.IntegerField(default=5432)
    database = models.CharField(max_length=100)
    username = models.TextField(help_text="Database username (encrypted)")
    password = models.TextField(help_text="Database password (encrypted)")
    ssl_mode = models.CharField(max_length=20, choices=SSL_MODES, default='prefer')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"{self.name} ({self.database})"
    
    def save(self, *args, **kwargs):
        """Encrypt sensitive fields before saving."""
        # Only encrypt if the value appears to be plain text
        if self.host and not self.host.startswith('gAAAAA'):
            self.host = self.encrypt(self.host)
        if self.username and not self.username.startswith('gAAAAA'):
            self.username = self.encrypt(self.username)
        if self.password and not self.password.startswith('gAAAAA'):
            self.password = self.encrypt(self.password)
        super().save(*args, **kwargs)
    
    def get_decrypted_host(self) -> str:
        return self.decrypt(self.host)
    
    def get_decrypted_username(self) -> str:
        return self.decrypt(self.username)
    
    def get_decrypted_password(self) -> str:
        return self.decrypt(self.password)
    
    def get_connection_params(self) -> dict:
        """Return decrypted connection parameters for psycopg2."""
        return {
            'host': self.get_decrypted_host(),
            'port': self.port,
            'database': self.database,
            'user': self.get_decrypted_username(),
            'password': self.get_decrypted_password(),
            'sslmode': self.ssl_mode,
            'connect_timeout': settings.DB_CONNECTION_TIMEOUT,
        }


class QueryHistory(models.Model):
    """
    Stores the history of analyzed queries.
    """
    connection = models.ForeignKey(Connection, on_delete=models.CASCADE, related_name='queries')
    original_query = models.TextField(help_text="The original SQL query")
    original_plan = models.JSONField(null=True, blank=True, help_text="EXPLAIN ANALYZE output as JSON")
    original_execution_time = models.FloatField(null=True, blank=True, help_text="Execution time in milliseconds")
    ai_provider = models.JSONField(null=True, blank=True, help_text="AI provider used for recommendations")
    analysis_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('analyzing', 'Analyzing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending'
    )
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Query histories'
    
    def __str__(self):
        return f"Query #{self.id} - {self.original_query[:50]}..."


class Recommendation(models.Model):
    """
    Stores optimization recommendations from Gemini.
    """
    RECOMMENDATION_TYPES = [
        ('index', 'Add Index'),
        ('rewrite', 'Query Rewrite'),
        ('config', 'Configuration Change'),
        ('schema', 'Schema Change'),
    ]
    
    query_history = models.ForeignKey(QueryHistory, on_delete=models.CASCADE, related_name='recommendations')
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPES)
    description = models.TextField(help_text="Explanation of the optimization")
    optimized_query = models.TextField(null=True, blank=True, help_text="Rewritten query if applicable")
    suggested_indexes = models.JSONField(default=list, help_text="List of CREATE INDEX statements")
    tested_execution_time = models.FloatField(null=True, blank=True, help_text="Tested execution time in ms")
    improvement_percentage = models.FloatField(null=True, blank=True)
    rank = models.IntegerField(default=0, help_text="Ranking by improvement")
    gemini_raw_response = models.JSONField(null=True, blank=True, help_text="Raw Gemini response for debugging")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['rank']
    
    def __str__(self):
        return f"Recommendation #{self.id} - {self.recommendation_type}"
    
    def calculate_improvement(self, original_time: float):
        """Calculate improvement percentage based on original execution time."""
        if original_time and self.tested_execution_time and original_time > 0:
            improvement = ((original_time - self.tested_execution_time) / original_time) * 100
            self.improvement_percentage = round(improvement, 2)
            self.save(update_fields=['improvement_percentage'])
