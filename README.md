# 📥 smotret-anime-downloader

Скрипт для автоматической загрузки аниме-серий с сайта [https://smotret-anime.online](https://smotret-anime.online), с поддержкой:

- Авторизации
- Выбора перевода и озвучки
- Сбора всех серий
- Кэширования ссылок
- Многопоточной загрузки с прогресс-барами
- Проверки целостности файлов

---

## 🚀 Установка (Anaconda + Conda)

### 1. Установи [Anaconda](https://www.anaconda.com/products/distribution) (если не установлена)

---

### 2. Создай новое виртуальное окружение:

```bash
conda create -n smotret-anime-downloader python=3.13 -y
```

---

### 3. Активируй окружение:

```bash
conda activate smotret-anime-downloader
```

---

### 4. Установи зависимости:

```bash
conda env update --file environment.yml --prune
```

---

### 5. Скачай [ChromeDriver](https://chromedriver.chromium.org/downloads)

- Выбери версию, соответствующую твоему Google Chrome
- Скачай и положи `chromedriver.exe` рядом со скриптом. (Можно положить и в другое место, но не забудь обновить переменную с путем к драйверу.)
- Обнови путь `CHROMEDRIVER_PATH` в `smotret-anime-downloader.py`, если нужно

---

## ▶ Запуск скрипта

1. Активируй окружение:

```bash
conda activate smotret-anime-downloader
```

2. Запусти скрипт:

```bash
python smotret-anime-downloader.py
```

---

## ⚙ Настройки внутри скрипта:

Открой файл `smotret-anime-downloader.py` и измени:

```python
LOGIN_URL = "https://smotret-anime.online/users/login"  # Ссылка на страницу с формой авторизации
LOGIN = ""  # Логин для авторизации
PASSWORD = ""    # Пароль для авторизации
ANIME_URL = "https://smotret-anime.online/catalog/naruto-shippuuden-4530/128-seriya-91114/russkie-subtitry-732269"  # Ссылка на серию аниме начиная с которой нужно начинать скачивать
DOWNLOAD_DIR = "downloads"  # Папка, куда будут качаться файлы
CHROMEDRIVER_PATH = "./chromedriver.exe"  # Путь к chromedriver
TRANSLATION_TYPE = "Русские субтитры"  # Пример: Raw, Японские субтитры, Английские субтитры, Английская озвучка, Украинская озвучка, Русские субтитры или Озвучка
TRANSLATION_VARIANTS = ["yakusub studio", "yakusub studio (bd)", "Bokusatsu Shiden Team"]  # Список предпочитаемых озвучек/субтитров
```

---

## 📦 Кэширование

- При первом запуске:
  - Происходит авторизация и парсинг ссылок
  - В `downloads/<название аниме>/` сохраняются:
    - `episodes.csv` — список серий
    - `cookies.json` — авторизационные куки
- При следующих запусках:
  - Ссылки берутся из кэша
  - Авторизация не требуется

---

## 🎛 Прочее

- Поддержка `--headless=new` для запуска без GUI (уже включено)
- Если хочешь видеть браузер — закомментируй эту строку:
  ```python
  options.add_argument("--headless=new")
  ```

---

## ❓ Возможные проблемы

- ❌ **Content-Length не найден** — сервер не прислал размер файла, скрипт всё равно скачает
- ⚠ **Размер файла не совпадает** — файл перекачается заново
- 🧼 Скрипт сам пропускает уже скачанные и целые файлы
