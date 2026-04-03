# midi_assistant

## Настройка YandexGPT парсера

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

### 2. Настройте переменные окружения

Скопируйте файл `.env.example` в `.env` и укажите ваши учетные данные:

```bash
cp .env.example .env
```

Отредактируйте файл `.env`:

```
YC_API_KEY=your_api_key_here
YC_FOLDER_ID=your_folder_id_here
```

Получить API ключ можно в [Yandex Cloud Console](https://console.cloud.yandex.ru/).

### 3. Запустите парсер

```bash
python parse_products_gpt.py
```

Скрипт:
- Прочитает все названия продуктов из `products.db`
- Отправит каждое название в YandexGPT для извлечения характеристик
- Сохранит структурированные данные в таблицу `floor_covering_specs`

## Логирование

Все действия логируются с помощью библиотеки `loguru`:

- **Консоль** — вывод сообщений уровня INFO и выше
- **Файл** — детальные логи в папке `logs/` с ротацией по дням (уровень DEBUG)

Логи автоматически исключены из системы контроля версий.

## Извлекаемые поля

- `product_type` - тип продукта (Ламинат, Винил, LVT, SPC и т.д.)
- `brand` - бренд/производитель
- `collection` - коллекция
- `model` - модель/название дизайна
- `length_mm` - длина в мм
- `width_mm` - ширина в мм
- `thickness_mm` - толщина в мм
- `length_m` - длина в метрах
- `pieces_per_pack` - количество штук в упаковке
- `area_per_pack_m2` - площадь в м² в упаковке
- `packs_per_pallet` - количество упаковок на паллете
- `wear_class` - класс износостойкости

## Пример

**Входное название:**
```
Ламинат EUROHOME MAJESTIC Дуб Викинг Золотой 1285*192*8мм (9шт/уп,2.22кв.м,52уп/пал) 33класс
```

**Результат:**
```json
{
  "product_type": "Ламинат",
  "brand": "EUROHOME",
  "collection": "MAJESTIC",
  "model": "Дуб Викинг Золотой",
  "length_mm": 1285,
  "width_mm": 192,
  "thickness_mm": 8,
  "pieces_per_pack": 9,
  "area_per_pack_m2": 2.22,
  "packs_per_pallet": 52,
  "wear_class": "33класс"
}
```

> **Важно:** Файл `.env` содержит конфиденциальные данные и не должен попадать в систему контроля версий. Он автоматически исключен через `.gitignore`.