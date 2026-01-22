import json
from datetime import datetime
from typing import Dict, List

REGISTRY_PATH = "data/ipo_registry.json"


def _load_registry() -> Dict:
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_ipos() -> List[Dict]:
    data = _load_registry()
    return data.get("ipos", [])


def get_ipos_by_status(status: str) -> List[Dict]:
    status = status.lower()
    return [
        ipo for ipo in get_all_ipos()
        if ipo.get("status") == status
    ]


def get_upcoming_ipos() -> List[Dict]:
    return get_ipos_by_status("upcoming")


def get_open_ipos() -> List[Dict]:
    return get_ipos_by_status("open")


def get_recently_closed_ipos() -> List[Dict]:
    return get_ipos_by_status("closed")


def find_ipo_by_name(name: str) -> Dict | None:
    name = name.lower()
    for ipo in get_all_ipos():
        if name in ipo["name"].lower() or name == ipo["short_name"].lower():
            return ipo
    return None
