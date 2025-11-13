'''
шаблон для проверки работоспособности ai_service
'''

from ai_service import get_ai_service

ai_service = get_ai_service()

doc1_path = r"C:\Users\egorg\Documents\RAG_минцифры\Правильно\Проект Контракта4.docx"

doc2_path = r"C:\Users\egorg\Documents\RAG_минцифры\Правильно\Заявка в ПГ3.docx"

print(f"Processing documents:")
print(f"Document 1: {doc1_path}")
print(f"Document 2: {doc2_path}")

try:
    result = ai_service.process_query(
        doc1_path=doc1_path,
        doc2_path=doc2_path
    )
    
    ai_response = result['ai_response']
    
    print(f"AI Response: {ai_response}")
    
except Exception as e:
    print(f"Error processing documents: {e}")
