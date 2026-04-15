import os
import platform
import subprocess
import re
import shutil
import zipfile
import tarfile
import requests
from constants import JAVA_DIR, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_RESET
from utils import download_with_retry
from config_manager import load_config, save_config

def find_java_executable_in_dir(java_dir):
    for root, dirs, files in os.walk(java_dir):
        if platform.system() == "Windows":
            if "java.exe" in files:
                return os.path.join(root, "java.exe")
        else:
            if "java" in files and os.access(os.path.join(root, "java"), os.X_OK):
                return os.path.join(root, "java")
    for root, dirs, files in os.walk(java_dir):
        if "bin" in dirs:
            bin_path = os.path.join(root, "bin")
            if platform.system() == "Windows":
                java_candidate = os.path.join(bin_path, "java.exe")
                if os.path.exists(java_candidate):
                    return java_candidate
            else:
                java_candidate = os.path.join(bin_path, "java")
                if os.path.exists(java_candidate) and os.access(java_candidate, os.X_OK):
                    return java_candidate
    return None

def get_java_version(java_path):
    try:
        result = subprocess.run([java_path, "-version"], capture_output=True, text=True, shell=True, timeout=5)
        output = result.stderr if result.stderr else result.stdout
        patterns = [r'version["\s]+([0-9._]+)', r'\(build ([0-9._]+)\)', r'java version["\s]+([0-9._]+)']
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                version_str = match.group(1)
                main_version_match = re.search(r'^(\d+)', version_str)
                if main_version_match:
                    return int(main_version_match.group(1))
        return None
    except Exception:
        return None

def get_required_java_version(minecraft_version):
    match = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', minecraft_version)
    if not match:
        return 8
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3)) if match.group(3) else 0
    if major == 1:
        if minor >= 21:
            return 21
        elif minor == 20 and patch >= 5:
            return 21
        elif minor >= 18:
            return 17
        elif minor >= 17:
            return 16
        else:
            return 8
    else:
        return 21

def find_suitable_java(minecraft_version):
    required = get_required_java_version(minecraft_version)
    for ver in [8, 11, 16, 17, 21]:
        if ver >= required:
            java_dir_candidate = os.path.join(JAVA_DIR, f"java_{ver}")
            if os.path.exists(java_dir_candidate):
                exe = find_java_executable_in_dir(java_dir_candidate)
                if exe:
                    return exe
    return None

def set_java_path_for_version(version, path=None):
    config = load_config()
    if path is None:
        if version in config["java_path_by_version"]:
            del config["java_path_by_version"][version]
            print(f"{COLOR_GREEN}Путь Java для версии {version} сброшен{COLOR_RESET}")
    else:
        if os.path.exists(path):
            config["java_path_by_version"][version] = path
            print(f"{COLOR_GREEN}Путь Java для версии {version} установлен: {path}{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Указанный путь не существует{COLOR_RESET}")
            return
    save_config(config)

def get_java_download_url(version, os_name, arch):
    api_url = f"https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
    params = {
        "architecture": arch,
        "image_type": "jdk",
        "os": os_name,
        "vendor": "adoptium"
    }
    try:
        response = requests.get(api_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data and len(data) > 0:
            binary = data[0].get("binary", {})
            package = binary.get("package", {})
            link = package.get("link")
            if link:
                if link.endswith(".zip"):
                    ext = "zip"
                elif link.endswith(".tar.gz"):
                    ext = "tar.gz"
                else:
                    ext = "unknown"
                return link, ext
    except Exception:
        pass
    return None, None

def install_java_version(java_version):
    system = platform.system()
    arch = platform.machine().lower()
    os_map = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}
    os_name = os_map.get(system)
    if not os_name:
        print(f"{COLOR_RED}ОС {system} не поддерживается{COLOR_RESET}")
        return False
    arch_map = {
        "x86_64": "x64", "amd64": "x64", "i386": "x86", "i686": "x86",
        "aarch64": "arm", "armv7l": "arm"
    }
    arch_api = arch_map.get(arch.lower(), arch)
    if arch_api not in ["x64", "x86", "arm", "ppc64le", "s390x"]:
        print(f"{COLOR_RED}Архитектура {arch} не поддерживается{COLOR_RESET}")
        return False
    url, ext = get_java_download_url(java_version, os_name, arch_api)
    if not url:
        print(f"{COLOR_RED}Не удалось получить ссылку для Java {java_version}{COLOR_RESET}")
        return False
    java_install_dir = os.path.join(JAVA_DIR, f"java_{java_version}")
    os.makedirs(java_install_dir, exist_ok=True)
    download_path = os.path.join(java_install_dir, f"java.{ext}")
    print(f"{COLOR_CYAN}Скачивание Java {java_version}...{COLOR_RESET}")
    def progress_callback(current, total):
        if total > 0:
            percent = (current / total) * 100
            bar_length = 30
            filled = int(bar_length * current / total)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r{COLOR_CYAN}[{bar}] {percent:.1f}% ({current/1024/1024:.1f} MB / {total/1024/1024:.1f} MB){COLOR_RESET}", end="")
    if not download_with_retry(url, download_path, progress_callback, max_retries=3):
        print(f"{COLOR_RED}Не удалось скачать Java{COLOR_RESET}")
        return False
    print()
    try:
        if ext == "zip":
            with zipfile.ZipFile(download_path, 'r') as zip_ref:
                zip_ref.extractall(java_install_dir)
        else:
            with tarfile.open(download_path, 'r:gz') as tar_ref:
                tar_ref.extractall(java_install_dir)
        os.remove(download_path)
    except Exception as e:
        print(f"{COLOR_RED}Ошибка распаковки Java: {e}{COLOR_RESET}")
        return False
    java_exe = find_java_executable_in_dir(java_install_dir)
    if not java_exe:
        print(f"{COLOR_RED}Исполняемый файл Java не найден{COLOR_RESET}")
        return False
    config = load_config()
    config["java_path"] = java_exe
    config["java_version"] = java_version
    save_config(config)
    return True

