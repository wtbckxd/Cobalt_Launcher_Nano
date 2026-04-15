import json
import os
from datetime import datetime
from constants import ACCOUNTS_FILE, COLOR_GREEN, COLOR_RED
from config_manager import load_config, save_config

def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_accounts(accounts):
    with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(accounts, f, indent=4, ensure_ascii=False)

def add_offline_account(username):
    accounts = load_accounts()
    account_id = max([acc["id"] for acc in accounts], default=0) + 1
    account = {
        "id": account_id,
        "username": username,
        "type": "offline",
        "created_at": datetime.now().isoformat()
    }
    accounts.append(account)
    save_accounts(accounts)
    return account

def rename_account(account_id, new_username):
    accounts = load_accounts()
    for acc in accounts:
        if acc["id"] == account_id:
            acc["username"] = new_username
            save_accounts(accounts)
            print(f"{COLOR_GREEN}Аккаунт переименован в {new_username}{COLOR_RESET}")
            return True
    print(f"{COLOR_RED}Аккаунт с ID {account_id} не найден{COLOR_RESET}")
    return False

def delete_account(account_id):
    accounts = load_accounts()
    accounts = [acc for acc in accounts if acc["id"] != account_id]
    save_accounts(accounts)
    config = load_config()
    if config.get("current_account") == account_id:
        config["current_account"] = None
        save_config(config)
    print(f"{COLOR_GREEN}Аккаунт удалён{COLOR_RESET}")
    return True

def get_account_by_id(account_id):
    accounts = load_accounts()
    for account in accounts:
        if account["id"] == account_id:
            return account
    return None