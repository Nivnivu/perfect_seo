import glob
import yaml
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent


def get_config_files() -> list[Path]:
    """List all config YAML files in project root, excluding config.example.yaml."""
    files: list[Path] = []
    default = ROOT_DIR / "config.yaml"
    if default.exists():
        files.append(default)
    for f in sorted(glob.glob(str(ROOT_DIR / "config.*.yaml"))):
        p = Path(f)
        if p.name != "config.example.yaml":
            files.append(p)
    return files


def get_site_id(path: Path) -> str:
    """Extract site identifier from filename: config.pawly.yaml -> 'pawly', config.yaml -> 'default'."""
    stem = path.stem  # e.g. "config" or "config.pawly"
    if stem == "config":
        return "default"
    return stem[len("config."):]


def list_sites() -> list[dict]:
    """Return summary info for all configured sites."""
    result = []
    for path in get_config_files():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            site_id = get_site_id(path)
            site = data.get("site", {})
            result.append({
                "id": site_id,
                "file": path.name,
                "name": site.get("name", site_id),
                "domain": site.get("domain", ""),
                "language": site.get("language", "en"),
                "platform": data.get("platform", "mongodb"),
                "has_gsc": bool(data.get("search_console", {}).get("credentials_file", "")),
            })
        except Exception:
            pass
    return result


def get_site(site_id: str) -> Optional[dict]:
    """Load full config dict for a site."""
    path = _resolve_path(site_id)
    if not path or not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data["_id"] = site_id
    data["_file"] = path.name
    return data


def save_site(site_id: str, config_data: dict) -> Path:
    """Write config data to YAML. Strips internal _ fields before saving."""
    config_data = {k: v for k, v in config_data.items() if not k.startswith("_")}
    path = ROOT_DIR / ("config.yaml" if site_id == "default" else f"config.{site_id}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    return path


def delete_site(site_id: str) -> bool:
    path = _resolve_path(site_id)
    if path and path.exists():
        path.unlink()
        return True
    return False


def _resolve_path(site_id: str) -> Optional[Path]:
    if site_id == "default":
        return ROOT_DIR / "config.yaml"
    return ROOT_DIR / f"config.{site_id}.yaml"
