#!/usr/bin/env python3
"""Однократная подготовка авторизованной сессии"""
import os
from playwright.sync_api import sync_playwright

os.makedirs("browser_data", exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, args=["--start-maximized"])
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()
    
    print("1. В браузере открой: https://mail.yandex.ru")
    print("2. Войди в ТЕСТОВЫЙ аккаунт (без 2FA!)")
    print("3. Дождись загрузки списка писем")
    print("4. НЕ ЗАКРЫВАЯ браузер, нажми ENTER здесь")
    
    page.goto("https://mail.yandex.ru", timeout=60000)
    input("\n>>> Нажми ENTER после входа: ")
    
    # Сохраняем сессию ДО закрытия браузера
    context.storage_state(path="browser_data/storage_state.json")
    print("\n✅ Сессия сохранена! Файл: browser_data/storage_state.json")
    
    browser.close()