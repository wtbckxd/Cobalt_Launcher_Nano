import os
import json
import shlex
import subprocess
import threading
import requests
import re
import webbrowser
import xml.etree.ElementTree as ET
import zipfile
import platform
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from constants import MINECRAFT_DIR, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_MAGENTA, COLOR_BLUE, COLOR_RESET, minecraft_processes
from utils import download_file, ProgressCallback, input_yes_no
from config_manager import load_config, save_config
from java_manager import ensure_java_for_version, find_suitable_java, get_java_version, get_required_java_version
from accounts import load_accounts, get_account_by_id

VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
_version_cache = None

def get_installed_versions():
    versions_dir = os.path.join(MINECRAFT_DIR, "versions")
    if not os.path.exists(versions_dir):
        return []
    installed = []
    for item in os.listdir(versions_dir):
        version_path = os.path.join(versions_dir, item)
        if os.path.isdir(version_path):
            json_file = os.path.join(version_path, f"{item}.json")
            jar_file = os.path.join(version_path, f"{item}.jar")
            if os.path.exists(json_file) and os.path.exists(jar_file):
                installed.append(item)
    return sorted(installed, reverse=True)

def get_version_manifest():
    global _version_cache
    if _version_cache is not None:
        return _version_cache
    try:
        resp = requests.get(VERSION_MANIFEST_URL, timeout=10)
        resp.raise_for_status()
        _version_cache = resp.json()
        return _version_cache
    except Exception as e:
        print(f"{COLOR_RED}Ошибка получения манифеста версий: {e}{COLOR_RESET}")
        return None

def get_available_versions():
    manifest = get_version_manifest()
    if not manifest:
        return []
    versions = []
    for v in manifest.get('versions', []):
        versions.append({
            'id': v['id'],
            'type': v['type']
        })
    return versions

def get_version_json(version_id, minecraft_dir):
    version_json_path = os.path.join(minecraft_dir, 'versions', version_id, f'{version_id}.json')
    if os.path.exists(version_json_path):
        with open(version_json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    manifest = get_version_manifest()
    if not manifest:
        return None
    for v in manifest['versions']:
        if v['id'] == version_id:
            url = v['url']
            try:
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                print(f"{COLOR_RED}Ошибка скачивания version.json: {e}{COLOR_RESET}")
                return None
    print(f"{COLOR_RED}Версия {version_id} не найдена в манифесте{COLOR_RESET}")
    return None

def extract_natives(minecraft_dir, version_json):
    natives_dir = os.path.join(minecraft_dir, 'versions', version_json['id'], 'natives')
    os.makedirs(natives_dir, exist_ok=True)
    system = platform.system().lower()
    if system == 'windows':
        classifier = 'natives-windows'
    elif system == 'linux':
        classifier = 'natives-linux'
    elif system == 'darwin':
        classifier = 'natives-osx'
    else:
        classifier = None
    if not classifier:
        return
    libraries = version_json.get('libraries', [])
    for lib in libraries:
        classifiers = lib.get('downloads', {}).get('classifiers', {})
        if classifier in classifiers:
            nat_info = classifiers[classifier]
            lib_path = os.path.join(minecraft_dir, 'libraries', nat_info['path'])
            if os.path.exists(lib_path):
                try:
                    with zipfile.ZipFile(lib_path, 'r') as jar:
                        jar.extractall(natives_dir)
                except Exception as e:
                    print(f"{COLOR_YELLOW}Не удалось распаковать natives из {lib_path}: {e}{COLOR_RESET}")

def download_assets(version_json, minecraft_dir):
    asset_index = version_json.get('assetIndex', {})
    if not asset_index or 'url' not in asset_index:
        return
    assets_index_dir = os.path.join(minecraft_dir, 'assets', 'indexes')
    os.makedirs(assets_index_dir, exist_ok=True)
    index_id = asset_index['id']
    index_path = os.path.join(assets_index_dir, f'{index_id}.json')
    if not os.path.exists(index_path):
        print(f"{COLOR_YELLOW}Скачивание индекса ассетов {index_id}...{COLOR_RESET}")
        if not download_file(asset_index['url'], index_path, None):
            print(f"{COLOR_RED}Не удалось скачать индекс ассетов{COLOR_RESET}")
            return
    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)
    objects = index_data.get('objects', {})
    total = len(objects)
    print(f"{COLOR_YELLOW}Скачивание ассетов (всего {total} файлов)...{COLOR_RESET}")
    for idx, (hash_path, info) in enumerate(objects.items(), 1):
        hash_val = info['hash']
        sub_folder = hash_val[:2]
        dest_dir = os.path.join(minecraft_dir, 'assets', 'objects', sub_folder)
        os.makedirs(dest_dir, exist_ok=True)
        dest_file = os.path.join(dest_dir, hash_val)
        if not os.path.exists(dest_file):
            url = f"https://resources.download.minecraft.net/{sub_folder}/{hash_val}"
            download_file(url, dest_file, None)
        if idx % 100 == 0 or idx == total:
            print(f"\r{COLOR_CYAN}Прогресс: {idx}/{total} ассетов{COLOR_RESET}", end="")
    print()

