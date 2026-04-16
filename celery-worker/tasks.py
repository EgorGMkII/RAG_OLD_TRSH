import os
import base64
import tempfile
import shutil
from celery import shared_task
from govno_model.ai_service import get_ai_service

ai_service = get_ai_service()

REQUIRED_DOCUMENTS = (
    ("plan", "Заявка в план-график"),
    ("contract", "Проект контракта"),
    ("ooz", "ООЗ"),
    ("zapiska", "Пояснительная записка"),
    ("onmck", "ОНМЦК"),
    ("obrasheniye", "Обращение о проведении закупки"),
)


@shared_task(bind=True, name='rag_worker.process_document_query')
def process_document_query(self, documents):
    try:
        if not isinstance(documents, list):
            raise ValueError("Expected a list of uploaded documents.")

        docs_by_key = {}
        for document in documents:
            doc_key = document.get('key')
            file_name = document.get('name')
            file_content_b64 = document.get('content_b64')

            if not doc_key or not file_name or not file_content_b64:
                raise ValueError("Each uploaded document must contain key, name and content_b64.")

            docs_by_key[doc_key] = {
                'name': file_name,
                'content': base64.b64decode(file_content_b64),
            }

        missing_docs = [label for key, label in REQUIRED_DOCUMENTS if key not in docs_by_key]
        if missing_docs:
            raise ValueError(
                f"Missing required documents: {', '.join(missing_docs)}."
            )

        temp_dir = tempfile.mkdtemp()
        try:
            doc_paths = {}
            for key, _label in REQUIRED_DOCUMENTS:
                file_name = os.path.basename(docs_by_key[key]['name'])
                temp_file_path = os.path.join(temp_dir, f"{key}_{file_name}")

                with open(temp_file_path, 'wb') as f:
                    f.write(docs_by_key[key]['content'])

                doc_paths[key] = temp_file_path

            result = ai_service.process_query(
                plan_path=doc_paths['plan'],
                contract_path=doc_paths['contract'],
                ooz_path=doc_paths['ooz'],
                zapiska_path=doc_paths['zapiska'],
                ONMCK_path=doc_paths['onmck'],
                Obrasheniye_path=doc_paths['obrasheniye'],
            )

            return {
                'ai_response': result['ai_response'],
                'documents': [
                    {
                        'key': key,
                        'label': label,
                        'name': docs_by_key[key]['name'],
                    }
                    for key, label in REQUIRED_DOCUMENTS
                ],
                'status': 'completed'
            }
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing documents: {error_msg}")
        raise Exception(error_msg)
