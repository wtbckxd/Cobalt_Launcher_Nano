import json
import os
import re
from constants import CONFIG_FILE, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_RESET

def load_config():
    default_config = {
        "java_args": "-Xmx2G -Xms1G",
        "selected_version": None,
        "current_account": None,
        "separate_version_dirs": False,
        "java_path": None,
        "java_version": "17",
        "user_commands": {},
        "custom_info_lines": [],
        "servers": [],
        "java_args_by_version": {},
        "java_path_by_version": {}
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        except json.JSONDecodeError:
            return default_config
    return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def set_java_args():
    config = load_config()
    current_args = config.get("java_args", "-Xmx2G -Xms1G")
    print(f"\n{COLOR_CYAN}Текущие общие аргументы Java: {current_args}{COLOR_RESET}")
    print(f"{COLOR_YELLOW}Примеры:{COLOR_RESET}")
    print(f"{COLOR_GREEN}  -Xmx4G -Xms2G{COLOR_RESET}")
    print(f"{COLOR_GREEN}  -Xmx8G -Xms4G -XX:+UseG1GC{COLOR_RESET}")
    new_args = input(f"\n{COLOR_YELLOW}Введите новые общие аргументы (Enter для отмены): {COLOR_RESET}")
    if new_args:
        config["java_args"] = new_args
        save_config(config)
        print(f"{COLOR_GREEN}Общие аргументы обновлены!{COLOR_RESET}")

def set_java_args_for_version(version, args):
    config = load_config()
    config["java_args_by_version"][version] = args
    save_config(config)
    print(f"{COLOR_GREEN}Аргументы для версии {version} сохранены{COLOR_RESET}")

def set_memory(gb):
    if not gb.isdigit():
        print(f"{COLOR_RED}Укажите количество гигабайт числом{COLOR_RESET}")
        return
    gb_int = int(gb)
    if gb_int < 1 or gb_int > 32:
        print(f"{COLOR_RED}Укажите значение от 1 до 32 GB{COLOR_RESET}")
        return
    config = load_config()
    current_args = config.get("java_args", "")
    new_args = re.sub(r"-Xmx\d+G", "", current_args)
    new_args = re.sub(r"-Xms\d+G", "", new_args)
    new_args = re.sub(r"\s+", " ", new_args).strip()
    memory_args = f"-Xmx{gb}G -Xms{gb}G"
    if new_args:
        new_args = f"{memory_args} {new_args}"
    else:
        new_args = memory_args
    config["java_args"] = new_args
    save_config(config)
    print(f"{COLOR_GREEN}Общая память установлена на {gb}GB{COLOR_RESET}")