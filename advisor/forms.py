"""
Forms for the Query Tuning Advisor.
"""
from django import forms
from .models import Connection


class ConnectionForm(forms.ModelForm):
    """Form for creating/editing database connections."""
    
    # Override password to use PasswordInput
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Database password',
            'autocomplete': 'new-password',
        }),
        required=True,
    )
    
    class Meta:
        model = Connection
        fields = ['name', 'host', 'port', 'database', 'username', 'password', 'ssl_mode']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'My Production DB',
            }),
            'host': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'db.example.com or IP address',
            }),
            'port': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '5432',
            }),
            'database': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'database_name',
            }),
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'postgres',
            }),
            'ssl_mode': forms.Select(attrs={
                'class': 'form-select',
            }),
        }


class QueryForm(forms.Form):
    """Form for submitting queries for analysis."""
    
    query = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-textarea code-editor',
            'placeholder': 'Enter your SQL query here...\n\nExample:\nSELECT * FROM users WHERE email = \'test@example.com\';',
            'rows': 10,
            'spellcheck': 'false',
        }),
        required=True,
        help_text='Enter a SELECT query to analyze. Only SELECT and WITH (CTE) queries are supported.',
    )
    
    test_recommendations = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-checkbox',
        }),
        help_text='Test recommendations using temporary tables (may take longer)',
    )
    
    def clean_query(self):
        query = self.cleaned_data['query'].strip()
        if not query:
            raise forms.ValidationError('Query cannot be empty')
        return query
