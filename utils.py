import logging
import json
import re
from typing import Optional, Dict, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def extract_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """
    Извлекает ПЕРВЫЙ валидный JSON объект с ключом "tool" из текста.
    Работает с чистым JSON и текстом + JSON.
    Автоматически очищает строки от пробелов.
    """
    import json
    import re
    
    # Удаляем артефакты разметки
    text = re.sub(r'<\|[^|]+\|>', '', text)
    
    # Находим первую открывающую скобку
    start = text.find('{')
    if start == -1:
        return None
    
    # Находим соответствующую закрывающую скобку (учитываем вложенность)
    depth = 0
    for i in range(start, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                json_str = text[start:i+1]
                try:
                    # Пробуем распарсить
                    parsed = json.loads(json_str)
                except json.JSONDecodeError:
                    # Пробуем исправить одинарные кавычки
                    try:
                        parsed = json.loads(json_str.replace("'", '"'))
                    except:
                        return None
                
                # Проверяем наличие обязательного ключа
                if isinstance(parsed, dict) and "tool" in parsed:
                    # Рекурсивная очистка всех строковых значений
                    def clean_strings(obj):
                        if isinstance(obj, dict):
                            return {k: clean_strings(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [clean_strings(v) for v in obj]
                        elif isinstance(obj, str):
                            return obj.strip()
                        return obj
                    
                    return clean_strings(parsed)
                break
    
    return None

def truncate_text(text: str, max_length: int = 1500) -> str:
    """Усекает текст до заданной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"... (усечено, всего {len(text)} символов)"

def safe_get(obj: Any, *keys: str, default: Any = None) -> Any:
    """
    Безопасное получение значения из вложенных словарей/объектов
    """
    for key in keys:
        try:
            if isinstance(obj, dict):
                obj = obj[key]
            elif hasattr(obj, key):
                obj = getattr(obj, key)
            else:
                return default
        except (KeyError, AttributeError, TypeError):
            return default
    return obj

def is_dangerous_action(tool_name: str, args: Dict[str, Any], task_context: str = "") -> bool:
    """
    Проверяет, является ли действие потенциально опасным.
    Учитывает контекст задачи — если пользователь явно просит удалить спам,
    то удаление НЕ является опасным действием.
    """
    dangerous_keywords = [
        "удалить", "спам", "корзина", "очистить",
        "оплатить", "купить", "заказать", "подтвердить",
        "отправить", "откликнуться", "сохранить"
    ]
    
    # Проверяем название инструмента и аргументы
    check_text = f"{tool_name} {str(args).lower()}"
    
    # Если действие опасное, проверяем контекст задачи
    is_dangerous = any(kw in check_text for kw in dangerous_keywords)
    
    if is_dangerous:
        # Если пользователь явно просит выполнить это действие — не спрашиваем
        task_lower = task_context.lower()
        
        # Удаление спама — целевое действие
        if "удалить спам" in task_lower or "очистить спам" in task_lower:
            if "удалить" in check_text or "корзина" in check_text:
                return False
        
        # Заказ еды — целевое действие
        if "закажи" in task_lower or "заказать" in task_lower:
            if "заказать" in check_text or "купить" in check_text:
                return False
        
        # Отклик на вакансии — целевое действие
        if "откликнись" in task_lower or "откликнуться" in task_lower:
            if "отклик" in check_text or "отправить" in check_text:
                return False
    
    return is_dangerous

def confirm_action(action: str, details: str) -> bool:
    """
    Запрашивает подтверждение у пользователя для опасных действий
    """
    print(f"\n{'='*60}")
    print(f"⚠️  ВНИМАНИЕ! Агент хочет выполнить: {action}")
    print(f"Детали: {details}")
    print(f"{'='*60}")
    while True:
        confirm = input("\nРазрешить? (да/нет): ").strip().lower()
        if confirm in ["да", "нет", "y", "n"]:
            return confirm in ["да", "y"]
        print("Пожалуйста, введите 'да' или 'нет'")