import os
import sys
import time
import itertools
import threading
import requests
from datetime import datetime
from typing import List, Dict, Optional
from constants import COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_BLUE, COLOR_RESET

def input_yes_no(prompt):
    while True:
        response = input(prompt).lower()
        if response in ['да', 'д']:
            return True
        elif response in ['нет', 'н']:
            return False
        else:
            print(f"{COLOR_RED}Пожалуйста, ответьте 'да' или 'нет'{COLOR_RESET}")

class ScrollableList:
    def __init__(self, items, page_size=10):
        self.items = items
        self.page_size = page_size
        self.current_page = 0

    def display_page(self):
        start_idx = self.current_page * self.page_size
        end_idx = start_idx + self.page_size
        page_items = self.items[start_idx:end_idx]
        total_pages = (len(self.items) + self.page_size - 1) // self.page_size if self.items else 1
        print(f"{COLOR_CYAN}Страница {self.current_page + 1}/{total_pages}{COLOR_RESET}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")
        if not page_items:
            print(f"{COLOR_YELLOW}Нет элементов для отображения{COLOR_RESET}")
        else:
            for i, item in enumerate(page_items, start=1):
                print(f"{COLOR_YELLOW}{start_idx + i:3}.{COLOR_RESET} {item}")
        print(f"{COLOR_BLUE}──────────────────────────────────{COLOR_RESET}")

    def navigate(self):
        if not self.items:
            print(f"{COLOR_YELLOW}Список пуст{COLOR_RESET}")
            return None
        while True:
            self.display_page()
            print(f"\n{COLOR_GREEN}Команды:{COLOR_RESET}")
            print(f"{COLOR_CYAN}с{COLOR_RESET} - следующая страница")
            print(f"{COLOR_CYAN}п{COLOR_RESET} - предыдущая страница")
            print(f"{COLOR_CYAN}число{COLOR_RESET} - выбрать элемент")
            print(f"{COLOR_CYAN}в{COLOR_RESET} - выйти")
            choice = input(f"{COLOR_YELLOW}Выберите: {COLOR_RESET}").lower()
            if choice == 'с':
                if (self.current_page + 1) * self.page_size < len(self.items):
                    self.current_page += 1
                else:
                    print(f"{COLOR_RED}Это последняя страница{COLOR_RESET}")
            elif choice == 'п':
                if self.current_page > 0:
                    self.current_page -= 1
                else:
                    print(f"{COLOR_RED}Это первая страница{COLOR_RESET}")
            elif choice == 'в':
                return None
            elif choice.isdigit():
                idx = int(choice) - 1
                actual_idx = self.current_page * self.page_size + idx
                if 0 <= actual_idx < len(self.items):
                    return actual_idx
                else:
                    print(f"{COLOR_RED}Неверный номер{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Неверная команда{COLOR_RESET}")

def download_with_retry(url, filepath, callback=None, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if callback and total_size > 0:
                            callback(downloaded, total_size)
            return True
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            print(f"\n{COLOR_YELLOW}Попытка {attempt} не удалась: {e}{COLOR_RESET}")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"{COLOR_CYAN}Повтор через {wait} секунд...{COLOR_RESET}")
                time.sleep(wait)
            else:
                print(f"{COLOR_RED}Не удалось скачать файл после {max_retries} попыток{COLOR_RESET}")
                return False
    return False

class Spinner:
    def __init__(self, message="Загрузка"):
        self.spinner = itertools.cycle(['-', '\\', '|', '/'])
        self.running = False
        self.thread = None
        self.message = message

    def spin(self):
        while self.running:
            print(f"\r{COLOR_CYAN}{self.message} {next(self.spinner)}{COLOR_RESET}", end="", flush=True)
            time.sleep(0.1)

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        print("\r" + " " * (len(self.message) + 10), end="\r", flush=True)

class ProgressCallback:
    def __init__(self, prefix=""):
        self.prefix = prefix
        self.current = 0
        self.total = 0

    def __call__(self, *args):
        if len(args) == 1 and isinstance(args[0], dict):
            data = args[0]
            self.current = data.get('current', 0)
            self.total = data.get('total', 0)
        elif len(args) == 2:
            self.current, self.total = args
        else:
            return

        if self.total > 0:
            percent = (self.current / self.total) * 100
            bar_length = 30
            filled = int(bar_length * self.current / self.total)
            bar = '█' * filled + '░' * (bar_length - filled)
            print(f"\r{COLOR_CYAN}{self.prefix}[{bar}] {percent:.1f}% ({self.current}/{self.total} файлов){COLOR_RESET}",
                  end="")
            if self.current >= self.total:
                print()

    def get(self, key, default=None):
        if key == 'current':
            return self.current
        elif key == 'total':
            return self.total
        return default

def download_file(url, dest, callback=None):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    success = download_with_retry(url, dest, callback, max_retries=3)
    return success