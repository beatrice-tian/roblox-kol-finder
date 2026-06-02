from pathlib import Path

import pandas as pd

from src.models.creator import CreatorRecord


class CsvReportExporter:
    """导出中文表头、Excel 友好的 UTF-8 BOM CSV。"""

    COLUMN_ORDER = [
        "排名",
        "创作者",
        "平台",
        "榜单分层",
        "潜力等级",
        "潜力分",
        "粉丝数",
        "平均播放",
        "平均点赞",
        "互动率",
        "稳定度",
        "爆款记录",
        "代表视频",
        "代表视频播放",
        "视频链接",
        "频道链接",
        "Shorts占比",
        "分析信号",
        "字幕关键词",
        "运营观察",
        "数据简评",
        "推荐原因",
        "发布时间",
    ]

    def export(
        self,
        records: list[CreatorRecord],
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        rows = [
            record.to_export_row(rank=idx)
            for idx, record in enumerate(records, start=1)
        ]
        df = pd.DataFrame(rows)

        for col in self.COLUMN_ORDER:
            if col not in df.columns:
                df[col] = ""

        df = df[self.COLUMN_ORDER]
        df = self._format_readable_columns(df)

        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        return output_path

    @staticmethod
    def _format_readable_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for col in ("粉丝数", "平均播放", "平均点赞", "代表视频播放"):
            if col in df.columns:
                df[col] = df[col].apply(_format_number)
        return df


def _format_number(value: object) -> object:
    try:
        return f"{int(float(value)):,}"
    except (TypeError, ValueError):
        return value
