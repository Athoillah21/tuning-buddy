"""
Views for the Query Tuning Advisor.
"""
import json
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

from .models import Connection, QueryHistory, Recommendation
from .forms import ConnectionForm, QueryForm
from .services.db_connector import DBConnector, DatabaseConnectionError
from .services.optimizer import QueryOptimizer, OptimizationError

logger = logging.getLogger(__name__)


def home(request):
    """Home page - shows connections and recent queries."""
    connections = Connection.objects.all()[:5]
    recent_queries = QueryHistory.objects.select_related('connection')[:5]
    
    return render(request, 'advisor/home.html', {
        'connections': connections,
        'recent_queries': recent_queries,
    })


def connection_list(request):
    """List all saved connections."""
    connections = Connection.objects.all()
    return render(request, 'advisor/connections/list.html', {
        'connections': connections,
    })


def connection_add(request):
    """Add a new database connection."""
    if request.method == 'POST':
        form = ConnectionForm(request.POST)
        if form.is_valid():
            connection = form.save()
            messages.success(request, f'Connection "{connection.name}" created successfully!')
            return redirect('advisor:connection_list')
    else:
        form = ConnectionForm()
    
    return render(request, 'advisor/connections/form.html', {
        'form': form,
        'title': 'Add Connection',
    })


def connection_edit(request, pk):
    """Edit an existing connection."""
    connection = get_object_or_404(Connection, pk=pk)
    
    if request.method == 'POST':
        form = ConnectionForm(request.POST, instance=connection)
        if form.is_valid():
            form.save()
            messages.success(request, f'Connection "{connection.name}" updated successfully!')
            return redirect('advisor:connection_list')
    else:
        # Don't show encrypted values in the form
        form = ConnectionForm(instance=connection, initial={
            'host': connection.get_decrypted_host(),
            'username': connection.get_decrypted_username(),
            'password': '',  # Don't show password
        })
    
    return render(request, 'advisor/connections/form.html', {
        'form': form,
        'title': 'Edit Connection',
        'connection': connection,
    })


def connection_delete(request, pk):
    """Delete a connection."""
    connection = get_object_or_404(Connection, pk=pk)
    
    if request.method == 'POST':
        name = connection.name
        connection.delete()
        messages.success(request, f'Connection "{name}" deleted successfully!')
        return redirect('advisor:connection_list')
    
    return render(request, 'advisor/connections/confirm_delete.html', {
        'connection': connection,
    })


def connection_test(request, pk):
    """Test a database connection (AJAX endpoint)."""
    connection = get_object_or_404(Connection, pk=pk)
    
    try:
        db = DBConnector(connection.get_connection_params())
        success, message = db.test_connection()
        return JsonResponse({
            'success': success,
            'message': message,
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e),
        })


def analyze_query(request, connection_id):
    """Query analysis page."""
    connection = get_object_or_404(Connection, pk=connection_id)
    
    if request.method == 'POST':
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data['query']
            test_recommendations = form.cleaned_data.get('test_recommendations', True)
            
            # Create query history record
            query_history = QueryHistory.objects.create(
                connection=connection,
                original_query=query,
                analysis_status='analyzing',
            )
            
            try:
                # Run optimization
                optimizer = QueryOptimizer(connection.get_connection_params())
                results = optimizer.optimize(query, test_recommendations=test_recommendations)
                
                if results['success']:
                    # Update query history
                    query_history.original_plan = results.get('original_plan')
                    query_history.original_execution_time = results.get('original_execution_time')
                    query_history.ai_provider = results.get('ai_provider')
                    query_history.analysis_status = 'completed'
                    query_history.save()
                    
                    # Save recommendations
                    for rec in results.get('recommendations', []):
                        Recommendation.objects.create(
                            query_history=query_history,
                            recommendation_type=rec.get('type', 'rewrite'),
                            description=rec.get('description', ''),
                            optimized_query=rec.get('optimized_query', ''),
                            suggested_indexes=rec.get('suggested_indexes', []),
                            tested_execution_time=rec.get('tested_execution_time'),
                            improvement_percentage=rec.get('improvement_percentage'),
                            rank=rec.get('rank', 0),
                            gemini_raw_response=rec,
                        )
                    
                    return redirect('advisor:view_results', query_id=query_history.id)
                else:
                    query_history.analysis_status = 'failed'
                    query_history.error_message = results.get('error', 'Unknown error')
                    query_history.save()
                    messages.error(request, f"Analysis failed: {results.get('error')}")
                    
            except OptimizationError as e:
                query_history.analysis_status = 'failed'
                query_history.error_message = str(e)
                query_history.save()
                messages.error(request, f"Optimization error: {e}")
            except Exception as e:
                query_history.analysis_status = 'failed'
                query_history.error_message = str(e)
                query_history.save()
                logger.exception("Unexpected error during analysis")
                messages.error(request, f"Unexpected error: {e}")
    else:
        form = QueryForm()
    
    return render(request, 'advisor/analyze.html', {
        'form': form,
        'connection': connection,
    })


def view_results(request, query_id):
    """View optimization results."""
    query_history = get_object_or_404(
        QueryHistory.objects.select_related('connection').prefetch_related('recommendations'),
        pk=query_id
    )
    
    all_recommendations = list(query_history.recommendations.all().order_by('rank'))
    original_time = query_history.original_execution_time or 0
    
    # Separate faster and slower recommendations
    faster_recs = []
    slower_recs = []
    untested_recs = []
    
    for rec in all_recommendations:
        if rec.tested_execution_time is None:
            untested_recs.append(rec)
        elif rec.tested_execution_time < original_time:
            faster_recs.append(rec)
        else:
            slower_recs.append(rec)
    
    # Prioritize: faster first, then untested, only show slower if nothing else
    if faster_recs or untested_recs:
        filtered_recommendations = faster_recs + untested_recs
        filtered_count = len(slower_recs)
    else:
        # No faster recommendations - show all with a note
        filtered_recommendations = all_recommendations
        filtered_count = 0
    
    # Re-rank the filtered recommendations
    for i, rec in enumerate(filtered_recommendations):
        rec.display_rank = i + 1
        # Mark if slower than original
        if rec.tested_execution_time and rec.tested_execution_time >= original_time:
            rec.is_slower = True
        else:
            rec.is_slower = False
    
    return render(request, 'advisor/results.html', {
        'query': query_history,
        'recommendations': filtered_recommendations,
        'total_recommendations': len(all_recommendations),
        'filtered_count': filtered_count,
        'all_slower': len(faster_recs) == 0 and len(untested_recs) == 0 and len(slower_recs) > 0,
    })


def query_history(request):
    """View query analysis history."""
    queries = QueryHistory.objects.select_related('connection').all()
    
    return render(request, 'advisor/history.html', {
        'queries': queries,
    })


@require_http_methods(["POST"])
def api_analyze(request):
    """API endpoint for asynchronous query analysis."""
    try:
        data = json.loads(request.body)
        connection_id = data.get('connection_id')
        query = data.get('query')
        test_recommendations = data.get('test_recommendations', True)
        
        if not connection_id or not query:
            return JsonResponse({
                'success': False,
                'error': 'Missing connection_id or query',
            }, status=400)
        
        connection = get_object_or_404(Connection, pk=connection_id)
        
        optimizer = QueryOptimizer(connection.get_connection_params())
        results = optimizer.optimize(query, test_recommendations=test_recommendations)
        
        return JsonResponse(results)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON',
        }, status=400)
    except Exception as e:
        logger.exception("API analyze error")
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)
