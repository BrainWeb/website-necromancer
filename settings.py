import json
import os

DEFAULT_SETTINGS_FILE = 'necromancer_settings.json'

DEFAULT_SETTINGS = {
    "logging": {
        "console": True,
        "file": False,
        "log_file_path": "necromancer.log",
        "level": "INFO" # Can be DEBUG, INFO, WARNING, ERROR, CRITICAL
    }
}

def load_settings():
    if os.path.exists(DEFAULT_SETTINGS_FILE):
        try:
            with open(DEFAULT_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Deep update the default settings with loaded settings
                for key, value in settings.items():
                    if isinstance(value, dict) and key in DEFAULT_SETTINGS:
                        DEFAULT_SETTINGS[key].update(value)
                    else:
                        DEFAULT_SETTINGS[key] = value
        except Exception as e:
            print(f"Warning: Failed to load settings file: {e}")
    return DEFAULT_SETTINGS

def save_settings(settings):
    try:
        with open(DEFAULT_SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Warning: Failed to save settings file: {e}")
