import time
import logging
import re
from config import Config
from typing import Optional, List, Dict, Any
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError

logger = logging.getLogger(__name__)

class BrowserTools:
    """Набор универсальных инструментов для работы с браузером"""
    
    def __init__(self, page: Page):
        self.page = page
    
    # ============================================================
    # БАЗОВЫЕ МЕТОДЫ (уже были в оригинале)
    # ============================================================
    
    def navigate(self, url: str) -> Dict[str, Any]:
        """Переход по указанному URL (автоматически добавляет схему)"""
        try:
            url = url.strip()
            if not url.startswith(('http://', 'https://', 'file://')):
                url = 'https://' + url
            
            logger.info(f"🌐 Переход на {url}")
            self.page.goto(url, timeout=Config.TOOL_TIMEOUT * 1000)
            time.sleep(1.5)
            
            # Проверка на редирект/капчу после навигации
            current_url = self.page.url
            is_captcha_detected = False
            captcha_keywords = ['captcha', 'security check', 'проверка безопасности', 'dzen.ru', 'yredirect']
            for keyword in captcha_keywords:
                if keyword.lower() in current_url.lower():
                    is_captcha_detected = True
                    break
            
            return {
                "success": True,
                "url": current_url,
                "is_captcha_detected": is_captcha_detected,
                "message": f"Перешли на {url}" + (" ⚠️ ОБНАРУЖЕНА КАПЧА/РЕДИРЕКТ!" if is_captcha_detected else "")
            }
        except Exception as e:
            error_msg = f"Ошибка навигации: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
            
    def extract_page_snapshot(self) -> Dict[str, Any]:
        """Извлекает информацию о текущей странице и видимых элементах"""
        try:
            logger.info("📸 Извлечение снимка страницы")
            
            # Проверка на капчу/редирект
            current_url = self.page.url
            is_captcha_detected = False
            captcha_keywords = ['captcha', 'security check', 'проверка безопасности', 'dzen.ru', 'yredirect']
            for keyword in captcha_keywords:
                if keyword.lower() in current_url.lower():
                    is_captcha_detected = True
                    break
            
            result = self.page.evaluate("""() => {
                const elements = [];
                const selectors = 'a, button, input, textarea, select, [role="button"], [role="link"]';
                const allElements = Array.from(document.querySelectorAll(selectors));
                
                allElements.forEach((el, idx) => {
                    try {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        
                        if (
                            rect.width > 10 &&
                            rect.height > 10 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden' &&
                            rect.top >= 0 &&
                            rect.bottom <= window.innerHeight
                        ) {
                            const text = el.textContent.trim();
                            const type = el.tagName.toLowerCase();
                            const inputType = el.type || '';
                            
                            elements.push({
                                index: elements.length,
                                type: type,
                                inputType: inputType,
                                text: text.substring(0, 100),
                                tagName: type,
                                href: el.href || '',
                                placeholder: el.placeholder || '',
                                value: el.value || ''
                            });
                        }
                    } catch (e) {
                        // Пропускаем элементы, которые вызывают ошибки
                    }
                });
                
                return {
                    title: document.title,
                    url: window.location.href,
                    elements: elements.slice(0, 50)
                };
            }""")
            
            element_count = len(result.get("elements", []))
            logger.info(f"✅ Извлечено {element_count} элементов")
            
            # Проверка на капчу по содержимому страницы
            page_title = result.get("title", "").lower()
            if 'captcha' in page_title or 'security' in page_title or 'проверка' in page_title:
                is_captcha_detected = True
            
            return {
                "success": True,
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "elements": result.get("elements", []),
                "element_count": element_count,
                "is_captcha_detected": is_captcha_detected,
                "message": f"Извлечено {element_count} элементов со страницы" + (" ⚠️ ОБНАРУЖЕНА КАПЧА/РЕДИРЕКТ!" if is_captcha_detected else "")
            }
            
        except Exception as e:
            error_msg = f"Ошибка извлечения снимка: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def click_element_by_index(self, index: int) -> Dict[str, Any]:
        """Кликает по элементу по индексу"""
        try:
            logger.info(f"🖱️ Клик по элементу #{index}")
            
            result = self.page.evaluate("""(idx) => {
                const selectors = 'a, button, input, textarea, select, [role="button"], [role="link"]';
                const elements = Array.from(document.querySelectorAll(selectors));
                
                const visibleElements = elements.filter(el => {
                    try {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 10 &&
                            rect.height > 10 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        );
                    } catch (e) {
                        return false;
                    }
                });
                
                if (idx >= visibleElements.length) {
                    return {found: false};
                }
                
                const element = visibleElements[idx];
                element.click();
                return {found: true, text: element.textContent.trim().substring(0, 50)};
            }""", index)
            
            if result.get("found"):
                logger.info(f"✅ Кликнули по элементу #{index}: {result.get('text', '')}")
                time.sleep(1)
                return {
                    "success": True,
                    "message": f"Кликнули по элементу #{index}: {result.get('text', '')}"
                }
            else:
                error_msg = f"Элемент #{index} не найден"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"Ошибка клика: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def fill_field_by_index(self, index: int, value: str) -> Dict[str, Any]:
        """Заполняет поле ввода по индексу"""
        try:
            logger.info(f"✍️ Заполнение поля #{index}: {value}")
            
            result = self.page.evaluate("""([idx, val]) => {
                const selectors = 'input, textarea, [contenteditable]';
                const elements = Array.from(document.querySelectorAll(selectors));
                
                const visibleElements = elements.filter(el => {
                    try {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 10 &&
                            rect.height > 10 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        );
                    } catch (e) {
                        return false;
                    }
                });
                
                if (idx >= visibleElements.length) {
                    return {found: false};
                }
                
                const field = visibleElements[idx];
                field.value = val;
                field.dispatchEvent(new Event('input', { bubbles: true }));
                field.dispatchEvent(new Event('change', { bubbles: true }));
                
                return {found: true, placeholder: field.placeholder || ''};
            }""", [index, value])
            
            if result.get("found"):
                logger.info(f"✅ Заполнили поле #{index}")
                time.sleep(0.5)
                return {
                    "success": True,
                    "message": f"Заполнили поле #{index}"
                }
            else:
                error_msg = f"Поле #{index} не найдено"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"Ошибка заполнения поля: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def scroll(self, direction: str = "down", amount: int = 500) -> Dict[str, Any]:
        """Прокручивает страницу"""
        try:
            logger.info(f"⬇️ Прокрутка {direction} на {amount}px")
            
            if direction == "down":
                self.page.evaluate(f"window.scrollBy(0, {amount})")
            else:
                self.page.evaluate(f"window.scrollBy(0, -{amount})")
            
            time.sleep(0.5)
            return {
                "success": True,
                "message": f"Прокрутили {direction} на {amount}px"
            }
            
        except Exception as e:
            error_msg = f"Ошибка прокрутки: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def press_enter(self) -> Dict[str, Any]:
        """Нажимает клавишу Enter"""
        try:
            logger.info("⏎ Нажатие Enter")
            
            self.page.keyboard.press("Enter")
            time.sleep(1)
            
            return {
                "success": True,
                "message": "Нажали Enter"
            }
            
        except Exception as e:
            error_msg = f"Ошибка нажатия Enter: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def get_current_url(self) -> Dict[str, Any]:
        """Возвращает текущий URL"""
        try:
            url = self.page.url
            logger.info(f"🔗 Текущий URL: {url}")
            return {
                "success": True,
                "url": url,
                "message": f"Текущий URL: {url}"
            }
        except Exception as e:
            error_msg = f"Ошибка получения URL: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def wait_for_navigation(self) -> Dict[str, Any]:
        """Ждёт завершения навигации"""
        try:
            logger.info("⏱️ Ожидание навигации...")
            self.page.wait_for_load_state("networkidle", timeout=10000)
            time.sleep(0.5)
            logger.info("✅ Навигация завершена")
            return {
                "success": True,
                "message": "Навигация завершена"
            }
        except PlaywrightTimeoutError:
            logger.warning("⚠️ Таймаут ожидания навигации")
            return {
                "success": True,
                "message": "Таймаут ожидания (продолжаем работу)"
            }
        except Exception as e:
            error_msg = f"Ошибка ожидания навигации: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    # ============================================================
    # НОВЫЕ МЕТОДЫ (добавлены для сложных задач)
    # ============================================================
    
    def extract_list_items(self, max_count: int = 10) -> Dict[str, Any]:
        """
        Извлекает структурированный список элементов (письма, вакансии, товары)
        
        Использует эвристики для определения контейнеров списка:
        - Родительские элементы с множеством дочерних элементов
        - Элементы с похожей структурой (карточки, строки таблицы)
        """
        try:
            logger.info(f"📋 Извлечение списка элементов (максимум {max_count})")
            
            items = self.page.evaluate("""(maxCount) => {
                // Ищем контейнеры со списками
                const containers = Array.from(document.querySelectorAll('div, section, article, ul, ol'));
                
                // Фильтруем контейнеры, которые выглядят как списки
                const listContainers = containers.filter(container => {
                    // Считаем "дочерние карточки"
                    const children = Array.from(container.children).filter(child => {
                        const rect = child.getBoundingClientRect();
                        return rect.width > 100 && rect.height > 50;
                    });
                    return children.length >= 2 && children.length <= 50;
                });
                
                if (listContainers.length === 0) {
                    return [];
                }
                
                // Берём первый подходящий контейнер
                const container = listContainers[0];
                const items = Array.from(container.children).filter(child => {
                    const rect = child.getBoundingClientRect();
                    return rect.width > 100 && rect.height > 50;
                });
                
                // Извлекаем данные из каждого элемента
                return items.slice(0, maxCount).map((item, idx) => {
                    try {
                        // Ищем текстовые узлы внутри элемента
                        const walker = document.createTreeWalker(
                            item,
                            NodeFilter.SHOW_TEXT,
                            null,
                            false
                        );
                        
                        let texts = [];
                        while (walker.nextNode()) {
                            const text = walker.currentNode.textContent.trim();
                            if (text && text.length > 2 && text.length < 200) {
                                texts.push(text);
                            }
                        }
                        
                        // Берём первые 3-5 значимых текстов
                        const relevantTexts = texts.slice(0, 5);
                        
                        // Ищем ссылки
                        const links = Array.from(item.querySelectorAll('a')).map(a => 
                            a.href || a.getAttribute('href') || ''
                        ).filter(Boolean);
                        
                        return {
                            index: idx,
                            texts: relevantTexts,
                            links: links.slice(0, 2),
                            htmlTag: item.tagName.toLowerCase(),
                            className: (item.className || '').split(' ')[0]
                        };
                    } catch (e) {
                        return {
                            index: idx,
                            texts: ['error'],
                            links: [],
                            htmlTag: 'unknown'
                        };
                    }
                });
            }""", max_count)
            
            if not items:
                items = []
                logger.warning("⚠️ Элементы списка не найдены")
            
            logger.info(f"✅ Извлечено {len(items)} элементов списка")
            
            # Формируем человекочитаемый текст для каждого элемента
            formatted_items = []
            for item in items:
                text = " | ".join(item.get("texts", []))
                formatted_items.append(f"[{item.get('index')}] {text}")
            
            return {
                "success": True,
                "items": items,
                "formatted_items": formatted_items,
                "count": len(items),
                "message": f"Извлечено {len(items)} элементов списка"
            }
            
        except Exception as e:
            error_msg = f"Ошибка извлечения списка: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": error_msg
            }
    
    def extract_table_data(self, max_rows: int = 10) -> Dict[str, Any]:
        """
        Извлекает данные из таблиц (например, для почты, вакансий)
        """
        try:
            logger.info(f"📊 Извлечение данных из таблицы (максимум {max_rows} строк)")
            
            table_data = self.page.evaluate("""(maxRows) => {
                // Ищем таблицы на странице
                const tables = Array.from(document.querySelectorAll('table'));
                
                if (tables.length === 0) {
                    return {headers: [], rows: []};
                }
                
                // Берём первую таблицу
                const table = tables[0];
                
                // Извлекаем заголовки
                const headers = [];
                const headerRows = table.querySelectorAll('thead tr, tr:first-child');
                if (headerRows.length > 0) {
                    const headerCells = headerRows[0].querySelectorAll('th, td');
                    headerCells.forEach(cell => {
                        headers.push(cell.textContent.trim());
                    });
                }
                
                // Извлекаем строки
                const rows = [];
                const bodyRows = table.querySelectorAll('tbody tr, tr');
                
                bodyRows.forEach((row, idx) => {
                    if (idx >= maxRows) return;
                    
                    // Пропускаем строку заголовка
                    if (row.querySelector('th') && headers.length > 0 && idx === 0) return;
                    
                    const cells = row.querySelectorAll('td');
                    const rowData = [];
                    
                    cells.forEach(cell => {
                        rowData.push(cell.textContent.trim());
                    });
                    
                    if (rowData.length > 0) {
                        rows.push({
                            index: rows.length,
                            data: rowData  // ← ИСПРАВЛЕНО: было "rowData"
                        });
                    }
                });
                
                return {headers, rows};
            }""", max_rows)
            
            headers = table_data.get("headers", [])
            rows = table_data.get("rows", [])
            
            logger.info(f"✅ Извлечено {len(rows)} строк таблицы")
            
            # Формируем человекочитаемый формат
            formatted_rows = []
            for row in rows:
                if headers:
                    row_dict = {}
                    for i, header in enumerate(headers):
                        if i < len(row["data"]):
                            row_dict[header] = row["data"][i]
                    formatted_rows.append(row_dict)
                else:
                    formatted_rows.append(row["data"])
            
            return {
                "success": True,
                "headers": headers,
                "rows": rows,
                "formatted_rows": formatted_rows,
                "count": len(rows),
                "message": f"Извлечено {len(rows)} строк таблицы"
            }
            
        except Exception as e:
            error_msg = f"Ошибка извлечения таблицы: {str(e)}"
            logger.error(f"❌ {error_msg}")
            import traceback
            logger.error(traceback.format_exc())
            
            return {
                "success": False,
                "error": error_msg
            }
    
    def extract_element_text(self, index: int) -> Dict[str, Any]:
        """
        Извлекает полный текст конкретного элемента (для чтения письма, описания вакансии)
        """
        try:
            logger.info(f"📖 Извлечение текста элемента #{index}")
            
            text = self.page.evaluate("""(idx) => {
                const selectors = 'div, article, section, p, span, li';
                const elements = Array.from(document.querySelectorAll(selectors));
                
                const visibleElements = elements.filter(el => {
                    try {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 50 &&
                            rect.height > 20 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        );
                    } catch (e) {
                        return false;
                    }
                });
                
                if (idx >= visibleElements.length) {
                    return null;
                }
                
                const element = visibleElements[idx];
                
                // Извлекаем весь текст внутри элемента
                return element.textContent.trim();
            }""", index)
            
            if text:
                logger.info(f"✅ Извлечён текст ({len(text)} символов)")
                return {
                    "success": True,
                    "text": text[:2000],  # Ограничиваем для контекста
                    "full_text_length": len(text),
                    "message": f"Извлечён текст элемента #{index}"
                }
            else:
                error_msg = f"Элемент #{index} не найден или пустой"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"Ошибка извлечения текста: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def check_checkbox(self, index: int) -> Dict[str, Any]:
        """
        Отмечает/снимает чекбокс по индексу
        """
        try:
            logger.info(f"☑️ Работа с чекбоксом #{index}")
            
            result = self.page.evaluate("""(idx) => {
                const selectors = 'input[type="checkbox"], [role="checkbox"]';
                const elements = Array.from(document.querySelectorAll(selectors));
                
                const visibleElements = elements.filter(el => {
                    try {
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 5 &&
                            rect.height > 5 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        );
                    } catch (e) {
                        return false;
                    }
                });
                
                if (idx >= visibleElements.length) {
                    return {found: false};
                }
                
                const checkbox = visibleElements[idx];
                const currentlyChecked = checkbox.checked;
                checkbox.click();
                
                return {
                    found: true,
                    was_checked: currentlyChecked,
                    now_checked: !currentlyChecked
                };
            }""", index)
            
            if result.get("found"):
                action = "отмечен" if result.get("now_checked") else "снят"
                logger.info(f"✅ Чекбокс #{index} {action}")
                return {
                    "success": True,
                    "message": f"Чекбокс #{index} {action}",
                    "was_checked": result.get("was_checked"),
                    "now_checked": result.get("now_checked")
                }
            else:
                error_msg = f"Чекбокс #{index} не найден"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"Ошибка работы с чекбоксом: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def hover_element(self, index: int) -> Dict[str, Any]:
        """
        Наводит курсор на элемент (для раскрытия меню, тултипов)
        """
        try:
            logger.info(f"👆 Наведение на элемент #{index}")
            
            element = self.page.evaluate_handle(f"""() => {{
                const selectors = 'a, button, div, span, li, [role]';
                const elements = Array.from(document.querySelectorAll(selectors));
                
                const visibleElements = elements.filter(el => {{
                    try {{
                        const rect = el.getBoundingClientRect();
                        const style = window.getComputedStyle(el);
                        return (
                            rect.width > 10 &&
                            rect.height > 10 &&
                            style.display !== 'none' &&
                            style.visibility !== 'hidden'
                        );
                    }} catch (e) {{
                        return false;
                    }}
                }});
                
                return visibleElements[{index}];
            }}""")
            
            if element and element.as_element():
                element_handle = element.as_element()
                element_handle.hover(timeout=5000)
                time.sleep(0.5)
                
                logger.info(f"✅ Навели на элемент #{index}")
                return {
                    "success": True,
                    "message": f"Навели на элемент #{index}"
                }
            else:
                error_msg = f"Элемент #{index} не найден"
                logger.warning(f"⚠️ {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
            
        except Exception as e:
            error_msg = f"Ошибка наведения: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
    
    def wait_for_element(self, selector: str, timeout: int = 10000) -> Dict[str, Any]:
        """
        Ждёт появления элемента на странице
        """
        try:
            logger.info(f"⏱️ Ожидание элемента: {selector}")
            
            self.page.wait_for_selector(selector, timeout=timeout, state="visible")
            time.sleep(0.5)
            
            logger.info(f"✅ Элемент появился: {selector}")
            return {
                "success": True,
                "message": f"Элемент появился: {selector}"
            }
            
        except PlaywrightTimeoutError:
            error_msg = f"Таймаут ожидания элемента: {selector}"
            logger.warning(f"⚠️ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"Ошибка ожидания элемента: {str(e)}"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }