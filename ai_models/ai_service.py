from typing import Optional, List, Dict, Any

#rm
from time import sleep
##your imports


##imports end

class AIService:    
    ready = False

    def __init__(self):
        self._initialize()
    
    def _initialize(self) -> None:
        # fill in initialization if needed

        #
        self.ready = True


    def is_ready(self) -> bool:
        return self.ready
    
    #doc1 - Заявка на внесение в план-график
    #doc2 - Контракт
    def process_query(self, doc1_path: str, doc2_path: str) -> Dict[str, Any]:
        ##processing
        ai_response = f'ai response {doc1_path}, {doc2_path}'
        sleep(5)
        ##
        return {
            'ai_response': ai_response
        }

_ai_service_instance: Optional[AIService] = None

def get_ai_service() -> AIService:
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = AIService()
    return _ai_service_instance

