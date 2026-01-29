import logging
from typing import List, Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

class SubAgent:
    """
    Специализированный агент для анализа контента.
    Используется для задач, требующих глубокого анализа:
    - Определение спама в письмах
    - Анализ вакансий
    - Классификация контента
    """
    
    def __init__(self, provider: str, client: Any):
        self.provider = provider
        self.client = client

    def _get_llm_response(self, prompt: str, json_mode: bool = True) -> str:
        """Универсальный метод для получения ответа от LLM"""
        try:
            if self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=Config.OPENAI_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"} if json_mode else None
                )
                return response.choices[0].message.content
            
            else:  # gigachat
                from gigachat.models import Chat, Messages
                response = self.client.chat(Chat(messages=[
                    Messages(role="user", content=prompt)
                ]))
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"Ошибка связи с LLM в суб-агенте: {e}")
            raise

    def analyze_spam(self, items: List[str]) -> Dict[str, Any]:
        """Анализирует список элементов (писем) на спам"""
        prompt = f"""Ты — эксперт по анализу спама. Твоя задача — проанализировать предоставленные тексты и определить, являются ли они спамом.

КРИТЕРИИ СПАМА:
1. Рекламные рассылки без явного согласия
2. Фишинг (запрос логинов, паролей, денег, персональных данных)
3. Подозрительные отправители (случайные символы, подделка известных компаний)
4. Массовые рассылки с шаблонным текстом
5. Предложения "быстрого заработка", казино, кредитов, лекарств
6. Срочные требования действовать "прямо сейчас"
7. Грамматические ошибки, странное форматирование

ФОРМАТ ОТВЕТА (ТОЛЬКО ВАЛИДНЫЙ JSON):
{{
    "analysis": [
        {{
            "index": 0,
            "is_spam": true/false,
            "confidence": 0.0,
            "reason": "краткое объяснение"
        }}
    ],
    "summary": {{
        "total": {len(items)},
        "spam_count": 0,
        "not_spam_count": 0
    }}
}}

Тексты для анализа:
"""
        for idx, item in enumerate(items):
            prompt += f"\nТЕКСТ {idx}:\n{item[:300]}\n"
        
        try:
            result_text = self._get_llm_response(prompt, json_mode=True)
            
            import json
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                spam_count = sum(1 for item in parsed.get("analysis", []) if item.get("is_spam"))
                parsed["summary"] = {
                    "total": len(items),
                    "spam_count": spam_count,
                    "not_spam_count": len(items) - spam_count
                }
                return parsed
            
            return {"error": "Не удалось распарсить ответ", "raw_response": result_text}
            
        except Exception as e:
            logger.error(f"Ошибка анализа спама: {e}")
            return {"error": str(e)}

    def analyze_job_relevance(self, job_descriptions: List[str], user_profile: str) -> Dict[str, Any]:
        """Анализирует релевантность вакансий профилю пользователя"""
        prompt = f"""Ты — эксперт по подбору персонала. Твоя задача — проанализировать вакансии и определить их релевантность профилю кандидата.

ПРОФИЛЬ КАНДИДАТА:
{user_profile}

ИНСТРУКЦИЯ:
1. Проанализируй каждую вакансию
2. Оцени релевантность по шкале 0-1 (1 = идеально подходит)
3. Учитывай: технологии, опыт, требования, уровень позиции, обязанности
4. Определи ключевые совпадения и чего не хватает

ФОРМАТ ОТВЕТА (ТОЛЬКО ВАЛИДНЫЙ JSON):
{{
    "analysis": [
        {{
            "index": 0,
            "relevance_score": 0.0,
            "key_matches": ["совпадение 1"],
            "missing_skills": ["навык"],
            "recommendation": "высокая"
        }}
    ],
    "summary": {{
        "total": {len(job_descriptions)},
        "high_relevance": 0,
        "medium_relevance": 0,
        "low_relevance": 0
    }}
}}

ВАКАНСИИ ДЛЯ АНАЛИЗА:
"""
        for idx, desc in enumerate(job_descriptions):
            prompt += f"\nВАКАНСИЯ {idx}:\n{desc[:500]}\n"
        
        try:
            result_text = self._get_llm_response(prompt, json_mode=True)
            
            import json
            import re
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
                high = sum(1 for item in parsed.get("analysis", []) if item.get("relevance_score", 0) >= 0.7)
                medium = sum(1 for item in parsed.get("analysis", []) if 0.4 <= item.get("relevance_score", 0) < 0.7)
                low = sum(1 for item in parsed.get("analysis", []) if item.get("relevance_score", 0) < 0.4)
                parsed["summary"] = {
                    "total": len(job_descriptions),
                    "high_relevance": high,
                    "medium_relevance": medium,
                    "low_relevance": low
                }
                return parsed
            
            return {"error": "Не удалось распарсить ответ", "raw_response": result_text}
            
        except Exception as e:
            logger.error(f"Ошибка анализа вакансий: {e}")
            return {"error": str(e)}