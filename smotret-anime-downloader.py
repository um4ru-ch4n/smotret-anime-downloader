import os
import re
import time
import requests
import csv
import json

from requests.exceptions import ReadTimeout, ConnectionError
from http.client import IncompleteRead
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from tqdm import tqdm


# === Константы ===
LOGIN_URL = "https://smotret-anime.online/users/login"  # login URL
LOGIN = ""  # your login for authorization
PASSWORD = ""    # your password
ANIME_URL = "https://smotret-anime.online/catalog/naruto-shippuuden-4530/128-seriya-91114/russkie-subtitry-732269"  # Ссылка на серию аниме начиная с которой нужно начинать скачивать
DOWNLOAD_DIR = "downloads"  # Папка, куда будут качаться файлы
CHROMEDRIVER_PATH = "./chromedriver.exe"  # Путь к chromedriver
TRANSLATION_TYPE = "Русские субтитры"  # Пример: Raw, Японские субтитры, Английские субтитры, Английская озвучка, Украинская озвучка, Русские субтитры или Озвучка
TRANSLATION_VARIANTS = ["yakusub studio", "yakusub studio (bd)", "Bokusatsu Shiden Team"]  # Список предпочитаемых озвучек/субтитров

MAX_CONCURRENT_DOWNLOADS = 5    # Одновременное кол-во скачиваний. Рекомендуется ставить не более 5

# === Selenium Setup ===
options = Options()
options.add_experimental_option("prefs", {
    "download.default_directory": os.path.abspath(DOWNLOAD_DIR),
    "download.prompt_for_download": False,
    "directory_upgrade": True,
    "safebrowsing.enabled": True
})

options.add_argument("--headless=new")  # Можно закомментировать строку если хотите смотреть как в браузере кнопочки нажимаются
service = Service(executable_path=CHROMEDRIVER_PATH)
driver = webdriver.Chrome(service=service, options=options)
wait = WebDriverWait(driver, 20)

# === Авторизация ===
def login():
    driver.get(LOGIN_URL)
    wait.until(EC.presence_of_element_located((By.NAME, "LoginForm[username]"))).send_keys(LOGIN)
    driver.find_element(By.NAME, "LoginForm[password]").send_keys(PASSWORD)
    login_btn = driver.find_element(By.XPATH, "//button[normalize-space(text())='Войти']")
    login_btn.click()

# === Получить название аниме ===
def get_anime_title():
    h2 = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h2.line-1 a")))
    return re.sub(r'[\\/*?:"<>|]', "", h2.text)

# === Получить номер текущего эпизода ===
def get_current_episode_number():
    prev_num, next_num = None, None

    try:
        prev_btn = driver.find_element(By.CSS_SELECTOR, "div.m-select-sibling-episode a i.left")
        prev_text = prev_btn.find_element(By.XPATH, "..").text.strip()
        prev_num = int(re.search(r'\d+', prev_text).group()) if prev_text else None
    except:
        pass

    try:
        next_btn = driver.find_element(By.CSS_SELECTOR, "div.m-select-sibling-episode a i.right")
        next_text = next_btn.find_element(By.XPATH, "..").text.strip()
        next_num = int(re.search(r'\d+', next_text).group()) if next_text else None
    except:
        pass

    if prev_num is not None and next_num is not None:
        return (prev_num + next_num) // 2
    elif next_num is not None:
        return next_num - 1
    elif prev_num is not None:
        return prev_num + 1
    else:
        return 1


# === Перейти к следующей серии ===
def go_to_next_episode():
    try:
        current_url = driver.current_url

        next_btn = driver.find_element(By.CSS_SELECTOR, "div.m-select-sibling-episode a i.right")
        next_btn.find_element(By.XPATH, "..").click()

        # Ждём пока изменится URL
        WebDriverWait(driver, 10).until(EC.url_changes(current_url))

        # Ждём появления блока загрузки видео как индикатора, что всё прогрузилось
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "m-translation-view-download"))
        )
        
        return True
    except:
        return False


def select_translation(driver, wait):
    # Выбор типа перевода (RAW, Субтитры, Озвучка и т.п.)
    try:
        type_container = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "m-select-translation-type")))
        type_links = type_container.find_elements(By.TAG_NAME, "a")
        desired_type = TRANSLATION_TYPE.strip().lower()

        for link in type_links:
            link_text = link.text.strip().lower()
            if link_text == desired_type and "active" not in link.get_attribute("class"):
                print(f"🎛 Переключаем тип перевода на: {TRANSLATION_TYPE}")
                link.click()
                time.sleep(1)
                break
    except Exception as e:
        print(f"⚠️ Не удалось выбрать тип перевода: {e}")

    # Выбор варианта перевода (по списку приоритетов)
    try:
        variant_container = driver.find_element(By.CLASS_NAME, "m-select-translation-variant")
        variant_links = variant_container.find_elements(By.TAG_NAME, "a")

        found_any = False

        for preferred in TRANSLATION_VARIANTS:
            desired_variant = preferred.strip().lower()
            for link in variant_links:
                link_text = link.text.strip().lower()
                if desired_variant in link_text:
                    found_any = True
                    if "current" not in link.get_attribute("class"):
                        print(f"🎛 Переключаем вариант перевода на: {link.text.strip()}")
                        link.click()
                        time.sleep(1)
                    else:
                        print(f"🎧 Вариант перевода уже выбран: {link.text.strip()}")
                    return  # закончили после первого совпадения

        if not found_any:
            print("ℹ️ Ни один желаемый вариант перевода не найден — будет использоваться по умолчанию.")
    except Exception:
        print("ℹ️ Варианты перевода не найдены — используется вариант по умолчанию.")


