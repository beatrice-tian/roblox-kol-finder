"""CLI：从 CSV 生成 web/data/reports/YYYY-MM-DD.json 并更新 index.json。"""

from src.web.data_export import default_paths, export_web_data


def main() -> None:
    csv_path, reports_path = default_paths()
    if not csv_path.exists():
        raise SystemExit(f"找不到报告: {csv_path}，请先运行 main.py")
    payload, json_path = export_web_data(csv_path)
    with_avatar = sum(1 for c in payload["creators"] if c.get("avatar_url"))
    print(f"Web 数据已归档: {json_path}")
    print(f"索引: {reports_path / 'index.json'}")
    print(f"频道头像: {with_avatar}/{len(payload['creators'])}")


if __name__ == "__main__":
    main()
