import os
import sys
import zipfile
import requests
from constants import PLUGINS_DIR, PLUGINS_INDEX_URL, plugin_commands, plugin_hooks, COLOR_GREEN, COLOR_RED, COLOR_CYAN, COLOR_YELLOW, COLOR_RESET
from utils import download_with_retry

class PluginAPI:
    def __init__(self, module):
        self.module = module
    def get_plugin_path(self):
        return os.path.dirname(self.module.__file__)
    def register_command(self, name, func, hidden=False):
        plugin_commands[name] = {'func': func, 'hidden': hidden}
    def register_banner_hook(self, func):
        plugin_hooks['banner'].append(func)
    def register_info_hook(self, func):
        plugin_hooks['info'].append(func)
    def get_data_dir(self):
        from constants import LAUNCHER_DATA_DIR
        return LAUNCHER_DATA_DIR
    def get_plugins_dir(self):
        return PLUGINS_DIR

def load_plugins():
    if not os.path.exists(PLUGINS_DIR):
        os.makedirs(PLUGINS_DIR)
    sys.path.insert(0, PLUGINS_DIR)
    for file in os.listdir(PLUGINS_DIR):
        if file.endswith(".py") and file != "__init__.py":
            module_name = file[:-3]
            try:
                module = __import__(module_name)
                if hasattr(module, "register_plugin"):
                    api = PluginAPI(module)
                    module.register_plugin(api)
                elif hasattr(module, "register_commands"):
                    cmd_dict = {}
                    module.register_commands(cmd_dict)
                    api = PluginAPI(module)
                    for name, func in cmd_dict.items():
                        api.register_command(name, func, hidden=False)
                print(f"{COLOR_GREEN}Загружен плагин: {module_name}{COLOR_RESET}")
            except Exception as e:
                print(f"{COLOR_RED}Ошибка загрузки плагина {module_name}: {e}{COLOR_RESET}")

def manage_plugins():
    print(f"{COLOR_CYAN}ПОЛУЧЕНИЕ СПИСКА ДОСТУПНЫХ ПЛАГИНОВ...{COLOR_RESET}")
    try:
        response = requests.get(PLUGINS_INDEX_URL, timeout=10)
        response.raise_for_status()
        plugins = response.json()
    except Exception as e:
        print(f"{COLOR_RED}Не удалось загрузить список плагинов: {e}{COLOR_RESET}")
        return

    if not plugins:
        print(f"{COLOR_YELLOW}Нет доступных плагинов{COLOR_RESET}")
        return

    while True:
        print(f"\n{COLOR_CYAN}ДОСТУПНЫЕ ПЛАГИНЫ{COLOR_RESET}")
        for i, p in enumerate(plugins, 1):
            print(f"{COLOR_YELLOW}{i}.{COLOR_RESET} {p['name']} - {p['description']}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        print(f"{COLOR_CYAN}в{COLOR_RESET} - назад")
        choice = input(f"{COLOR_YELLOW}Выберите номер для установки: {COLOR_RESET}").strip()
        if choice.lower() == 'в':
            break
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(plugins):
                install_plugin(plugins[idx])
            else:
                print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")

def install_plugin(plugin_info):
    name = plugin_info['name']
    url = plugin_info['download_url']
    print(f"{COLOR_CYAN}Установка плагина '{name}'...{COLOR_RESET}")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        archive_path = os.path.join(PLUGINS_DIR, f"{name}.zip")
        with open(archive_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            members = zip_ref.namelist()
            top_dirs = set(m.split('/')[0] for m in members if '/' in m)
            if len(top_dirs) == 1 and all(m.startswith(next(iter(top_dirs))) for m in members):
                for member in members:
                    target = member.replace(next(iter(top_dirs)) + '/', '', 1)
                    if target:
                        source = zip_ref.open(member)
                        target_path = os.path.join(PLUGINS_DIR, target)
                        if member.endswith('/'):
                            os.makedirs(target_path, exist_ok=True)
                        else:
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            with open(target_path, 'wb') as out:
                                out.write(source.read())
            else:
                zip_ref.extractall(PLUGINS_DIR)
        os.remove(archive_path)
        print(f"{COLOR_GREEN}Плагин '{name}' установлен!{COLOR_RESET}")
        restart_launcher()
    except Exception as e:
        print(f"{COLOR_RED}Ошибка установки: {e}{COLOR_RESET}")

def restart_launcher():
    import sys
    import time
    print(f"{COLOR_GREEN}Перезапуск лаунчера...{COLOR_RESET}")
    time.sleep(1)
    os.execv(sys.executable, [sys.executable] + sys.argv)