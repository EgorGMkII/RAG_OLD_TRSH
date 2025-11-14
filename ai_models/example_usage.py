'''
шаблон для проверки работоспособности ai_service
'''
from docx import Document
from ai_service import get_ai_service

ai_service = get_ai_service()

doc1_path = r"C:\Users\egorg\Documents\RAG_минцифры\Правильно\Заявка в ПГ.docx"
doc2_path = r"C:\Users\egorg\Documents\RAG_минцифры\Правильно\Проект Контракта.docx"

print(f"Processing documents:")
print(f"Document 1: {doc1_path}")
print(f"Document 2: {doc2_path}")


try:
    result = ai_service.process_query(
        doc1_path=doc1_path,
        doc2_path=doc2_path
    )
    
    ai_response = result['ai_response']
    doc = Document()
    doc.add_paragraph(ai_response)
    doc.save("ai_analysis.docx")

    print(f"AI Response: {ai_response}")
    
except Exception as e:
    print(f"Error processing documents: {e}")