def ensure_java_for_version(minecraft_version):
    required = get_required_java_version(minecraft_version)
    java_exe = find_suitable_java(minecraft_version)
    if java_exe:
        return java_exe
    print(f"{COLOR_YELLOW}Требуется Java {required} для версии {minecraft_version}. Автоматическая установка...{COLOR_RESET}")
    install_java_version(required)
    java_exe = find_suitable_java(minecraft_version)
    if java_exe:
        print(f"{COLOR_GREEN}Java {required} установлена и будет использована.{COLOR_RESET}")
        return java_exe
    else:
        print(f"{COLOR_RED}Не удалось установить Java {required}. Пожалуйста, установите вручную.{COLOR_RESET}")
        return None

def set_java_path():
    config = load_config()
    current_path = config.get("java_path", "Не установлен")
    print(f"\n{COLOR_CYAN}Текущий общий путь к Java: {current_path}{COLOR_RESET}")
    print(f"{COLOR_YELLOW}Примеры:{COLOR_RESET}")
    print(f"{COLOR_GREEN}  C:\\Program Files\\Java\\jdk-17\\bin\\java.exe{COLOR_RESET} - Windows")
    print(f"{COLOR_GREEN}  /usr/lib/jvm/java-17-openjdk/bin/java{COLOR_RESET} - Linux")
    new_path = input(f"\n{COLOR_YELLOW}Введите новый путь к Java (Enter для сброса): {COLOR_RESET}")
    if new_path:
        if os.path.exists(new_path):
            config["java_path"] = new_path
            save_config(config)
            print(f"{COLOR_GREEN}Путь к Java обновлен!{COLOR_RESET}")
            java_version = get_java_version(new_path)
            if java_version:
                print(f"{COLOR_GREEN}Версия Java: {java_version}{COLOR_RESET}")
                config["java_version"] = str(java_version)
                save_config(config)
            else:
                print(f"{COLOR_YELLOW}Не удалось определить версию Java{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Указанный путь не существует!{COLOR_RESET}")
    elif new_path == "" and current_path != "Не установлен":
        config["java_path"] = None
        config["java_version"] = "17"
        save_config(config)
        print(f"{COLOR_GREEN}Общий путь к Java сброшен, будет использована системная Java.{COLOR_RESET}")

def install_java_interactive():
    print(f"{COLOR_CYAN}Автоматическая установка Java...{COLOR_RESET}")
    system = platform.system()
    arch = platform.machine().lower()
    os_map = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}
    os_name = os_map.get(system)
    if not os_name:
        print(f"{COLOR_RED}ОС {system} не поддерживается{COLOR_RESET}")
        return
    arch_map = {
        "x86_64": "x64", "amd64": "x64", "i386": "x86", "i686": "x86",
        "aarch64": "arm", "armv7l": "arm"
    }
    arch_api = arch_map.get(arch.lower(), arch)
    if arch_api not in ["x64", "x86", "arm", "ppc64le", "s390x"]:
        print(f"{COLOR_RED}Архитектура {arch} не поддерживается{COLOR_RESET}")
        return
    java_versions = {
        "1": {"name": "Java 8", "version": "8"},
        "2": {"name": "Java 11", "version": "11"},
        "3": {"name": "Java 17", "version": "17"},
        "4": {"name": "Java 21", "version": "21"}
    }
    print(f"{COLOR_YELLOW}Выберите версию Java для установки:{COLOR_RESET}")
    print(f"{COLOR_RED}ВНИМАНИЕ: Для Minecraft 1.17+ требуется Java 17 или выше!{COLOR_RESET}")
    for key, value in java_versions.items():
        print(f"{COLOR_CYAN}{key}.{COLOR_RESET} {value['name']}")
    choice = input(f"{COLOR_YELLOW}Ваш выбор (1-4, рекомендуется 3 для Java 17): {COLOR_RESET}")
    if choice not in java_versions:
        print(f"{COLOR_RED}Неверный выбор{COLOR_RESET}")
        return
    java_version = java_versions[choice]["version"]
    install_java_version(java_version)