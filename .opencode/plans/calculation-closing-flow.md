# План: переход calculation → closing + restart

После расчёта материалов бот говорит «отлично, обратитесь на стойку заказов» и предлагает начать заново.

## Изменения

### 1. `app/state.py`
Добавить `"calculation_shown": False` в `DEFAULT_STATE`.

### 2. `app/fsm.py`
В `next_stage()` — переход `calculation → closing`, когда `calculation_shown == True`:
```python
elif current == "calculation":
    if state.get("calculation_shown"):
        return "closing"
```

### 3. `app/agent_fsm.py`
- После успешного `calculate_material()` (блок `calculation`, строка ~163) — установить `calculation_shown = True` через `update_state()`.
- В начале `run_fsm_agent()` — если `extracted.get("restart")` и стадия `closing`, вызвать `reset_state()` и вернуть приветственное сообщение (до 30 строки раньше, чтобы не тащить остальной код).

### 4. `app/extractor.py`
- Добавить `"restart": true/false — пользователь хочет начать подбор заново` в оба промпта (`EXTRACT_PROMPT` и `EXTRACT_WITH_PRODUCTS_PROMPT`).

### 5. `app/prompts.py`
- Обновить `STAGE_RULES["closing"]`:
```
- Подведи итог выбора: товар, количество упаковок, общая стоимость.
- Скажи клиенту: «Отлично! С этими данными обратитесь, пожалуйста, на стойку заказов. Рад, что смог быть полезным!»
- Спроси, хочет ли клиент начать подбор заново.
```
