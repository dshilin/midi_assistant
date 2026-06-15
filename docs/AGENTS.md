# Agent Guide — midi_assistant

## Architecture

Три слоя: LLM (мышление) → FSM (контроль сценария) → State (память).

```
Пользователь → HTML-форма → FastAPI (/chat)
                                    ↓
                            agent_fsm.py
                           ┌────┬────┬────┐
                           │    │    │    │
                          ↓     ↓    ↓    ↓
                     state  fsm  extractor  db
                                      ↓
                                   LLM провайдер
                                   (.env)
```

## Project Structure

```
app/
├── __init__.py
├── main.py                   # FastAPI: GET /, POST /chat
├── agent_fsm.py              # FSM orchestrator
├── state.py                  # User state (in-memory)
├── fsm.py                    # FSM stage transitions
├── extractor.py              # Entity extraction via LLM
├── llm.py                    # LLM client (OpenAI / YandexGPT)
├── prompts.py                # Dynamic system prompt
├── db.py                     # SQLite queries
├── parse_products_gpt.py     # Product name parser (YandexGPT)
├── scrape_products.py        # Web scraper
└── migrate_color.py          # One-time color inference script
tests/
├── test_fsm.py               # State, FSM, prompts tests
├── test_llm.py               # LLM client tests
└── test_parse_products.py    # Parser + DB tests
static/chat.html              # Web chat UI
docs/
├── superpowers/specs/        # Design specs
├── superpowers/plans/        # Implementation plans
└── AGENTS.md                 # This file
```

## FSM Stages

| Stage | Trigger | Behavior |
|-------|---------|----------|
| `discovery` | Начало сессии / нет type и color | Задавать вопросы, узнать потребности |
| `selection` | type или color заданы | Искать товары в БД, предлагать варианты |
| `calculation` | selected_product задан | Расчёт материалов с запасом 10% |
| `objection` | Сомнения клиента | Работа с возражениями |
| `closing` | После calculation | Подвести итог, предложить заказ |

Переходы в `fsm.py:next_stage()`:
- discovery → selection: когда появился type или color
- selection → calculation: когда выбран selected_product
- calculation → closing: автоматически

## State Fields

```python
DEFAULT_STATE = {
    "room_type": None,          # гостиная, спальня, кухня...
    "area": None,               # площадь в м² (число)
    "type": None,               # ламинат, винил, SPC, паркет...
    "color": None,              # белый, темный, серый, венге...
    "brand": None,              # предпочитаемый бренд
    "budget": None,             # бюджет на м² в рублях (число)
    "selected_product": None,   # ID товара
    "stage": "discovery",       # текущая стадия FSM
}
```

## DB Schema (`floor_covering_specs`)

```sql
CREATE TABLE floor_covering_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    product_type TEXT,      -- Ламинат, Винил, SPC, Террасная доска...
    brand TEXT,             -- EUROHOME, KRONOSPAN...
    collection TEXT,        -- MAJESTIC, Castello Classik...
    model TEXT,             -- Дуб Викинг Золотой, Дуб Каньон Белый...
    color TEXT,             -- белый, темный, венге, графит, золотой...
    length_mm REAL,
    width_mm REAL,
    thickness_mm REAL,
    length_m REAL,
    pieces_per_pack INTEGER,
    area_per_pack_m2 REAL,
    packs_per_pallet INTEGER,
    wear_class TEXT,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

## Color Groups (Синонимы цветов)

В `db.py:COLOR_GROUPS` — поиск по цвету расширяется до группы семантически близких цветов:

```python
COLOR_GROUPS = {
    "темный":    ["темный", "черный", "коричневый", "венге", "графит", "вишневый", "шоколадный"],
    "черный":    ["черный", "темный", "венге", "графит"],
    "коричневый":["коричневый", "венге", "шоколадный", "темный"],
    "светлый":   ["светлый", "белый", "желтый", "золотой", "серебристый"],
    "белый":     ["белый", "светлый", "серебристый"],
    "серый":     ["серый", "графит", "серебристый"],
    "золотой":   ["золотой", "желтый", "светлый"],
}
```

Например, поиск `color="темный"` найдет товары с любым из цветов: темный, черный, венге, графит, вишневый, шоколадный.

## Critical Quirks

### 1. SQLite LIKE регистрозависим для кириллицы

`LIKE '%ламинат%'` НЕ находит "Ламинат" с заглавной Л. SQLite не поддерживает case-insensitive для Unicode/кириллицы.

**Фикс в `db.py`**: каждый текстовый параметр ищется в двух вариантах:
```python
query += " AND (s.product_type LIKE ? OR s.product_type LIKE ?)"
params.append(f"%{term}%")
params.append(f"%{term[0].upper() + term[1:]}%")  # с заглавной
```

### 2. YandexGPT возвращает "null" строкой вместо JSON null

В ответе LLM может быть `"null"` (строка) вместо `null` (JSON null). Это затирает state.

**Фикс в `state.py`**:
```python
if v is not None and str(v).lower() != "null":
```

**Фикс в `db.py:_clean()`**: та же проверка для параметров запросов.

### 3. Extractor видит state, а не только текущее сообщение

`extract_entities()` принимает `current_state` и передаёт LLM известные параметры как контекст. Без этого extractor не знает, что пользователь уже указал ранее.

### 4. LLM игнорирует state и переспрашивает известное

Промпт в `prompts.py` содержит жёсткое правило: `НЕ переспрашивай параметры, которые уже есть в ТЕКУЩЕМ СОСТОЯНИИ`. Если YandexGPT продолжает это делать — промпт нужно ужесточать.

### 5. "null" строки в БД

Парсер мог сохранить строку `"null"` (не Python None) в поля БД. `_clean()` в `db.py` обрабатывает это.

## How to Run

```bash
# Server
uvicorn app.main:app --reload

# Parser (требует YC_API_KEY, YC_FOLDER_ID)
python -m app.parse_products_gpt            # все продукты
python -m app.parse_products_gpt --id 70     # один
python -m app.parse_products_gpt --ids 70,71,72  # несколько

# Scraper
python -m app.scrape_products

# Tests
python -m pytest tests/
python -m pytest tests/ -v           # verbose
python -m pytest tests/test_fsm.py  # только FSM тесты

# Color migration (one-time)
python -m app.migrate_color
```

## .env

```env
LLM_PROVIDER=openai              # или "yandex" / "yandexgpt"
LLM_API_KEY=sk-...               # для OpenAI-совместимых
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Для YandexGPT (когда LLM_PROVIDER=yandex):
YC_API_KEY=...
YC_FOLDER_ID=...
```

## Branch

Все текущие изменения в ветке `fsm-ai-consultant`.

## Git Conventions

- `feat:` — новая функциональность
- `fix:` — исправление бага
- `docs:` — документация
- `refactor:` — рефакторинг
- `chore:` — зависимости, конфиги

Всегда коммитить в ветку, не в main/master.
