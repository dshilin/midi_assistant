# FSM-based AI Consultant for Building Materials

## Описание

Stateful AI-консультант по напольным покрытиям с FSM-управлением диалогом,
работающий поверх существующей базы продуктов и парсера YandexGPT.

## Архитектура

```
Пользователь → HTML-форма → FastAPI (/chat → /chat)
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

Три слоя: LLM (мышление) → FSM (контроль сценария) → State (память).

## Компоненты

### `state.py`
- In-memory словарь `STATE: Dict[str, dict]`
- `get_state(user_id)` — возвращает копию состояния (или DEFAULT)
- `update_state(user_id, updates, stage)` — обновляет поля и/или стадию
- `reset_state(user_id)` — сбрасывает на DEFAULT

Поля:
- `room_type`, `area`, `type`, `color`, `brand`, `selected_product`, `stage`

### `fsm.py`
- Четыре стадии: `discovery → selection → calculation → closing`
- `next_stage(state)` — определяет следующую стадию по заполненным полям
- Обнаружены type/color → selection. Выбран product → calculation. После → closing.

### `extractor.py`
- Отправляет сообщение пользователя в LLM с промптом на извлечение JSON
- Поля: type, color, area, room_type, brand
- При ошибке парсинга → пустой `{}`

### `db.py`
- `get_products(type, brand, color, limit)` — поиск с фильтрацией
- `get_product_by_id(id)` — один товар
- `calculate_material(area, product_id)` — расчёт упаковок (запас 10%)

### `prompts.py`
- `build_system_prompt(state)` — динамический промпт под стадию
- Поведение: discovery → вопросы, selection → подбор, calculation → расчёт, closing → заявка

### `agent_fsm.py`
1. Извлечение сущностей из сообщения
2. Обновление state
3. Определение следующей стадии через FSM
4. Построение system prompt под стадию
5. Запрос к LLM
6. Возврат ответа + state

### `main.py`
- FastAPI: `GET /` → `static/chat.html`, `POST /chat` → JSON { response, state }

### `static/chat.html`
- Чат-форма, отправляет запросы на `/chat`
- Отображает этап FSM под ответами бота

## Data Flow

```
message → extract_entities() → update state
→ next_stage() → build_system_prompt(state)
→ LLM response → response + state → клиент
```

## FSM Transition Rules

```
discovery  → type || color задан                  → selection
selection  → selected_product задан                → calculation
calculation→ (автоматически)                       → closing
```

FSM пересчитывается на каждом шаге. Если клиент меняет ответы, state
обновляется, и FSM переходит на подходящую стадию.

## Error Handling

- extractor: пустой JSON при ошибке → state не портится
- agent_fsm: заглушка при отсутствии ответа LLM
- db: None при невозможности расчёта
- HTTP: 500 при падении, сообщение об ошибке в форме

## Testing

32 теста (17 существующих + 15 новых):
- `test_parse_products.py` — 17 тестов (парсер, БД, YandexGPT)
- `test_fsm.py` — 15 тестов (state, FSM, prompts)
