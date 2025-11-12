import os
import base64
import tempfile
import shutil
from celery import shared_task
from ai_models import get_ai_service

ai_service = get_ai_service()


@shared_task(bind=True, name='rag_worker.process_document_query')
def process_document_query(self, file1_content_b64, file1_name, file2_content_b64, file2_name):
    if not ai_service.is_ready():
        error_msg = "AI model not loaded. Check worker logs."
        raise Exception(error_msg)
    
    try:
        file1_content = base64.b64decode(file1_content_b64)
        file2_content = base64.b64decode(file2_content_b64)
        
        temp_dir = tempfile.mkdtemp()
        try:
            temp_file1_path = os.path.join(temp_dir, file1_name)
            temp_file2_path = os.path.join(temp_dir, file2_name)
            
            with open(temp_file1_path, 'wb') as f:
                f.write(file1_content)
            
            with open(temp_file2_path, 'wb') as f:
                f.write(file2_content)
            
            result = ai_service.process_query(
                doc1_path=temp_file1_path,
                doc2_path=temp_file2_path
            )
            
            return {
                'ai_response': result['ai_response'],
                'file1_name': file1_name,
                'file2_name': file2_name,
                'status': 'completed'
            }
            
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing documents: {error_msg}")
        raise Exception(error_msg)