def install_minecraft_version(version_id, minecraft_dir, callback=None):
    print(f"{COLOR_CYAN}Установка ванильной версии {version_id}...{COLOR_RESET}")
    version_json = get_version_json(version_id, minecraft_dir)
    if not version_json:
        return False
    version_dir = os.path.join(minecraft_dir, 'versions', version_id)
    os.makedirs(version_dir, exist_ok=True)
    json_path = os.path.join(version_dir, f'{version_id}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(version_json, f, indent=2)
    downloads = version_json.get('downloads', {})
    client_info = downloads.get('client')
    if client_info:
        client_url = client_info['url']
        client_path = os.path.join(version_dir, f'{version_id}.jar')
        print(f"{COLOR_YELLOW}Скачивание клиента...{COLOR_RESET}")
        if not download_file(client_url, client_path, callback):
            return False
    libraries = version_json.get('libraries', [])
    total = len(libraries)
    for idx, lib in enumerate(libraries):
        if callback:
            callback({'current': idx + 1, 'total': total})
        downloads_lib = lib.get('downloads', {})
        artifact = downloads_lib.get('artifact')
        if artifact and 'url' in artifact:
            url = artifact['url']
            path = artifact['path']
            dest = os.path.join(minecraft_dir, 'libraries', path)
            if not os.path.exists(dest):
                download_file(url, dest, None)
        classifiers = downloads_lib.get('classifiers')
        if classifiers:
            for classifier_name, nat_info in classifiers.items():
                url = nat_info['url']
                path = nat_info['path']
                dest = os.path.join(minecraft_dir, 'libraries', path)
                if not os.path.exists(dest):
                    download_file(url, dest, None)
    download_assets(version_json, minecraft_dir)
    extract_natives(minecraft_dir, version_json)
    if callback:
        callback({'current': total, 'total': total})
    print(f"{COLOR_GREEN}Ванильная версия {version_id} установлена.{COLOR_RESET}")
    return True

def get_forge_versions(minecraft_version):
    versions = []
    try:
        resp = requests.get("https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        promos = data.get('promos', {})
        for key, value in promos.items():
            if key.startswith(f"{minecraft_version}-"):
                versions.append(value)
    except:
        pass
    if not versions:
        try:
            maven_url = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
            resp = requests.get(maven_url, timeout=10)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            for versioning in root.findall('.//versioning/versions/version'):
                ver_text = versioning.text
                if ver_text and ver_text.startswith(minecraft_version):
                    versions.append(ver_text)
        except:
            pass
    return sorted(set(versions), reverse=True)

def install_forge_version(minecraft_version, forge_ver, minecraft_dir, callback=None):
    possible_urls = [
        f"https://maven.minecraftforge.net/net/minecraftforge/forge/{forge_ver}/forge-{forge_ver}-installer.jar",
        f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{forge_ver}/forge-{forge_ver}-installer.jar"
    ]
    installer_url = None
    for url in possible_urls:
        try:
            head_resp = requests.head(url, timeout=5)
            if head_resp.status_code == 200:
                installer_url = url
                break
        except:
            continue
    if not installer_url:
        print(f"{COLOR_RED}Не удалось найти установщик Forge {forge_ver}{COLOR_RESET}")
        return None
    installer_path = os.path.join(minecraft_dir, f"forge-installer-{forge_ver}.jar")
    print(f"{COLOR_YELLOW}Скачивание установщика Forge...{COLOR_RESET}")
    if not download_file(installer_url, installer_path, callback):
        return None
    java_path = ensure_java_for_version(minecraft_version)
    if not java_path:
        java_path = find_suitable_java(minecraft_version) or 'java'
    version_name = f"{minecraft_version}-forge-{forge_ver}"
    cmd = [
        java_path, '-jar', installer_path,
        '--installClient',
        f'--version={version_name}',
        f'--target={minecraft_dir}'
    ]
    print(f"{COLOR_CYAN}Запуск установщика Forge для создания версии {version_name}...{COLOR_RESET}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(installer_path)
    if result.returncode != 0:
        print(f"{COLOR_RED}Ошибка установки Forge: {result.stderr}{COLOR_RESET}")
        return None
    print(f"{COLOR_GREEN}Forge {forge_ver} установлен как версия {version_name}{COLOR_RESET}")
    return version_name

def install_forge(minecraft_version, minecraft_dir, callback=None):
    print(f"{COLOR_CYAN}Установка Forge для {minecraft_version} как отдельной версии...{COLOR_RESET}")
    forge_versions = get_forge_versions(minecraft_version)
    if not forge_versions:
        print(f"{COLOR_RED}Не найдено версий Forge для {minecraft_version}{COLOR_RESET}")
        print(f"{COLOR_YELLOW}Пожалуйста, установите Forge вручную с сайта https://files.minecraftforge.net/{COLOR_RESET}")
        if input_yes_no("Открыть страницу Forge в браузере? (да/нет): "):
            webbrowser.open("https://files.minecraftforge.net/")
        return None
    if len(forge_versions) == 1:
        selected = forge_versions[0]
        print(f"{COLOR_GREEN}Найдена версия Forge: {selected}{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}Доступные версии Forge для {minecraft_version}:{COLOR_RESET}")
        for i, fv in enumerate(forge_versions[:15], 1):
            print(f"  {COLOR_YELLOW}{i}.{COLOR_RESET} {fv}")
        choice = input(f"{COLOR_YELLOW}Выберите номер версии (или 'в' для отмены): {COLOR_RESET}").strip()
        if choice.lower() == 'в':
            return None
        if not choice.isdigit():
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")
            return None
        idx = int(choice) - 1
        if idx < 0 or idx >= len(forge_versions):
            print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
            return None
        selected = forge_versions[idx]
    return install_forge_version(minecraft_version, selected, minecraft_dir, callback)

def get_fabric_versions(minecraft_version):
    try:
        url = f"https://meta.fabricmc.net/v2/versions/loader/{minecraft_version}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            loaders = resp.json()
            return [f"{l['loader']['version']}" for l in loaders]
    except:
        pass
    return []

def install_fabric_version(minecraft_version, loader_ver, minecraft_dir, callback=None):
    try:
        installer_meta_url = "https://meta.fabricmc.net/v2/versions/installer"
        resp = requests.get(installer_meta_url, timeout=10)
        resp.raise_for_status()
        installers = resp.json()
        if not installers:
            return None
        latest_installer = installers[0]
        installer_version = latest_installer['version']
        installer_url = f"https://maven.fabricmc.net/net/fabricmc/fabric-installer/{installer_version}/fabric-installer-{installer_version}.jar"
        installer_path = os.path.join(minecraft_dir, f"fabric-installer-{installer_version}.jar")
        if not download_file(installer_url, installer_path, callback):
            return None
        java_path = ensure_java_for_version(minecraft_version)
        if not java_path:
            java_path = find_suitable_java(minecraft_version) or 'java'
        version_name = f"fabric-loader-{loader_ver}-{minecraft_version}"
        cmd = [
            java_path, '-jar', installer_path,
            'client',
            '-dir', minecraft_dir,
            '-mcversion', minecraft_version,
            '-loader', loader_ver,
            '-launcher', 'custom', 
            '-version', version_name
        ]
        print(f"{COLOR_CYAN}Запуск установщика Fabric для создания версии {version_name}...{COLOR_RESET}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(installer_path)
        if result.returncode != 0:
            print(f"{COLOR_RED}Ошибка установки Fabric: {result.stderr}{COLOR_RESET}")
            return None
        print(f"{COLOR_GREEN}Fabric {loader_ver} установлен как версия {version_name}{COLOR_RESET}")
        return version_name
    except Exception as e:
        print(f"{COLOR_RED}Ошибка установки Fabric: {e}{COLOR_RESET}")
        return None

def install_fabric(minecraft_version, minecraft_dir, callback=None):
    print(f"{COLOR_CYAN}Установка Fabric для {minecraft_version} как отдельной версии...{COLOR_RESET}")
    fabric_versions = get_fabric_versions(minecraft_version)
    if not fabric_versions:
        print(f"{COLOR_RED}Не найдено версий Fabric для {minecraft_version}{COLOR_RESET}")
        print(f"{COLOR_YELLOW}Попробуйте установить Fabric вручную с сайта https://fabricmc.net/use/installer/{COLOR_RESET}")
        if input_yes_no("Открыть страницу установки Fabric в браузере? (да/нет): "):
            webbrowser.open("https://fabricmc.net/use/installer/")
        return None
    if len(fabric_versions) == 1:
        selected = fabric_versions[0]
        print(f"{COLOR_GREEN}Найдена версия Fabric: {selected}{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}Доступные версии Fabric для {minecraft_version}:{COLOR_RESET}")
        for i, fv in enumerate(fabric_versions[:15], 1):
            print(f"  {COLOR_YELLOW}{i}.{COLOR_RESET} {fv}")
        choice = input(f"{COLOR_YELLOW}Выберите номер версии (или 'в' для отмены): {COLOR_RESET}").strip()
        if choice.lower() == 'в':
            return None
        if not choice.isdigit():
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")
            return None
        idx = int(choice) - 1
        if idx < 0 or idx >= len(fabric_versions):
            print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
            return None
        selected = fabric_versions[idx]
    return install_fabric_version(minecraft_version, selected, minecraft_dir, callback)

def get_quilt_versions(minecraft_version):
    try:
        url = f"https://meta.quiltmc.org/v3/versions/loader/{minecraft_version}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            loaders = resp.json()
            return [f"{l['loader']['version']}" for l in loaders]
    except:
        pass
    return []

def install_quilt_version(minecraft_version, loader_ver, minecraft_dir, callback=None):
    try:
        installer_meta_url = "https://meta.quiltmc.org/v3/versions/installer"
        resp = requests.get(installer_meta_url, timeout=10)
        resp.raise_for_status()
        installers = resp.json()
        if not installers:
            return None
        latest_installer = installers[0]
        installer_version = latest_installer['version']
        installer_url = f"https://maven.quiltmc.org/repository/release/org/quiltmc/quilt-installer/{installer_version}/quilt-installer-{installer_version}.jar"
        installer_path = os.path.join(minecraft_dir, f"quilt-installer-{installer_version}.jar")
        if not download_file(installer_url, installer_path, callback):
            return None
        java_path = ensure_java_for_version(minecraft_version)
        if not java_path:
            java_path = find_suitable_java(minecraft_version) or 'java'
        version_name = f"quilt-loader-{loader_ver}-{minecraft_version}"
        cmd = [
            java_path, '-jar', installer_path,
            'install', 'client', minecraft_version, minecraft_dir,
            '--install-dir=' + minecraft_dir,
            '--loader-version', loader_ver,
            '--custom-version', version_name
        ]
        print(f"{COLOR_CYAN}Запуск установщика Quilt для создания версии {version_name}...{COLOR_RESET}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        os.remove(installer_path)
        if result.returncode != 0:
            print(f"{COLOR_RED}Ошибка установки Quilt: {result.stderr}{COLOR_RESET}")
            return None
        print(f"{COLOR_GREEN}Quilt {loader_ver} установлен как версия {version_name}{COLOR_RESET}")
        return version_name
    except Exception as e:
        print(f"{COLOR_RED}Ошибка установки Quilt: {e}{COLOR_RESET}")
        return None

def install_quilt(minecraft_version, minecraft_dir, callback=None):
    print(f"{COLOR_CYAN}Установка Quilt для {minecraft_version} как отдельной версии...{COLOR_RESET}")
    quilt_versions = get_quilt_versions(minecraft_version)
    if not quilt_versions:
        print(f"{COLOR_RED}Не найдено версий Quilt для {minecraft_version}{COLOR_RESET}")
        print(f"{COLOR_YELLOW}Попробуйте установить Quilt вручную с сайта https://quiltmc.org/en/install/{COLOR_RESET}")
        if input_yes_no("Открыть страницу установки Quilt в браузере? (да/нет): "):
            webbrowser.open("https://quiltmc.org/en/install/")
        return None
    if len(quilt_versions) == 1:
        selected = quilt_versions[0]
        print(f"{COLOR_GREEN}Найдена версия Quilt: {selected}{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}Доступные версии Quilt для {minecraft_version}:{COLOR_RESET}")
        for i, qv in enumerate(quilt_versions[:15], 1):
            print(f"  {COLOR_YELLOW}{i}.{COLOR_RESET} {qv}")
        choice = input(f"{COLOR_YELLOW}Выберите номер версии (или 'в' для отмены): {COLOR_RESET}").strip()
        if choice.lower() == 'в':
            return None
        if not choice.isdigit():
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")
            return None
        idx = int(choice) - 1
        if idx < 0 or idx >= len(quilt_versions):
            print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
            return None
        selected = quilt_versions[idx]
    return install_quilt_version(minecraft_version, selected, minecraft_dir, callback)

def get_neoforge_versions(minecraft_version):
    try:
        api_url = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        versions = data.get('versions', [])
        return [v for v in versions if v.startswith(minecraft_version) or f"mc{minecraft_version}" in v]
    except:
        return []

def install_neoforge_version(minecraft_version, neoforge_ver, minecraft_dir, callback=None):
    installer_url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{neoforge_ver}/neoforge-{neoforge_ver}-installer.jar"
    installer_path = os.path.join(minecraft_dir, f"neoforge-installer-{neoforge_ver}.jar")
    if not download_file(installer_url, installer_path, callback):
        return None
    java_path = ensure_java_for_version(minecraft_version)
    if not java_path:
        java_path = find_suitable_java(minecraft_version) or 'java'
    version_name = f"{minecraft_version}-neoforge-{neoforge_ver}"
    cmd = [
        java_path, '-jar', installer_path,
        '--installClient',
        f'--version={version_name}',
        f'--target={minecraft_dir}'
    ]
    print(f"{COLOR_CYAN}Запуск установщика NeoForge для создания версии {version_name}...{COLOR_RESET}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    os.remove(installer_path)
    if result.returncode != 0:
        print(f"{COLOR_RED}Ошибка установки NeoForge: {result.stderr}{COLOR_RESET}")
        return None
    print(f"{COLOR_GREEN}NeoForge {neoforge_ver} установлен как версия {version_name}{COLOR_RESET}")
    return version_name

def install_neoforge(minecraft_version, minecraft_dir, callback=None):
    print(f"{COLOR_CYAN}Установка NeoForge для {minecraft_version} как отдельной версии...{COLOR_RESET}")
    neoforge_versions = get_neoforge_versions(minecraft_version)
    if not neoforge_versions:
        print(f"{COLOR_RED}Не найдено версий NeoForge для {minecraft_version}{COLOR_RESET}")
        return None
    if len(neoforge_versions) == 1:
        selected = neoforge_versions[0]
        print(f"{COLOR_GREEN}Найдена версия NeoForge: {selected}{COLOR_RESET}")
    else:
        print(f"{COLOR_GREEN}Доступные версии NeoForge для {minecraft_version}:{COLOR_RESET}")
        for i, nv in enumerate(neoforge_versions[:15], 1):
            print(f"  {COLOR_YELLOW}{i}.{COLOR_RESET} {nv}")
        choice = input(f"{COLOR_YELLOW}Выберите номер версии (или 'в' для отмены): {COLOR_RESET}").strip()
        if choice.lower() == 'в':
            return None
        if not choice.isdigit():
            print(f"{COLOR_RED}Неверный ввод{COLOR_RESET}")
            return None
        idx = int(choice) - 1
        if idx < 0 or idx >= len(neoforge_versions):
            print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
            return None
        selected = neoforge_versions[idx]
    return install_neoforge_version(minecraft_version, selected, minecraft_dir, callback)

def install_loader(version, loader_choice, minecraft_dir):
    if loader_choice == '1':
        return install_forge(version, minecraft_dir)
    elif loader_choice == '2':
        return install_fabric(version, minecraft_dir)
    elif loader_choice == '3':
        return install_quilt(version, minecraft_dir)
    elif loader_choice == '4':
        return install_neoforge(version, minecraft_dir)
    else:
        print(f"{COLOR_RED}Неизвестный тип модлоадера{COLOR_RESET}")
        return None

def get_minecraft_dir_for_version(version):
    config = load_config()
    if config.get("separate_version_dirs", False):
        return str(Path.home() / f".minecraft_{version}")
    return MINECRAFT_DIR

def install_version_with_progress(version, loader_choice=None):
    minecraft_dir = get_minecraft_dir_for_version(version)
    ensure_java_for_version(version)
    progress = ProgressCallback()
    success = install_minecraft_version(version, minecraft_dir, progress)
    if not success:
        return
    loader_version_name = None
    if loader_choice:
        loader_version_name = install_loader(version, loader_choice, minecraft_dir)
    config = load_config()
    # Если установлен модлоадер, выбираем его версию, иначе ванильную
    if loader_version_name:
        config["selected_version"] = loader_version_name
        print(f"{COLOR_GREEN}✓ Версия {loader_version_name} с модлоадером успешно установлена!{COLOR_RESET}")
    else:
        config["selected_version"] = version
        print(f"{COLOR_GREEN}✓ Версия {version} успешно установлена!{COLOR_RESET}")
    save_config(config)

def install_version_interactive(version=None):
    if not version:
        version = input(f"{COLOR_YELLOW}Введите версию Minecraft: {COLOR_RESET}").strip()
        if not version:
            print(f"{COLOR_RED}Версия не указана{COLOR_RESET}")
            return
    if input_yes_no("Установить с модлоадером? (да/нет): "):
        print(f"{COLOR_GREEN}Выберите модлоадер:{COLOR_RESET}")
        print(f"{COLOR_YELLOW}1.{COLOR_RESET} Forge")
        print(f"{COLOR_YELLOW}2.{COLOR_RESET} Fabric")
        print(f"{COLOR_YELLOW}3.{COLOR_RESET} Quilt")
        print(f"{COLOR_YELLOW}4.{COLOR_RESET} NeoForge")
        loader_choice = input(f"{COLOR_YELLOW}Ваш выбор (1-4): {COLOR_RESET}").strip()
        if loader_choice not in ['1', '2', '3', '4']:
            print(f"{COLOR_RED}Неверный выбор, установка без модлоадера{COLOR_RESET}")
            loader_choice = None
    else:
        loader_choice = None
    install_version_with_progress(version, loader_choice)

def build_classpath(minecraft_dir, version_json):
    classpath = []
    version_id = version_json['id']
    client_jar = os.path.join(minecraft_dir, 'versions', version_id, f'{version_id}.jar')
    if os.path.exists(client_jar):
        classpath.append(client_jar)
    libraries = version_json.get('libraries', [])
    for lib in libraries:
        artifact = lib.get('downloads', {}).get('artifact')
        if artifact and 'path' in artifact:
            lib_path = os.path.join(minecraft_dir, 'libraries', artifact['path'])
            if os.path.exists(lib_path):
                classpath.append(lib_path)
    return os.pathsep.join(classpath)

def get_minecraft_command(version, minecraft_dir, options):
    version_json_path = os.path.join(minecraft_dir, 'versions', version, f'{version}.json')
    if not os.path.exists(version_json_path):
        raise Exception(f"Version {version} not installed")
    with open(version_json_path, 'r', encoding='utf-8') as f:
        version_json = json.load(f)

    main_class = version_json.get('mainClass', 'net.minecraft.client.main.Main')

    game_args = []
    arguments = version_json.get('arguments')
    if arguments and 'game' in arguments:
        for arg in arguments['game']:
            if isinstance(arg, str):
                game_args.append(arg)
    else:
        mc_args_str = version_json.get('minecraftArguments', '')
        if mc_args_str:
            try:
                game_args = shlex.split(mc_args_str)
            except ValueError:
                game_args = mc_args_str.split()

    jvm_args = []
    if arguments and 'jvm' in arguments:
        for arg in arguments['jvm']:
            if isinstance(arg, str):
                jvm_args.append(arg)
    else:
        jvm_args = [
            '-Djava.library.path=${natives_directory}',
            '-cp', '${classpath}'
        ]

    natives_dir = os.path.join(minecraft_dir, 'versions', version, 'natives')
    classpath = build_classpath(minecraft_dir, version_json)

    def replace_placeholders(arg):
        arg = arg.replace('${version_name}', version)
        arg = arg.replace('${game_directory}', minecraft_dir)
        arg = arg.replace('${assets_root}', os.path.join(minecraft_dir, 'assets'))
        arg = arg.replace('${assets_index_name}', version_json.get('assetIndex', {}).get('id', version))
        arg = arg.replace('${auth_uuid}', options.get('uuid', '00000000-0000-0000-0000-000000000000'))
        arg = arg.replace('${auth_access_token}', options.get('token', '0'))
        arg = arg.replace('${auth_player_name}', options.get('username', 'Player'))
        arg = arg.replace('${user_type}', 'mojang')
        arg = arg.replace('${version_type}', version_json.get('type', 'release'))
        arg = arg.replace('${natives_directory}', natives_dir)
        arg = arg.replace('${library_directory}', os.path.join(minecraft_dir, 'libraries'))
        arg = arg.replace('${classpath}', classpath)
        arg = arg.replace('${classpath_separator}', os.pathsep)
        return arg

    game_args = [replace_placeholders(arg) for arg in game_args]
    jvm_args = [replace_placeholders(arg) for arg in jvm_args]

    has_cp = any(arg == '-cp' or arg == '--classpath' for arg in jvm_args)
    if not has_cp:
        command = jvm_args + ['-cp', classpath, main_class] + game_args
    else:
        command = jvm_args + [main_class] + game_args
    return command

def launch_minecraft_thread(version, java_path, java_args_str, username, minecraft_dir, account_type, access_token=None):
    try:
        options = {'username': username, 'uuid': '', 'token': ''}
        if account_type == 'ely' and access_token:
            print(f"{COLOR_YELLOW}Авторизация Ely.by: требует доработки.{COLOR_RESET}")
        minecraft_command = get_minecraft_command(version, minecraft_dir, options)
        java_args = shlex.split(java_args_str) if java_args_str else []
        java_executable = java_path if java_path else ('java' if platform.system() != "Linux" else shutil.which("java") or "java")
        full_command = [java_executable] + java_args + minecraft_command
        print(f"{COLOR_CYAN}Команда запуска: {' '.join(full_command)}{COLOR_RESET}")
        proc = subprocess.Popen(
            full_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'
        )
        pid = proc.pid
        prefix = f"{COLOR_MAGENTA}[Minecraft-{pid}]{COLOR_RESET}"
        minecraft_processes.append((pid, proc))
        print(f"{COLOR_GREEN}Minecraft запущен (PID {pid}){COLOR_RESET}")
        print(f"{COLOR_YELLOW}Для завершения используйте Ctrl+C в этом окне (завершит лаунчер и игру) или закройте окно игры{COLOR_RESET}")
        try:
            import keyboard
            KEYBOARD_AVAILABLE = True
        except ImportError:
            KEYBOARD_AVAILABLE = False
        if KEYBOARD_AVAILABLE:
            def monitor_hotkey(proc, pid):
                try:
                    keyboard.wait('alt+shift')
                    if proc.poll() is None:
                        print(f"\n{COLOR_YELLOW}Горячая клавиша Alt+Shift нажата, завершение Minecraft (PID {pid})...{COLOR_RESET}")
                        proc.terminate()
                        proc.wait()
                except:
                    pass
            threading.Thread(target=monitor_hotkey, args=(proc, pid), daemon=True).start()
        for line in iter(proc.stdout.readline, ''):
            if line:
                print(f"{prefix} {line.rstrip()}")
            else:
                break
        proc.wait()
        for i, (p, pr) in enumerate(minecraft_processes):
            if p == pid:
                minecraft_processes.pop(i)
                break
        print(f"{COLOR_GREEN}Minecraft (PID {pid}) завершил работу{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Ошибка запуска в потоке: {e}{COLOR_RESET}")

def launch_minecraft(version=None):
    config = load_config()
    if not version:
        version = config.get("selected_version")
    if not version:
        print(f"{COLOR_RED}Сначала установите версию Minecraft!{COLOR_RESET}")
        return
    accounts = load_accounts()
    current_account_id = config.get("current_account")
    if not current_account_id or not any(a["id"] == current_account_id for a in accounts):
        print(f"{COLOR_RED}Сначала настройте аккаунт!{COLOR_RESET}")
        return
    account = next((a for a in accounts if a["id"] == current_account_id), None)
    if not account:
        print(f"{COLOR_RED}Аккаунт не найден!{COLOR_RESET}")
        return
    username = account["username"]
    minecraft_dir = get_minecraft_dir_for_version(version)
    java_path = None
    if version in config["java_path_by_version"]:
        java_path = config["java_path_by_version"][version]
        print(f"{COLOR_CYAN}Используется Java для версии: {java_path}{COLOR_RESET}")
    elif config.get("java_path"):
        java_path = config["java_path"]
        print(f"{COLOR_CYAN}Используется общий путь Java: {java_path}{COLOR_RESET}")
    else:
        auto_java = find_suitable_java(version)
        if auto_java:
            java_path = auto_java
            print(f"{COLOR_CYAN}Автоматически найдена подходящая Java: {java_path}{COLOR_RESET}")
        else:
            print(f"{COLOR_YELLOW}Не задан путь к Java, будет использована системная{COLOR_RESET}")
    if java_path and os.path.exists(java_path):
        java_version = get_java_version(java_path)
        if java_version:
            print(f"{COLOR_GREEN}Версия Java: {java_version}{COLOR_RESET}")
            required = get_required_java_version(version.split('-')[0])  # извлекаем ванильную версию
            if java_version < required:
                print(f"{COLOR_RED}ВНИМАНИЕ: Для Minecraft {version} требуется Java {required} или выше!{COLOR_RESET}")
                print(f"{COLOR_RED}Текущая Java: {java_version}{COLOR_RESET}")
                print(f"{COLOR_YELLOW}Вы можете установить Java {required} командой: {COLOR_GREEN}установить джава{COLOR_RESET}")
                if not input_yes_no("Продолжить запуск? (да/нет): "):
                    return
        else:
            print(f"{COLOR_YELLOW}Не удалось определить версию Java{COLOR_RESET}")
    if version in config["java_args_by_version"]:
        java_args_str = config["java_args_by_version"][version]
    else:
        java_args_str = config.get("java_args", "-Xmx2G -Xms1G")
    print(f"{COLOR_CYAN}ЗАПУСК MINECRAFT{COLOR_RESET}")
    print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
    print(f"{COLOR_GREEN}Версия:{COLOR_RESET} {version}")
    print(f"{COLOR_GREEN}Аккаунт:{COLOR_RESET} {username}")
    print(f"{COLOR_GREEN}Аргументы JVM:{COLOR_RESET} {java_args_str}")
    memory_match = re.search(r'-Xmx(\d+)G', java_args_str)
    if memory_match:
        print(f"{COLOR_GREEN}Память:{COLOR_RESET} {memory_match.group(1)}GB")
    print(f"{COLOR_GREEN}Папка:{COLOR_RESET} {minecraft_dir}")
    print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
    access_token = account.get("access_token") if account.get("type") == "ely" else None
    thread = threading.Thread(
        target=launch_minecraft_thread,
        args=(version, java_path, java_args_str, username, minecraft_dir, account.get('type'), access_token),
        daemon=True
    )
    thread.start()

def delayed_launch(version, delay_seconds, count):
    try:
        delay = int(delay_seconds)
        cnt = int(count)
    except ValueError:
        print(f"{COLOR_RED}Неверные аргументы. Используйте: отложенный запуск <версия> <секунды> <количество>{COLOR_RESET}")
        return
    print(f"{COLOR_CYAN}Запланирован запуск {cnt} клиентов версии {version} через {delay} секунд{COLOR_RESET}")

    def launch_wrapper():
        for i in range(cnt):
            threading.Timer(i * 2, lambda: launch_minecraft(version)).start()

    threading.Timer(delay, launch_wrapper).start()

def toggle_separate_dirs():
    config = load_config()
    current = config.get("separate_version_dirs", False)
    config["separate_version_dirs"] = not current
    status = "включено" if config["separate_version_dirs"] else "выключено"
    print(f"{COLOR_CYAN}Отдельные папки для версий: {COLOR_GREEN}{status}{COLOR_RESET}")
    if config["separate_version_dirs"]:
        print(f"{COLOR_YELLOW}Теперь каждая версия Minecraft будет установлена в отдельную папку.{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}Все версии Minecraft будут использовать одну папку .minecraft{COLOR_RESET}")
    save_config(config)