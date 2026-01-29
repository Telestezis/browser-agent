import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Конфигурация агента (только GigaChat)"""
    
    LLM_PROVIDER = "gigachat"  # Фиксировано
    
    GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
    GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "gigachat")
    
    BROWSER_HEADLESS = False
    BROWSER_SLOW_MO = 500
    BROWSER_MAXIMIZE = True
    BROWSER_USER_DATA_DIR = "./browser_data"
    
    MAX_STEPS = 30
    TOOL_TIMEOUT = 30
    WAIT_TIMEOUT = 10000
    
    @classmethod
    def validate(cls):
        if not cls.GIGACHAT_CREDENTIALS:
            raise ValueError("❌ GIGACHAT_CREDENTIALS не найден в .env файле!")
        print("✅ Используется GIGACHAT")