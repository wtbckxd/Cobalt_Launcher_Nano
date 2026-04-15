import os
from constants import COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_MAGENTA, COLOR_CYAN, COLOR_RESET, NOTES_FILE, MINECRAFT_DIR, plugin_hooks, plugin_commands
from config_manager import load_config
from accounts import load_accounts
from version_manager import get_installed_versions

def print_banner():
    banner = f"""
{COLOR_CYAN}Cobalt Launcher Nano:{COLOR_RESET}
{COLOR_CYAN}Версия: {COLOR_RED}1.0 Релиз{COLOR_RESET}
{COLOR_CYAN}Создатель: {COLOR_GREEN}M1rotvorets{COLOR_RESET}
{COLOR_CYAN}Разработчики:: {COLOR_YELLOW}WaterBucket, Nos0kkk{COLOR_RESET}
{COLOR_CYAN}Репозиторий: {COLOR_BLUE}https://github.com/m1r0tv0rets/Cobalt_Launcher_Nano{COLOR_RESET}
    """
    for hook in plugin_hooks['banner']:
        try:
            banner = hook(banner) or banner
        except Exception as e:
            print(f"{COLOR_RED}Ошибка в хуке баннера: {e}{COLOR_RESET}")
    print(banner)

def show_quick_info():
    print(f"{COLOR_CYAN}════════════════════════════════════════════════════════════{COLOR_RESET}")
    installed = get_installed_versions()
    if installed:
        print(f"{COLOR_GREEN}Установленные версии Minecraft:{COLOR_RESET}")
        for i, ver in enumerate(installed[:10], 1):
            print(f"  {COLOR_YELLOW}{i}.{COLOR_RESET} {ver}")
        if len(installed) > 10:
            print(f"  {COLOR_YELLOW}... и ещё {len(installed)-10} версий{COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}Установленные версии: нет (используйте 'установить <версия>'){COLOR_RESET}")
    accounts = load_accounts()
    if accounts:
        config = load_config()
        current_id = config.get("current_account")
        print(f"{COLOR_GREEN}Аккаунты:{COLOR_RESET}")
        for acc in accounts:
            marker = "✓" if current_id == acc["id"] else " "
            print(f"  [{marker}] {acc['username']} ({acc['type']})")
    else:
        print(f"{COLOR_YELLOW}Аккаунты: не добавлены (используйте 'акк'){COLOR_RESET}")
    if os.path.exists(NOTES_FILE):
        with open(NOTES_FILE, 'r', encoding='utf-8') as f:
            notes = f.readlines()
        if notes:
            print(f"{COLOR_GREEN}Последние заметки:{COLOR_RESET}")
            for note in notes[-3:]:
                print(f"  {COLOR_CYAN}•{COLOR_RESET} {note.strip()}")
        else:
            print(f"{COLOR_YELLOW}Заметок пока нет (используйте 'заметка <текст>'){COLOR_RESET}")
    else:
        print(f"{COLOR_YELLOW}Заметок пока нет (используйте 'заметка <текст>'){COLOR_RESET}")
    print(f"{COLOR_CYAN}════════════════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_MAGENTA}Не знаете команды? Введите '{COLOR_GREEN}помощь{COLOR_MAGENTA}' для списка команд{COLOR_RESET}")