# === Собрать ссылки на все серии ===
def extract_download_links():
    links = []

    while True:
        episode_num = get_current_episode_number()

        # ⚙️ Автоматический выбор перевода и варианта
        select_translation(driver, wait)

        video_link = None
        subs_link = None

        try:
            container = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "m-translation-view-download")))
            for quality in ["Скачать видео (1080p)", "Скачать видео (720p)", "Скачать видео (536p)", "Скачать видео (406p)", "Скачать видео (360p)", "Скачать видео (356p)"]:
                try:
                    el = container.find_element(By.XPATH, f".//a[normalize-space(text())='{quality}']")
                    video_link = el.get_attribute("href")
                    if video_link:
                        break
                except:
                    continue
        except:
            pass

        try:
            subs_el = driver.find_element(By.XPATH, "//a[normalize-space(text())='Скачать субтитры']")
            subs_link = subs_el.get_attribute("href")
        except:
            pass

        links.append({
            "episode": episode_num,
            "video_url": video_link,
            "subs_url": subs_link
        })

        print(f"🔗 Серия {episode_num}: ссылки собраны")

        if not go_to_next_episode():
            break
        time.sleep(3)

    return links


def format_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = 0
    p = 1024
    size = float(size_bytes)
    while size >= p and i < len(size_name) - 1:
        size /= p
        i += 1
    return f"{size:.2f} {size_name[i]}"


def is_file_valid(url, filename, cookies):
    if not os.path.exists(filename):
        return False

    try:
        with requests.get(url, cookies=cookies, stream=True, timeout=2) as r:
            r.raise_for_status()
            content_length = int(r.headers.get('Content-Length', 0))
            if content_length == 0:
                print(f"⚠️ Content-Length не найден для {filename}")
                return False
            file_size = os.path.getsize(filename)
            if file_size == content_length:
                return True
            else:
                print(f"⚠️ Размер файла не совпадает: {format_size(file_size)} != {format_size(content_length)}")
                return False
    except Exception as e:
        print(f"⚠️ Не удалось определить размер удалённого файла: {e}")
        return False


def download_file(url, filename, cookies, retries=3):
    if is_file_valid(url, filename, cookies):
        print(f"⏭ Пропускаем (файл целый): {filename}")
        return

    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, cookies=cookies, stream=True, timeout=(10, 120)) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('Content-Length', 0))
                block_size = 8192
                progress = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=os.path.basename(filename),
                    leave=False
                )
                with open(filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=block_size):
                        if chunk:
                            f.write(chunk)
                            progress.update(len(chunk))
                progress.close()
            print(f"✅ Скачан: {filename}")
            return
        except (IncompleteRead, ReadTimeout, ConnectionError) as e:
            print(f"⚠️ Попытка {attempt}/{retries} не удалась при скачивании {filename}: {e}")
            time.sleep(2)
        except Exception as e:
            print(f"❌ Неизвестная ошибка при скачивании {filename}: {e}")
            break
    print(f"❌ Не удалось скачать {filename} после {retries} попыток.")


def save_episode_data(anime_folder, episodes, cookies):
    csv_path = os.path.join(anime_folder, "episodes.csv")
    json_path = os.path.join(anime_folder, "cookies.json")

    with open(csv_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["episode", "video_url", "subs_url"])
        writer.writeheader()
        for ep in episodes:
            writer.writerow(ep)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cookies, f)

    print(f"💾 Ссылки и куки сохранены: {csv_path}, {json_path}")


def load_episode_data(anime_folder):
    csv_path = os.path.join(anime_folder, "episodes.csv")
    json_path = os.path.join(anime_folder, "cookies.json")

    episodes = []
    if os.path.exists(csv_path) and os.path.exists(json_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                episodes.append({
                    "episode": int(row["episode"]),
                    "video_url": row["video_url"] or None,
                    "subs_url": row["subs_url"] or None
                })

        with open(json_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)

        print(f"📂 Загружены ссылки из кэша: {csv_path}")
        return episodes, cookies
    else:
        return None, None



# === Основной запуск ===
def main():
    login()
    time.sleep(3)

    driver.get(ANIME_URL)

    # Получаем название и создаём папку
    anime_title = get_anime_title()
    anime_folder = os.path.join(DOWNLOAD_DIR, anime_title)
    os.makedirs(anime_folder, exist_ok=True)
    print(f"\n📂 Скачиваем в папку: {anime_folder}")

    episodes, cookies = load_episode_data(anime_folder)

    if not episodes:
        episodes = extract_download_links()
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        save_episode_data(anime_folder, episodes, cookies)
        driver.quit()
    else:
        driver.quit()
        print(f"🔁 Используем кэшированные ссылки — вход на сайт не требуется")

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_DOWNLOADS) as executor:
        for ep in episodes:
            ep_num = ep["episode"]

            if ep["video_url"]:
                ext = re.search(r'/translations/([^/]+)/', ep["video_url"]).group(1)
                filename = os.path.join(anime_folder, f"episode_{ep_num:02d}.{ext}")
                executor.submit(download_file, ep["video_url"], filename, cookies)

            if ep["subs_url"]:
                ext = re.search(r'/translations/([^/]+)/', ep["subs_url"]).group(1)
                filename = os.path.join(anime_folder, f"episode_{ep_num:02d}.{ext}")
                executor.submit(download_file, ep["subs_url"], filename, cookies)

if __name__ == "__main__":
    main()
