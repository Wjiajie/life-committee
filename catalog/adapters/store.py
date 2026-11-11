"""JSON / 文本 / CSV 文件读写。"""

import csv
import json
from pathlib import Path


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def read_json_dir(directory: Path) -> list:
    """按文件名顺序读取目录下所有 .json，返回 [(文件名, 内容)]。"""
    if not directory.exists():
        return []
    return [(p.name, read_json(p)) for p in sorted(directory.glob("*.json"))]


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def clear_dir(directory: Path, pattern: str) -> None:
    if directory.exists():
        for p in directory.glob(pattern):
            p.unlink()
