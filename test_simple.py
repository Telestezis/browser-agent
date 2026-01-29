from browser_agent import BrowserAgent

agent = BrowserAgent()
try:
    result = agent.think_and_act(
        "Перейди на сайт Яндекса, введи в поиск 'погода Москва' и нажми Enter",
        max_steps=10
    )
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ:")
    print(result)
finally:
    agent.close()