def print_help():
    help_text = f"""
{COLOR_CYAN}=== ОСНОВНЫЕ КОМАНДЫ ==={COLOR_RESET}
{COLOR_GREEN}помощь{COLOR_RESET}               - Показать эту справку
{COLOR_GREEN}установленные{COLOR_RESET}       - Показать установленные версии Minecraft
{COLOR_GREEN}акк{COLOR_RESET}                 - Управление аккаунтами
{COLOR_GREEN}альфа, бета, снапшоты, релизы{COLOR_RESET} - Показать версии определённого типа
{COLOR_GREEN}установить <версия> [модлоадер]{COLOR_RESET} - Установить версию (forge, fabric, quilt, neoforge)
{COLOR_GREEN}запуск [версия]{COLOR_RESET}      - Запустить Minecraft
{COLOR_GREEN}отложенный запуск <версия> <сек> <кол-во>{COLOR_RESET} - Запустить несколько клиентов с задержкой

{COLOR_CYAN}=== НАСТРОЙКА JAVA ==={COLOR_RESET}
{COLOR_GREEN}арг{COLOR_RESET}                 - Настройка общих аргументов Java
{COLOR_GREEN}арг версии <версия> <аргументы>{COLOR_RESET} - Аргументы Java для конкретной версии
{COLOR_GREEN}джава версии <версия> [путь]{COLOR_RESET} - Установить/сбросить путь Java для версии
{COLOR_GREEN}память <ГБ>{COLOR_RESET}         - Установить общий объем памяти (-Xmx, -Xms)
{COLOR_GREEN}джава{COLOR_RESET}              - Установить общий путь к Java
{COLOR_GREEN}установить джава{COLOR_RESET}    - Скачать и установить Java автоматически
{COLOR_GREEN}отдельные папки{COLOR_RESET}    - Включить/выключить отдельные папки для версий

{COLOR_CYAN}=== МОДЫ И ОПТИМИЗАЦИЯ ==={COLOR_RESET}
{COLOR_GREEN}моды{COLOR_RESET}               - Поиск и управление модами (Modrinth)
{COLOR_GREEN}optifine{COLOR_RESET}           - Открыть страницу скачивания OptiFine
{COLOR_GREEN}sodium{COLOR_RESET}             - Установить Sodium (Fabric)
{COLOR_GREEN}embeddium{COLOR_RESET}          - Установить Embeddium (Forge)
{COLOR_GREEN}modmenu{COLOR_RESET}            - Установить Mod Menu (Fabric/Quilt)
{COLOR_GREEN}journeymap{COLOR_RESET}         - Установить JourneyMap
{COLOR_GREEN}xaeros{COLOR_RESET}             - Установить Xaero's Minimap
{COLOR_GREEN}vulkanmod{COLOR_RESET}          - Установить VulkanMod
{COLOR_GREEN}iris{COLOR_RESET}               - Установить Iris Shaders (Fabric)
{COLOR_GREEN}fabricapi{COLOR_RESET}          - Установить Fabric API
{COLOR_GREEN}quiltapi{COLOR_RESET}           - Установить Quilted Fabric API
{COLOR_GREEN}forgeapi{COLOR_RESET}           - Информация о Forge API
{COLOR_GREEN}установить мод <название>{COLOR_RESET} - Поиск и установка любого мода с Modrinth

{COLOR_CYAN}=== УПРАВЛЕНИЕ ПАПКАМИ ==={COLOR_RESET}
{COLOR_GREEN}папка{COLOR_RESET}              - Открыть папку Minecraft
{COLOR_GREEN}папка модов{COLOR_RESET}        - Открыть папку модов
{COLOR_GREEN}ресурспак{COLOR_RESET}          - Открыть папку ресурспаков
{COLOR_GREEN}миры{COLOR_RESET}               - Открыть папку миров
{COLOR_GREEN}скриншоты{COLOR_RESET}          - Открыть папку скриншотов
{COLOR_GREEN}конфиги{COLOR_RESET}            - Открыть папку конфигов
{COLOR_GREEN}схемы{COLOR_RESET}              - Открыть папку схем

{COLOR_CYAN}=== ИНФОРМАЦИЯ И ЗАМЕТКИ ==={COLOR_RESET}
{COLOR_GREEN}инфо{COLOR_RESET}               - Полезная информация (серверы, новости)
{COLOR_GREEN}заметка <текст>{COLOR_RESET}     - Добавить заметку
{COLOR_GREEN}заметки{COLOR_RESET}            - Показать все заметки
{COLOR_GREEN}добавить инфо <текст>{COLOR_RESET} - Добавить строку в информацию
{COLOR_GREEN}очистить инфо{COLOR_RESET}      - Очистить пользовательскую информацию

{COLOR_CYAN}=== СЕРВЕРЫ ==={COLOR_RESET}
{COLOR_GREEN}добавить сервер <имя> <айпи> [версия]{COLOR_RESET} - Добавить сервер в информацию и в игру
{COLOR_GREEN}удалить сервер <айпи>{COLOR_RESET} - Удалить сервер

{COLOR_CYAN}=== ПЛАГИНЫ И ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ ==={COLOR_RESET}
{COLOR_GREEN}плагины{COLOR_RESET}            - Управление плагинами лаунчера
{COLOR_GREEN}добавить команду{COLOR_RESET}    - Мастер добавления пользовательской команды
{COLOR_GREEN}удалить команду <имя>{COLOR_RESET} - Удалить пользовательскую команду
{COLOR_GREEN}команды{COLOR_RESET}            - Список пользовательских команд

{COLOR_CYAN}=== ОБСЛУЖИВАНИЕ ==={COLOR_RESET}
{COLOR_GREEN}бэкап{COLOR_RESET}              - Создать резервную копию (миры, ресурспаки, конфиги, моды, конфиг)
{COLOR_GREEN}конфиг лаунчера{COLOR_RESET}    - Скопировать конфиг лаунчера на рабочий стол
{COLOR_GREEN}лог{COLOR_RESET}                - Скопировать последний лог на рабочий стол
{COLOR_GREEN}краш{COLOR_RESET}               - Скопировать краш-репорты на рабочий стол
{COLOR_GREEN}удалить лаунчер{COLOR_RESET}    - Полностью удалить папку лаунчера

{COLOR_CYAN}=== РАЗНОЕ ==={COLOR_RESET}
{COLOR_GREEN}альт мод{COLOR_RESET}           - Открыть ru-minecraft.ru
    """
    config = load_config()
    if config["user_commands"]:
        help_text += f"\n{COLOR_CYAN}ПОЛЬЗОВАТЕЛЬСКИЕ КОМАНДЫ:{COLOR_RESET}\n"
        for name, data in config["user_commands"].items():
            help_text += f"{COLOR_GREEN}{name}{COLOR_RESET} - {data['type']}: {data['params']}\n"
    plugin_cmds = [name for name, info in plugin_commands.items() if not info.get('hidden', False)]
    if plugin_cmds:
        help_text += f"\n{COLOR_CYAN}КОМАНДЫ ПЛАГИНОВ:{COLOR_RESET}\n"
        for name in plugin_cmds:
            help_text += f"{COLOR_GREEN}{name}{COLOR_RESET} - плагин\n"
    print(help_text)