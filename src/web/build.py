"""CLI：从 CSV 生成 web/data/report.json。"""

from pathlib import Path

from src.web.data_export import default_paths, export_web_data


def main() -> None:
    csv_path, json_path = default_paths()
    if not csv_path.exists():
        raise SystemExit(f"找不到报告: {csv_path}，请先运行 main.py")
    payload = export_web_data(csv_path, json_path)
    with_avatar = sum(1 for c in payload["creators"] if c.get("avatar_url"))
    print(f"Web 数据已生成: {json_path}")
    print(f"频道头像: {with_avatar}/{len(payload['creators'])}")


if __name__ == "__main__":
    main()
