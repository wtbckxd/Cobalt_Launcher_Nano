import os
import json
import re
import webbrowser
import requests
from datetime import datetime
from typing import List, Dict
from constants import MINECRAFT_DIR, MODS_FAVORITES_FILE, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_BLUE, COLOR_RESET
from utils import download_with_retry, input_yes_no
from config_manager import load_config

def load_mods_favorites():
    if os.path.exists(MODS_FAVORITES_FILE):
        try:
            with open(MODS_FAVORITES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_mods_favorites(favorites):
    with open(MODS_FAVORITES_FILE, 'w', encoding='utf-8') as f:
        json.dump(favorites, f, indent=4, ensure_ascii=False)

def add_mod_to_favorites(mod_info):
    favorites = load_mods_favorites()
    for fav in favorites:
        if fav.get('id') == mod_info.get('id'):
            print(f"{COLOR_YELLOW}Мод уже в избранном!{COLOR_RESET}")
            return False
    mod_info['added_at'] = datetime.now().isoformat()
    favorites.append(mod_info)
    save_mods_favorites(favorites)
    print(f"{COLOR_GREEN}Мод '{mod_info.get('title', 'Без названия')}' добавлен в избранное!{COLOR_RESET}")
    return True

def remove_mod_from_favorites(mod_id):
    favorites = load_mods_favorites()
    new_favorites = [fav for fav in favorites if fav.get('id') != mod_id]
    if len(new_favorites) < len(favorites):
        save_mods_favorites(new_favorites)
        print(f"{COLOR_GREEN}Мод удален из избранного!{COLOR_RESET}")
        return True
    else:
        print(f"{COLOR_RED}Мод не найден в избранном!{COLOR_RESET}")
        return False

def search_mods_modrinth(query: str, limit: int = 20) -> List[Dict]:
    print(f"{COLOR_CYAN}Поиск модов на Modrinth...{COLOR_RESET}")
    try:
        url = f"https://api.modrinth.com/v2/search?query={query}&limit={limit}&facets=[[\"project_type:mod\"]]"
        headers = {"User-Agent": "CobaltLauncher/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        mods = []
        for hit in data.get('hits', []):
            mod_info = {
                'id': hit.get('project_id'),
                'title': hit.get('title', 'Без названия'),
                'description': hit.get('description', 'Нет описания'),
                'downloads': hit.get('downloads', 0),
                'follows': hit.get('follows', 0),
                'author': hit.get('author', 'Неизвестен'),
                'versions': hit.get('versions', []),
                'icon_url': hit.get('icon_url'),
                'slug': hit.get('slug'),
                'source': 'modrinth'
            }
            mods.append(mod_info)
        return mods
    except Exception as e:
        print(f"{COLOR_RED}Ошибка поиска на Modrinth: {e}{COLOR_RESET}")
        return []

def show_mod_details(mod_info: Dict):
    print(f"\n{COLOR_CYAN}════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_GREEN}Название:{COLOR_RESET} {mod_info.get('title', 'Без названия')}")
    print(f"{COLOR_GREEN}Источник:{COLOR_RESET} {mod_info.get('source', 'Неизвестен').upper()}")
    if 'description' in mod_info:
        desc = mod_info['description']
        if len(desc) > 200:
            desc = desc[:200] + "..."
        print(f"{COLOR_GREEN}Описание:{COLOR_RESET} {desc}")
    if 'downloads' in mod_info:
        print(f"{COLOR_GREEN}Загрузки:{COLOR_RESET} {mod_info['downloads']:,}")
    if 'author' in mod_info:
        print(f"{COLOR_GREEN}Автор:{COLOR_RESET} {mod_info['author']}")
    print(f"{COLOR_CYAN}════════════════════════════════════════════════{COLOR_RESET}")

def get_mod_versions(mod_id: str) -> List[Dict]:
    try:
        url = f"https://api.modrinth.com/v2/project/{mod_id}/version"
        headers = {"User-Agent": "CobaltLauncher/1.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"{COLOR_RED}Ошибка получения версий мода: {e}{COLOR_RESET}")
        return []

def download_mod(mod_info: Dict, game_version: str = None):
    print(f"{COLOR_CYAN}Скачивание мода '{mod_info.get('title')}'...{COLOR_RESET}")
    try:
        mod_id = mod_info.get('id')
        versions = get_mod_versions(mod_id)
        if not versions:
            print(f"{COLOR_RED}Нет доступных версий для скачивания{COLOR_RESET}")
            return
        if game_version:
            compatible_versions = [v for v in versions if game_version in v.get('game_versions', [])]
        else:
            compatible_versions = versions
        if not compatible_versions:
            print(f"{COLOR_YELLOW}Нет версий, совместимых с Minecraft {game_version or 'любой'}{COLOR_RESET}")
            return
        if len(compatible_versions) == 1:
            selected_version = compatible_versions[0]
        else:
            print(f"{COLOR_GREEN}Доступные версии мода:{COLOR_RESET}")
            for i, ver in enumerate(compatible_versions[:10], 1):
                loaders = ', '.join(ver.get('loaders', []))
                mc_versions = ', '.join(ver.get('game_versions', [])[:3])
                print(f"{COLOR_YELLOW}{i}.{COLOR_RESET} {ver.get('version_number')} [Загрузчики: {loaders}] [MC: {mc_versions}...]")
            choice = input(f"{COLOR_YELLOW}Выберите версию (1-{min(10, len(compatible_versions))}): {COLOR_RESET}")
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(compatible_versions):
                    selected_version = compatible_versions[idx]
                else:
                    print(f"{COLOR_RED}Неверный выбор{COLOR_RESET}")
                    return
            else:
                print(f"{COLOR_RED}Неверный выбор{COLOR_RESET}")
                return
        dependencies = selected_version.get('dependencies', [])
        if dependencies:
            print(f"{COLOR_CYAN}Зависимости:{COLOR_RESET}")
            for dep in dependencies:
                if dep.get('dependency_type') == 'required':
                    print(f"  - {dep.get('version_id', 'Неизвестно')} (обязательно)")
        jar_file = None
        for file in selected_version.get('files', []):
            if file.get('filename', '').endswith('.jar'):
                jar_file = file
                break
        if not jar_file:
            print(f"{COLOR_RED}Не найден файл .jar для скачивания{COLOR_RESET}")
            return
        mods_dir = os.path.join(MINECRAFT_DIR, "mods")
        os.makedirs(mods_dir, exist_ok=True)
        download_url = jar_file.get('url')
        filename = jar_file.get('filename', f"mod_{mod_id}.jar")
        filepath = os.path.join(mods_dir, filename)
        print(f"{COLOR_YELLOW}Скачивание {filename}...{COLOR_RESET}")

        def progress_callback(current, total):
            if total > 0:
                percent = (current / total) * 100
                bar_length = 30
                filled = int(bar_length * current / total)
                bar = '█' * filled + '░' * (bar_length - filled)
                print(f"\r{COLOR_CYAN}[{bar}] {percent:.1f}%{COLOR_RESET}", end="")

        success = download_with_retry(download_url, filepath, progress_callback, max_retries=3)
        if success:
            print(f"\n{COLOR_GREEN}✓ Мод успешно скачан: {filepath}{COLOR_RESET}")
        else:
            print(f"\n{COLOR_RED}Не удалось скачать мод{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Ошибка скачивания мода: {e}{COLOR_RESET}")

def manage_mods_menu():
    while True:
        print(f"\n{COLOR_CYAN}УПРАВЛЕНИЕ МОДАМИ{COLOR_RESET}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        print(f"{COLOR_GREEN}Выберите действие:{COLOR_RESET}")
        print(f"{COLOR_YELLOW}1.{COLOR_RESET} Поиск модов на Modrinth")
        print(f"{COLOR_YELLOW}2.{COLOR_RESET} Показать избранные моды")
        print(f"{COLOR_YELLOW}3.{COLOR_RESET} Назад")
        choice = input(f"{COLOR_YELLOW}Выберите: {COLOR_RESET}")
        if choice == '1':
            search_mods_menu()
        elif choice == '2':
            show_favorites_menu()
        elif choice == '3':
            break
        else:
            print(f"{COLOR_RED}Неверный выбор!{COLOR_RESET}")

def search_mods_menu():
    query = input(f"{COLOR_YELLOW}Введите запрос для поиска: {COLOR_RESET}")
    if not query:
        print(f"{COLOR_RED}Запрос не может быть пустым!{COLOR_RESET}")
        return
    mods = search_mods_modrinth(query)
    if not mods:
        print(f"{COLOR_YELLOW}Моды не найдены{COLOR_RESET}")
        return
    while True:
        print(f"\n{COLOR_CYAN}НАЙДЕННЫЕ МОДЫ ({len(mods)}){COLOR_RESET}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        for i, mod in enumerate(mods, 1):
            title = mod.get('title', 'Без названия')
            if len(title) > 40:
                title = title[:37] + "..."
            print(f"{COLOR_YELLOW}{i:3}.{COLOR_RESET} {title}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        print(f"{COLOR_GREEN}Команды:{COLOR_RESET}")
        print(f"{COLOR_CYAN}число{COLOR_RESET} - просмотреть информацию о моде")
        print(f"{COLOR_CYAN}в{COLOR_RESET} - вернуться назад")
        choice = input(f"{COLOR_YELLOW}Выберите мод или команду: {COLOR_RESET}").lower()
        if choice == 'в':
            break
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(mods):
                mod_details_menu(mods[idx])
            else:
                print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Неверная команда{COLOR_RESET}")

def mod_details_menu(mod_info: Dict):
    while True:
        show_mod_details(mod_info)
        print(f"\n{COLOR_GREEN}Действия с модом:{COLOR_RESET}")
        print(f"{COLOR_YELLOW}1.{COLOR_RESET} Скачать мод")
        print(f"{COLOR_YELLOW}2.{COLOR_RESET} Добавить в избранное")
        print(f"{COLOR_YELLOW}3.{COLOR_RESET} Назад")
        choice = input(f"{COLOR_YELLOW}Выберите действие: {COLOR_RESET}")
        if choice == '1':
            config = load_config()
            game_version = config.get("selected_version")
            if game_version:
                match = re.search(r'(\d+\.\d+(?:\.\d+)?)', game_version)
                if match:
                    game_version = match.group(1)
            if not game_version:
                game_version = input(f"{COLOR_YELLOW}Введите версию Minecraft (например, 1.20.1): {COLOR_RESET}")
            download_mod(mod_info, game_version)
        elif choice == '2':
            add_mod_to_favorites(mod_info)
        elif choice == '3':
            break
        else:
            print(f"{COLOR_RED}Неверный выбор!{COLOR_RESET}")

def show_favorites_menu():
    favorites = load_mods_favorites()
    if not favorites:
        print(f"{COLOR_YELLOW}У вас пока нет избранных модов{COLOR_RESET}")
        return
    while True:
        print(f"\n{COLOR_CYAN}ИЗБРАННЫЕ МОДЫ ({len(favorites)}){COLOR_RESET}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        for i, fav in enumerate(favorites, 1):
            title = fav.get('title', 'Без названия')
            if len(title) > 40:
                title = title[:37] + "..."
            source = fav.get('source', 'unknown').upper()
            print(f"{COLOR_YELLOW}{i:3}.{COLOR_RESET} {title} [{source}]")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        print(f"{COLOR_GREEN}Команды:{COLOR_RESET}")
        print(f"{COLOR_CYAN}число{COLOR_RESET} - просмотреть информацию о моде")
        print(f"{COLOR_CYAN}у{COLOR_RESET} - удалить мод из избранного")
        print(f"{COLOR_CYAN}в{COLOR_RESET} - вернуться назад")
        choice = input(f"{COLOR_YELLOW}Выберите мод или команду: {COLOR_RESET}").lower()
        if choice == 'в':
            break
        elif choice == 'у':
            mod_id = input(f"{COLOR_YELLOW}Введите ID мода для удаления: {COLOR_RESET}")
            remove_mod_from_favorites(mod_id)
            favorites = load_mods_favorites()
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(favorites):
                mod_details_menu(favorites[idx])
            else:
                print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Неверная команда{COLOR_RESET}")

def open_alt_mod_site():
    url = "https://ru-minecraft.ru"
    print(f"{COLOR_CYAN}Открытие ru-minecraft.ru в браузере...{COLOR_RESET}")
    try:
        webbrowser.open(url)
        print(f"{COLOR_GREEN}Сайт открыт в браузере!{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Ошибка открытия браузера: {e}{COLOR_RESET}")
        print(f"{COLOR_YELLOW}Вы можете открыть сайт вручную: {url}{COLOR_RESET}")

def get_current_minecraft_version():
    config = load_config()
    version = config.get("selected_version")
    if not version:
        print(f"{COLOR_RED}Сначала установите версию Minecraft!{COLOR_RESET}")
        return None
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version)
    if match:
        return match.group(1)
    return version

def get_mod_download_url_from_modrinth(project_slug, game_version, loader=None):
    api_url = f"https://api.modrinth.com/v2/project/{project_slug}/version"
    headers = {"User-Agent": "CobaltLauncher/1.0"}
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        versions = resp.json()
        versions.sort(key=lambda v: v.get('date_published', ''), reverse=True)
        for ver in versions:
            game_versions = ver.get('game_versions', [])
            loaders = ver.get('loaders', [])
            if game_version in game_versions:
                if loader and loader.lower() not in [l.lower() for l in loaders]:
                    continue
                for file in ver.get('files', []):
                    if file.get('filename', '').endswith('.jar'):
                        return file.get('url')
        print(f"{COLOR_YELLOW}Не найдена версия мода {project_slug} для Minecraft {game_version} с загрузчиком {loader}{COLOR_RESET}")
        return None
    except Exception as e:
        print(f"{COLOR_RED}Ошибка запроса к Modrinth: {e}{COLOR_RESET}")
        return None

def install_mod_from_modrinth(slug, display_name, loader=None):
    game_version = get_current_minecraft_version()
    if not game_version:
        return
    print(f"{COLOR_CYAN}Поиск {display_name} для Minecraft {game_version}...{COLOR_RESET}")
    download_url = get_mod_download_url_from_modrinth(slug, game_version, loader)
    if not download_url:
        print(f"{COLOR_RED}Не удалось найти {display_name}{COLOR_RESET}")
        return
    mods_dir = os.path.join(MINECRAFT_DIR, "mods")
    os.makedirs(mods_dir, exist_ok=True)
    filename = f"{slug}_{game_version}.jar"
    filepath = os.path.join(mods_dir, filename)
    print(f"{COLOR_YELLOW}Скачивание {display_name}...{COLOR_RESET}")
    def progress(current, total):
        if total > 0:
            percent = (current / total) * 100
            bar = '█' * int(percent // 2) + '░' * (50 - int(percent // 2))
            print(f"\r{COLOR_CYAN}[{bar}] {percent:.1f}%{COLOR_RESET}", end="")
    success = download_with_retry(download_url, filepath, progress, max_retries=3)
    if success:
        print(f"\n{COLOR_GREEN}✓ {display_name} установлен в папку модов.{COLOR_RESET}")
    else:
        print(f"\n{COLOR_RED}Не удалось скачать {display_name}{COLOR_RESET}")

def install_optifine():
    print(f"{COLOR_CYAN}OptiFine не поддерживает автоматическую установку через лаунчер.{COLOR_RESET}")
    print(f"{COLOR_YELLOW}Откройте страницу https://optifine.net/downloads, скачайте версию для вашей версии Minecraft и установите вручную.{COLOR_RESET}")
    print(f"{COLOR_YELLOW}После установки OptiFine появится отдельная версия в лаунчере (например, '1.20.1-OptiFine_...').{COLOR_RESET}")
    if input_yes_no("Открыть страницу OptiFine в браузере? (да/нет): "):
        webbrowser.open("https://optifine.net/downloads")

def install_sodium():
    install_mod_from_modrinth("sodium", "Sodium", loader="fabric")

def install_embeddium():
    install_mod_from_modrinth("embeddium", "Embeddium", loader="forge")

def install_modmenu():
    install_mod_from_modrinth("modmenu", "Mod Menu", loader="fabric")

def install_journeymap():
    install_mod_from_modrinth("journeymap", "JourneyMap", loader=None)

def install_xaeros_minimap():
    install_mod_from_modrinth("xaeros-minimap", "Xaero's Minimap", loader=None)

def install_vulkanmod():
    install_mod_from_modrinth("vulkanmod", "VulkanMod", loader=None)

def install_iris():
    install_mod_from_modrinth("iris", "Iris Shaders", loader="fabric")

def install_fabric_api():
    install_mod_from_modrinth("fabric-api", "Fabric API", loader="fabric")

def install_quilted_fabric_api():
    install_mod_from_modrinth("qfapi", "Quilted Fabric API", loader="quilt")

def install_forge_api():
    print(f"{COLOR_CYAN}Forge API встроен в Forge. Убедитесь, что у вас установлен Forge для нужной версии.{COLOR_RESET}")
    print(f"{COLOR_YELLOW}Команда 'установить <версия> forge' установит Forge с API.{COLOR_RESET}")

def install_mod_by_name(mod_name):
    game_version = get_current_minecraft_version()
    if not game_version:
        return
    print(f"{COLOR_CYAN}Поиск мода '{mod_name}' на Modrinth...{COLOR_RESET}")
    search_url = f"https://api.modrinth.com/v2/search?query={mod_name}&limit=5&facets=[[\"project_type:mod\"]]"
    headers = {"User-Agent": "CobaltLauncher/1.0"}
    try:
        resp = requests.get(search_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get('hits', [])
        if not hits:
            print(f"{COLOR_RED}Мод '{mod_name}' не найден на Modrinth{COLOR_RESET}")
            return
        print(f"{COLOR_GREEN}Найдено несколько модов:{COLOR_RESET}")
        for i, hit in enumerate(hits[:5], 1):
            title = hit.get('title', 'Без названия')
            slug = hit.get('slug')
            print(f"{COLOR_YELLOW}{i}.{COLOR_RESET} {title} (slug: {slug})")
        choice = input(f"{COLOR_YELLOW}Выберите номер мода для установки (или 'в' для отмены): {COLOR_RESET}")
        if choice.lower() == 'в':
            return
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(hits):
                slug = hits[idx].get('slug')
                if slug:
                    install_mod_from_modrinth(slug, hits[idx].get('title'), loader=None)
                else:
                    print(f"{COLOR_RED}Ошибка: slug не найден{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Ошибка поиска мода: {e}{COLOR_RESET}")