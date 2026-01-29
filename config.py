import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация агента"""
    
    # ===== LLM ПРОВАЙДЕР (выбрать ОДИН) =====
    # Провайдер: "claude", "openai" или "gigachat"
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "claude")
    
    # Claude 3.5 Sonnet (рекомендуется)
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
    
    # OpenAI GPT-4o
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    # GigaChat (резервный, НЕ рекомендуется для сложных задач)
    GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
    GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "gigachat")
    
    # ===== БРАУЗЕР =====
    BROWSER_HEADLESS = False
    BROWSER_SLOW_MO = 500
    BROWSER_MAXIMIZE = True
    BROWSER_USER_DATA_DIR = "./browser_data"
    
    # ===== АГЕНТ =====
    MAX_STEPS = 30  # Максимум шагов на задачу
    CONTEXT_MAX_TOKENS = 8000
    PAGE_TEXT_LIMIT = 2000  # Символов текста со страницы
    PAGE_ELEMENTS_LIMIT = 50  # Элементов на странице
    
    # ===== ИНСТРУМЕНТЫ =====
    TOOL_TIMEOUT = 30  # секунд
    WAIT_TIMEOUT = 10000  # мс для ожидания элементов
    
    @classmethod
    def validate(cls):
        """Проверка обязательных настроек"""
        if cls.LLM_PROVIDER == "claude":
            if not cls.CLAUDE_API_KEY:
                raise ValueError("❌ CLAUDE_API_KEY не найден в .env файле!")
        elif cls.LLM_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                raise ValueError("❌ OPENAI_API_KEY не найден в .env файле!")
        elif cls.LLM_PROVIDER == "gigachat":
            if not cls.GIGACHAT_CREDENTIALS:
                raise ValueError("❌ GIGACHAT_CREDENTIALS не найден в .env файле!")
        
        print(f"✅ Используется {cls.LLM_PROVIDER.upper()}")