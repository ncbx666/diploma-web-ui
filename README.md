# Прогноз болезней растений

Минималистичный Python-сайт для загрузки Excel-файла с погодными данными и получения размеченного `.xlsx` с прогнозом наступления болезни.

Доступные сценарии:

- пирикуляриоз риса в Краснодаре: `krasnodar_model_results_optuna_10/random_forest_f1_0.741`;
- фитофтороз картофеля в Гатчине: `golitcino_model_results_optuna_50/random_forest_f1_0.691`.

## Запуск

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m app.server
```

После запуска откройте `http://127.0.0.1:8000`.

## Что делает сервис

1. Принимает `.xlsx` с листами погодных данных.
2. Даёт выбрать болезнь и модель.
3. Нормализует названия колонок из исходных датасетов.
4. Возвращает Excel-файл с листами:
   - `marked_data` — исходные строки и колонки прогноза;
   - `summary` — краткая сводка по обработке.

## Признаки

### Пирикуляриоз риса, Краснодар

Модель ждёт колонки:

`year`, `day`, `t_min`, `t_max`, `is_rain`, `precipitation`, `t_avg`, `cloudiness`, `t_gt_7`.

Допустимые исходные названия из Excel:

- `year` или `год` — год;
- `day` — день года;
- `T_min` — минимальная температура;
- `T_max` — максимальная температура;
- `Is_rain` — флаг дождя: 1 или 0;
- `Precipitation` — осадки;
- `T_avg` — средняя температура;
- `Cloudines` или `Cloudiness` — облачность;
- `T>7` — температурный признак `t_gt_7`.

Если `T_avg` отсутствует, сервис считает его как `(t_min + t_max) / 2`. Если `T>7` отсутствует, используется `t_avg`.

### Фитофтороз картофеля, Гатчина

Модель ждёт колонки:

`year`, `day`, `t_min`, `t_max`, `is_rain`, `precipitation`, `t_avg`, `cloudiness`, `precipitation_t_gt_10`, `t_gt_10`.

Допустимые исходные названия из Excel:

- `year`, `год` или `Unnamed: 0` — год;
- `day` — день года;
- `T_min` — минимальная температура;
- `T_max` — максимальная температура;
- `Is_rain` — флаг дождя: 1 или 0;
- `Precipitation` — осадки;
- `T_avg` — средняя температура;
- `Cloudiness` или `Cloudines` — облачность;
- `Precipitation_T_gt_10` — осадки при температуре выше 10 градусов;
- `T>10` — температурный признак `t_gt_10`.

Если `Precipitation_T_gt_10` отсутствует, сервис считает его из `precipitation` и `t_avg`: осадки сохраняются только для строк, где `t_avg > 10`, иначе ставится 0. Если `T>10` отсутствует, используется `t_avg`.

## Проверка

```bash
python -m pytest
```

Если `pytest` не установлен, можно выполнить быструю проверку инференса:

```bash
python - <<'PY'
from app.inference import predict_workbook
result = predict_workbook("../Данные Краснодар 2012-2021.xlsx", "krasnodar_rice_blast")
print(result.rows, result.event_count)
PY
```
