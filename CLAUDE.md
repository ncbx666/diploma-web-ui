# CLAUDE.md

Веб-сервис на стандартном `http.server`: принимает Excel с погодой и возвращает `.xlsx` с прогнозом болезни (пирикуляриоз риса, Краснодар; фитофтороз картофеля, Гатчина). Модели обучены в репозитории `diploma`. Деплой на Render: https://diploma-web-ui.onrender.com/

## Команды

- Установка: `pip install -r requirements.txt`
- Запуск: `python -m app.server` (`HOST`/`PORT`, по умолчанию 127.0.0.1:8000)
- Тесты: `uv run --no-project --with pandas --with scikit-learn --with openpyxl --with joblib --with pytest python -m pytest -q`

## Где что

- `app/server.py` — HTTP-сервер и загрузка файла
- `app/inference.py` — профили сценариев (модель, признаки, подписи), нормализация колонок, инференс
- `app/templates/`, `app/static/` — страница загрузки
- `models/` — `*.joblib` и конфиги обучения; название модели в README и `model_label` в `inference.py` должны совпадать с файлом
