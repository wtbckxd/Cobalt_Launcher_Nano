import os
import platform
from pathlib import Path
from colored import fg, attr

COLOR_RED = fg('red')
COLOR_GREEN = fg('green')
COLOR_YELLOW = fg('yellow')
COLOR_BLUE = fg('blue')
COLOR_MAGENTA = fg('magenta')
COLOR_CYAN = fg('cyan')
COLOR_RESET = attr('reset')

LAUNCHER_DATA_DIR = "C:\\cobalt_launcher"

CONFIG_FILE = os.path.join(LAUNCHER_DATA_DIR, "config.json")
NOTES_FILE = os.path.join(LAUNCHER_DATA_DIR, "notes.txt")
JAVA_DIR = os.path.join(LAUNCHER_DATA_DIR, "java")
MINECRAFT_DIR = os.path.join(LAUNCHER_DATA_DIR, "minecraft")
ACCOUNTS_FILE = os.path.join(MINECRAFT_DIR, "launcher_profiles.json")
MODS_FAVORITES_FILE = os.path.join(LAUNCHER_DATA_DIR, "mods_favorites.json")
PLUGINS_DIR = os.path.join(LAUNCHER_DATA_DIR, "plugins")

PLUGINS_INDEX_URL = "https://raw.githubusercontent.com/m1r0tv0rets/Cobalt_Launcher_Nano/main/plugins.json"

os.makedirs(LAUNCHER_DATA_DIR, exist_ok=True)
os.makedirs(JAVA_DIR, exist_ok=True)
os.makedirs(MINECRAFT_DIR, exist_ok=True)
os.makedirs(PLUGINS_DIR, exist_ok=True)

plugin_commands = {}
plugin_hooks = {'banner': [], 'info': []}
minecraft_processes = []
hotkey_thread_running = False