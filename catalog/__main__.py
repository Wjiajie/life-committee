"""命令行入口：python -m catalog <阶段> [文件]"""

import argparse
import json
import sys

from catalog import build


def main() -> None:
    parser = argparse.ArgumentParser(prog="catalog", description="参考答案 epub → 作者目录")
    parser.add_argument("stage", choices=["extract", "names", "build", "validate", "checks"])
    parser.add_argument("file", nargs="?", help="validate 阶段可只校验 data/curated/sources/ 下的某个文件")
    args = parser.parse_args()
    stats = build.validate(args.file) if args.stage == "validate" else getattr(build, args.stage)()
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    if stats.get("problems"):
        sys.exit(1)


if __name__ == "__main__":
    main()
