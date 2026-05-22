import time
import logging
import os
from typing import Dict, Any, Optional, List
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from config import Config
from browser_tools import BrowserTools
from sub_agent import SubAgent
from utils import (
    logger,
    extract_json_from_text,
    is_dangerous_action,
    confirm_action,
    truncate_text
)

class BrowserAgent:
    """
    Основной универсальный браузерный агент (только GigaChat).
    """
    
    def __init__(self):
        Config.validate()
        
        # Инициализация только GigaChat
        from gigachat import GigaChat
        self.llm_provider = "gigachat"
        self.llm_client = GigaChat(
            credentials=Config.GIGACHAT_CREDENTIALS,
            model=Config.GIGACHAT_MODEL,
            verify_ssl_certs=False
        )
        logger.info("✅ Инициализирован провайдер: GIGACHAT")
        
        # Инициализация суб-агента
        self.sub_agent = SubAgent(self.llm_provider, self.llm_client)
        
        # Запуск браузера
        self.playwright = sync_playwright().start()
        os.makedirs("browser_data", exist_ok=True)
        storage_path = "browser_data/storage_state.json"
        storage_state = storage_path if os.path.exists(storage_path) else None
        
        self.browser: Browser = self.playwright.chromium.launch(
            headless=Config.BROWSER_HEADLESS,
            slow_mo=Config.BROWSER_SLOW_MO,
            args=["--start-maximized"] if Config.BROWSER_MAXIMIZE else []
        )
        
        self.context = self.browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU"
        )
        
        self.page: Page = self.context.new_page()
        self.tools = BrowserTools(self.page)
        self.conversation_history: List[Dict[str, str]] = []
        self.analysis_cache: Dict[str, Any] = {}
    
    def close(self):
        """Закрытие браузера и ресурсов"""
        try:
            self.browser.close()
        except:
            pass
        try:
            self.playwright.stop()
        except:
            pass
    
    def _build_system_prompt(self, task: str = "") -> str:
        """
        Строит системный промпт динамически в зависимости от задачи.
        """
        task_lower = task.lower() if task else ""
        
        # Определяем тип задачи
        is_email_task = any(keyword in task_lower for keyword in [
            "почт", "письм", "email", "imap", "спам", "удали письмо", "прочитай письмо",
            "найди в почте", "получи письмо", "отчёт из письма"
        ])
        
        is_search_task = any(keyword in task_lower for keyword in [
            "найди", "поищи", "расскажи про", "информация", "погода", "новости",
            "узнай", "что такое", "как", "где найти"
        ]) or not is_email_task  # По умолчанию считаем поисковой задачей
        
        base_prompt = """Ты — автономный браузерный агент с двумя режимами работы:
1. 🔍 ПОИСК ИНФОРМАЦИИ в интернете через Яндекс
2. 📧 РАБОТА С ЭЛЕКТРОННОЙ ПОЧТОЙ через браузер (Yandex Mail)

## 🔴 КРИТИЧЕСКИ ВАЖНО — ФОРМАТ ОТВЕТА:
1. ТВОЙ ОТВЕТ ДОЛЖЕН СОДЕРЖАТЬ ТОЛЬКО ОДИН ЧИСТЫЙ JSON БЕЗ ЛЮБОГО ДРУГОГО ТЕКСТА
2. Формат: {"tool": "название", "args": {"параметр": "значение"}}
3. ЗАПРЕЩЕНО:
   • Пробелы внутри кавычек: "url ": "значение " → должно быть "url": "значение"
   • Несколько инструментов в одном ответе
   • Текст до или после JSON

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
{"tool": "navigate", "args": {"url": "https://yandex.ru"}}
"""
        
        # Добавляем инструкции для почтовых задач
        if is_email_task:
            email_section = """
## 📧 ТЫ РАБОТАЕШЬ С ЭЛЕКТРОННОЙ ПОЧТОЙ (YANDEX MAIL через браузер)

### СТРАТЕГИЯ ДЛЯ ПОЧТОВЫХ ЗАДАЧ:
1. ШАГ 1: Перейди на почту → {"tool": "navigate", "args": {"url": "https://mail.yandex.ru"}}
2. ШАГ 2: Сделай снимок страницы → {"tool": "extract_page_snapshot", "args": {}}
3. ШАГ 3: Найди и кликни по письмам в списке
4. ШАГ 4: Прочитай содержимое писем

### ДОСТУПНЫЕ ИНСТРУМЕНТЫ:
Все браузерные инструменты работают с почтой через веб-интерфейс.
"""
            base_prompt += email_section
        
        # Добавляем инструкции для поисковых задач
        if is_search_task:
            search_section = """
## 🔍 ТЫ ВЫПОЛНЯЕШЬ ПОИСК ИНФОРМАЦИИ В ИНТЕРНЕТЕ

### ГЛАВНОЕ ПРАВИЛО ДЛЯ ИНФОРМАЦИОННЫХ ЗАПРОСОВ:
Если пользователь просит найти информацию («найди», «поищи», «расскажи про»):
→ ВСЕГДА начинай с перехода на Яндекс: https://yandex.ru
→ Используй поле поиска Яндекса для ввода запроса
→ Если Яндекс недоступен (капча/редирект), попробуй альтернативы:
   • https://ya.ru - короткая версия Яндекса
   • https://google.com - международный поиск
   • https://ru.wikipedia.org - для энциклопедической информации

### СТРАТЕГИЯ РАБОТЫ:
1. ШАГ 1: {"tool": "navigate", "args": {"url": "https://yandex.ru"}}
2. ШАГ 2: {"tool": "extract_page_snapshot", "args": {}}
3. ШАГ 3: Найди поле поиска (обычно индекс 0 или 1) → {"tool": "fill_field_by_index", "args": {"index": 0, "value": "запрос"}}
4. ШАГ 4: {"tool": "press_enter", "args": {}}
5. ШАГ 5: Проанализируй результаты поиска → кликни по подходящей ссылке

### ЕСЛИ ЯНДЕКС НЕДОСТУПЕН (КАПЧА/РЕДИРЕКТ):
1. Попробуй https://ya.ru - более лёгкая версия
2. Попробуй https://ru.wikipedia.org/wiki/Запрос
3. Попробуй https://google.com/search?q=запрос

### ДОСТУПНЫЕ ИНСТРУМЕНТЫ ДЛЯ БРАУЗЕРА:
{"tool": "navigate", "args": {"url": "https://example.com"}}
{"tool": "extract_page_snapshot", "args": {}}
{"tool": "click_element_by_index", "args": {"index": 0}}
{"tool": "fill_field_by_index", "args": {"index": 0, "value": "текст"}}
{"tool": "press_enter", "args": {}}
{"tool": "scroll", "args": {"direction": "down", "amount": 500}}
{"tool": "check_checkbox", "args": {"index": 0}}
{"tool": "get_current_url", "args": {}}
{"tool": "wait_for_navigation", "args": {}}
"""
            base_prompt += search_section
        
        finish_section = """
## ФИНАЛЬНЫЙ ОТВЕТ:
Когда задача выполнена, напиши ТОЛЬКО:
ЗАДАЧА ВЫПОЛНЕНА
[краткий результат]

НЕ пиши ничего после этого. НЕ продолжай размышления.
"""
        base_prompt += finish_section
        
        return base_prompt

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Выполнение инструмента по имени"""
        
        # Словарь доступных инструментов
        available_tools = {
            "navigate": lambda: self.tools.navigate(args.get("url", "")),
            "extract_page_snapshot": lambda: self.tools.extract_page_snapshot(),
            "extract_list_items": lambda: self.tools.extract_list_items(args.get("max_count", 10)),
            "extract_table_data": lambda: self.tools.extract_table_data(args.get("max_rows", 10)),
            "extract_element_text": lambda: self.tools.extract_element_text(args.get("index", 0)),
            "click_element_by_index": lambda: self.tools.click_element_by_index(args.get("index", 0)),
            "fill_field_by_index": lambda: self.tools.fill_field_by_index(
                args.get("index", 0), 
                args.get("value", "")
            ),
            "scroll": lambda: self.tools.scroll(
                args.get("direction", "down"), 
                args.get("amount", 500)
            ),
            "press_enter": lambda: self.tools.press_enter(),
            "check_checkbox": lambda: self.tools.check_checkbox(args.get("index", 0)),
            "hover_element": lambda: self.tools.hover_element(args.get("index", 0)),
            "get_current_url": lambda: self.tools.get_current_url(),
            "wait_for_navigation": lambda: self.tools.wait_for_navigation(),
            "wait_for_element": lambda: self.tools.wait_for_element(
                args.get("selector", ""),
                args.get("timeout", Config.WAIT_TIMEOUT)
            ),
        }
        
        # Специальный инструмент для суб-агента
        if tool_name == "sub_agent_analysis":
            analysis_type = args.get("type", "spam")
            items = args.get("items", [])
            
            if analysis_type == "spam":
                result = self.sub_agent.analyze_spam(items)
                self.analysis_cache["last_spam_analysis"] = result
                return result
            elif analysis_type == "jobs":
                user_profile = args.get("user_profile", "")
                result = self.sub_agent.analyze_job_relevance(items, user_profile)
                self.analysis_cache["last_job_analysis"] = result
                return result
            else:
                return {
                    "success": False,
                    "error": f"Неизвестный тип анализа: {analysis_type}"
                }
        
        if tool_name not in available_tools:
            return {
                "success": False,
                "error": f"Неизвестный инструмент: {tool_name}"
            }
        
        try:
            return available_tools[tool_name]()
        except Exception as e:
            return {
                "success": False,
                "error": f"Ошибка выполнения {tool_name}: {str(e)}"
            }
    
    def _get_llm_response(self) -> str:
        """Получение ответа от GigaChat"""
        try:
            from gigachat.models import Chat
            response = self.llm_client.chat(Chat(messages=self.conversation_history))
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Ошибка связи с LLM: {e}")
            raise

    def think_and_act(self, task: str, max_steps: int = None) -> str:
        """Главный цикл агента: думает → выбирает действие → получает результат"""
        
        if max_steps is None:
            max_steps = Config.MAX_STEPS
        
        logger.info(f"🎯 Задача: {task}")
        
        # Инициализация истории диалога для GigaChat
        from gigachat.models import Messages, MessagesRole
        system_prompt = self._build_system_prompt(task)
        self.conversation_history = [
            Messages(role=MessagesRole.SYSTEM, content=system_prompt),
            Messages(role=MessagesRole.USER, content=f"ЗАДАЧА: {task}")
        ]
        
        # Счётчики для детектирования проблем
        consecutive_format_errors = 0
        blank_page_count = 0
        last_url = "about:blank"
        
        # Основной цикл выполнения задачи
        for step in range(max_steps):
            logger.info(f"\n{'='*60}")
            logger.info(f"ШАГ {step + 1}/{max_steps}")
            logger.info(f"{'='*60}")
            
            # Запрос к модели
            assistant_reply = ""
            try:
                assistant_reply = self._get_llm_response()
                from gigachat.models import Messages, MessagesRole
                self.conversation_history.append(
                    Messages(role=MessagesRole.ASSISTANT, content=assistant_reply)
                )
            except Exception as e:
                return f"❌ Ошибка связи с LLM: {str(e)}"
            
            # Вывод рассуждений агента в консоль
            print(f"\n{'─'*60}")
            print(f"🤖 АГЕНТ (Шаг {step + 1}):")
            print(f"{'─'*60}")
            print(assistant_reply)
            
            # ПРОВЕРКА ЗАВЕРШЕНИЯ ЗАДАЧИ - должна быть ДО парсинга JSON
            reply_lower = assistant_reply.lower().strip()
            
            # Если агент явно сообщает о завершении задачи
            if any(keyword in reply_lower for keyword in ["задача выполнена", "готово", "успешно завершено", "mission complete"]):
                # Проверяем, что это не просто упоминание, а финальное сообщение
                if "tool" not in reply_lower or reply_lower.startswith("задача выполнена") or reply_lower.startswith("готово"):
                    logger.info("✅ Агент сообщил о завершении задачи")
                    return f"✅ ЗАДАЧА ВЫПОЛНЕНА:\n{assistant_reply}"
            
            # ИЗВЛЕЧЕНИЕ ИНСТРУМЕНТА ИЗ ОТВЕТА
            tool_call = extract_json_from_text(assistant_reply)
            
            if tool_call and isinstance(tool_call, dict) and "tool" in tool_call:
                tool_name = str(tool_call.get("tool", "")).strip()
                raw_args = tool_call.get("args", {})
                
                # Глубокая очистка аргументов
                if isinstance(raw_args, dict):
                    args = {}
                    for key, value in raw_args.items():
                        if isinstance(value, str):
                            args[key] = value.strip()
                        else:
                            args[key] = value
                else:
                    args = {}
                
                logger.info(f"🔧 Выполняю инструмент: {tool_name} | args: {args}")
                consecutive_format_errors = 0
                
                # ВЫПОЛНЕНИЕ ИНСТРУМЕНТА
                if is_dangerous_action(tool_name, args, task):
                    if not confirm_action(tool_name, str(args)):
                        tool_result = {
                            "success": False,
                            "message": "Действие отменено пользователем"
                        }
                    else:
                        tool_result = self._execute_tool(tool_name, args)
                else:
                    tool_result = self._execute_tool(tool_name, args)
                
                # ФОРМИРОВАНИЕ ОТВЕТА ДЛЯ МОДЕЛИ
                if tool_result.get("success"):
                    result_msg = f"✅ Успешно: {tool_result.get('message', 'Действие выполнено')}"
                else:
                    result_msg = f"❌ Ошибка: {tool_result.get('error', 'Неизвестная ошибка')}"
                
                # Добавление деталей для снимка страницы
                if tool_name == "extract_page_snapshot" and tool_result.get("success"):
                    elements = tool_result.get("elements", [])[:15]
                    elements_info = "\n".join([
                        f"{el.get('index', '?')}. [{el.get('type', '?')}] \"{el.get('text', '')[:60].strip()}\""
                        for el in elements if isinstance(el, dict)
                    ])
                    
                    result_msg += f"\n\nТекущая страница: {tool_result.get('title', 'Без названия')}"
                    result_msg += f"\nURL: {tool_result.get('url', 'Неизвестен')}"
                    
                    # Проверка на капчу/редирект
                    is_captcha = tool_result.get("is_captcha_detected", False)
                    if is_captcha:
                        result_msg += "\n⚠️ ОБНАРУЖЕНА КАПЧА ИЛИ РЕДИРЕКТ! Попробуй другой URL:"
                        result_msg += "\n- https://ya.ru - короткая версия Яндекса"
                        result_msg += "\n- https://google.com/search?q=запрос"
                        result_msg += "\n- https://ru.wikipedia.org/wiki/Запрос"
                    
                    result_msg += f"\n\nЭлементы на странице ({tool_result.get('element_count', 0)}):"
                    result_msg += f"\n{elements_info or 'Нет элементов'}"
                    if tool_result.get("element_count", 0) > 15:
                        result_msg += f"\n... и ещё {tool_result.get('element_count', 0) - 15} элементов"
                    
                    # Детектирование пустой страницы
                    current_url = tool_result.get("url", "")
                    if current_url == "about:blank" or tool_result.get("element_count", 0) == 0:
                        blank_page_count += 1
                    else:
                        blank_page_count = 0
                        last_url = current_url
                    
                    # Если обнаружена капча, увеличиваем счётчик для восстановления
                    if is_captcha:
                        blank_page_count += 1
                
                # Детектирование неудачной навигации
                if tool_name == "navigate":
                    current_url = tool_result.get("url", "")
                    is_captcha = tool_result.get("is_captcha_detected", False)
                    if current_url == "about:blank" or not tool_result.get("success") or is_captcha:
                        blank_page_count += 1
                    else:
                        blank_page_count = 0
                        last_url = current_url
                
                # Добавление результата в историю
                from gigachat.models import Messages, MessagesRole
                self.conversation_history.append(
                    Messages(role=MessagesRole.USER, content=f"Результат действия:\n{result_msg}")
                )
                
                logger.info(f"🔧 Результат: {result_msg.split(chr(10))[0][:100]}...")
                
            else:
                # ОБРАБОТКА ОШИБКИ ФОРМАТА
                consecutive_format_errors += 1
                
                if any(keyword in assistant_reply.lower() for keyword in ["задача выполнена", "готово"]):
                    return f"✅ ЗАДАЧА ВЫПОЛНЕНА:\n{assistant_reply}"
                
                if consecutive_format_errors >= 3:
                    return (f"⚠️ Агент не может сформировать корректный вызов инструмента "
                        f"({consecutive_format_errors} попыток).\n"
                        f"Последний ответ модели:\n{assistant_reply[:300]}... ")
                
                # Отправка корректирующего сообщения модели
                correction = ("ОШИБКА ФОРМАТА! Ответ должен содержать ТОЛЬКО ОДИН инструмент в ЧИСТОМ JSON:\n"
                            '{"tool": "название_инструмента", "args": {"параметр": "значение"}}\n'
                            "Без текста до/после JSON, без нескольких инструментов в одном ответе.")
                logger.warning(f"⚠️ {correction}")
                
                from gigachat.models import Messages, MessagesRole
                self.conversation_history.append(
                    Messages(role=MessagesRole.USER, content=correction)
                )
                continue
            
            # ВОССТАНОВЛЕНИЕ ПРИ ЗАСТРЕВАНИИ НА ПУСТОЙ СТРАНИЦЕ
            if blank_page_count >= 3:
                logger.warning("⚠️ Агент застрял на пустой странице. Пробую восстановление...")
                recovery_result = self.tools.navigate("https://yandex.ru")
                recovery_msg = (f"Восстановление: переход на Яндекс "
                            f"{'успешен' if recovery_result.get('success') else 'не удался'}")
                logger.info(recovery_msg)
                
                from gigachat.models import Messages, MessagesRole
                self.conversation_history.append(
                    Messages(role=MessagesRole.USER, content=f"СИСТЕМА: {recovery_msg}")
                )
                blank_page_count = 0
        
        # ДОСТИГНУТ ЛИМИТ ШАГОВ
        if last_url != "about:blank":
            return (f"⚠️ Достигнут лимит шагов ({max_steps}).\n"
                f"Последний URL: {last_url}\n"
                f"Агент не завершил задачу, но выполнил часть действий.")
        else:
            return ("⚠️ Достигнут лимит шагов ({max_steps}).\n"
                "Агент не смог покинуть пустую страницу.\n"
                "Возможные причины: проблемы с интернетом, блокировка сайта, ошибка в задаче.")