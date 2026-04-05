import os
import base64
from django.shortcuts import render, redirect
from celery import Celery
from celery.result import AsyncResult

celery_app = Celery('django_client')
celery_app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
celery_app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
celery_app.conf.task_serializer = 'json'
celery_app.conf.result_serializer = 'json'
celery_app.conf.accept_content = ['json']


def index(request):
    context = {}
    if 'error' in request.GET:
        context['error'] = request.GET['error']
    return render(request, 'fileprocessor/index.html', context)


def upload_and_process(request):
    if request.method == 'POST':
        uploaded_file1 = request.FILES.get('file1')
        uploaded_file2 = request.FILES.get('file2')
        
        if not uploaded_file1:
            return redirect('fileprocessor:index?error=Please select the first file to upload.')
        
        if not uploaded_file2:
            return redirect('fileprocessor:index?error=Please select the second file to upload.')
        
        file1_content = uploaded_file1.read()
        file1_name = uploaded_file1.name
        file2_content = uploaded_file2.read()
        file2_name = uploaded_file2.name
        
        file1_content_b64 = base64.b64encode(file1_content).decode('utf-8')
        file2_content_b64 = base64.b64encode(file2_content).decode('utf-8')
        
        result = celery_app.send_task(
            'rag_worker.process_document_query',
            args=[file1_content_b64, file1_name, file2_content_b64, file2_name]
        )
        
        request.session['task_id'] = result.id
        request.session['file1_name'] = file1_name
        request.session['file2_name'] = file2_name
        
        return redirect('fileprocessor:result')
    
    return redirect('fileprocessor:index')


def result(request):
    task_id = request.session.get('task_id')
    
    if not task_id:
        return redirect('fileprocessor:index')
    
    result = AsyncResult(task_id, app=celery_app)
    
    context = {
        'task_id': task_id,
        'file1_name': request.session.get('file1_name', ''),
        'file2_name': request.session.get('file2_name', ''),
        'status': 'processing',
    }
    
    if result.ready():
        if result.successful():
            data = result.get()
            context['ai_response'] = data.get('ai_response', '')
            context['status'] = 'completed'
        else:
            context['error'] = str(result.info) if result.info else 'Unknown error occurred'
            context['status'] = 'failed'
    else:
        context['status'] = 'processing'
    
    return render(request, 'fileprocessor/result.html', context)



