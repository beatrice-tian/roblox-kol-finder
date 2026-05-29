"""Roblox KOL Finder 入口。"""

from src.pipeline.finder import KolFinderPipeline


def main() -> None:
    pipeline = KolFinderPipeline()
    _top, output_path = pipeline.run()
    print("\n完成！")
    print(f"报告已保存: {output_path}")


if __name__ == "__main__":
    main()
