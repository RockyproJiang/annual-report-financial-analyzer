# -*- coding: utf-8 -*-
"""全局配置：路径、API、阈值。所有脚本只从这里读配置。

安全说明：
- 不再在代码中硬编码 API Key。
- 优先从环境变量读取，也支持项目根目录下的 .env 文件。
- 建议将 .env 加入 .gitignore，不要把密钥提交到 Git。
"""

import os
import re
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# 项目路径
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
OUTPUT_DIR = BASE_DIR / "output"
MAPPING_CSV = BASE_DIR / "mapping" / "subject_map.csv"


# ---------------------------------------------------------------------------
# 简易 .env 加载器（不依赖第三方库）
# ---------------------------------------------------------------------------
def _load_dotenv(dotenv_path: Path) -> None:
    """如果存在 .env 文件，则将其中的键值对写入 os.environ（已存在的变量不覆盖）。"""
    if not dotenv_path.is_file():
        return
    try:
        with dotenv_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        # .env 解析失败时静默忽略，不影响后续从系统环境变量读取
        pass


_load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# 辅助函数：从环境变量读取配置
# ---------------------------------------------------------------------------
def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_float(key: str, default: float) -> float:
    raw = os.getenv(key, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        print(f"[config] 环境变量 {key}={raw!r} 不是合法数字，使用默认值 {default}")
        return default


# ---------------------------------------------------------------------------
# DeepSeek / LLM 配置
# ---------------------------------------------------------------------------
DEEPSEEK_API_KEY = _env_str("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = _env_str("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = _env_str("DEEPSEEK_MODEL", "deepseek-v4-flash")

if not DEEPSEEK_API_KEY:
    print(
        "[config] 警告：未检测到 DEEPSEEK_API_KEY。"
        "step5 的大模型归因分析将不可用；"
        "请在环境变量或项目根目录 .env 中配置后重试。"
    )


# ---------------------------------------------------------------------------
# 阈值配置（支持环境变量覆盖，默认值保持原逻辑）
# ---------------------------------------------------------------------------
TOLERANCE_GOV_BOND = _env_float("TOLERANCE_GOV_BOND", 0.021)
RING_CHANGE_LIMIT = _env_float("RING_CHANGE_LIMIT", 0.50)
CASH_PROFIT_RATIO = _env_float("CASH_PROFIT_RATIO", 0.50)
NONREC_RATIO = _env_float("NONREC_RATIO", 0.30)          # 非经常性损益占归母净利润：≥30% 预警
NONREC_HIGH_RATIO = _env_float("NONREC_HIGH_RATIO", 0.50)  # ≥50% 异常


# ---------------------------------------------------------------------------
# 输出路径管理
# ---------------------------------------------------------------------------
_INVALID_CHARS = re.compile(r'[\\/:*?"<>|]')


def make_report_paths(pdf_stem: str) -> "ReportPaths":
    name = _INVALID_CHARS.sub("＿", pdf_stem.strip()).rstrip(". ")
    return ReportPaths(name or "未命名报告")


@dataclass
class ReportPaths:
    report_name: str

    def __post_init__(self):
        d = OUTPUT_DIR / self.report_name
        self.dir = d
        self.RAW_CSV = d / "01_原始提取.csv"
        self.AUDIT_CSV = d / "01_审计汇总.csv"
        self.ERROR_CSV = d / "01_错误日志.csv"
        self.KEY_INFO_CSV = d / "01_关键信息.csv"
        self.STD_CSV = d / "02_标准化数据.csv"
        self.IND_CSV = d / "03_指标结果.csv"
        self.ALERT_CSV = d / "04_异常清单.csv"
        self.EVIDENCE_JSON = d / "05_证据链.json"
        self.REPORT_MD = d / "06_分析报告.md"
        self.BENCH_JSON = d / "07_结构化基准包.json"
        self.BASE_CSV = d / "07-1_基础信息.csv"
        self.IND_CALC_CSV = d / "07-2_指标计算结果.csv"
        self.IND_ABN_CSV = d / "07-3_指标异常结果.csv"
        self.GOUJI_CSV = d / "07-4_勾稽校验结果.csv"
        self.RISK_CSV = d / "07-5_汇总风险.csv"

    def mkdir(self):
        self.dir.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    # 直接运行本文件时，打印当前关键配置，方便排查
    print("BASE_DIR        =", BASE_DIR)
    print("FILES_DIR       =", FILES_DIR)
    print("OUTPUT_DIR      =", OUTPUT_DIR)
    print("MAPPING_CSV     =", MAPPING_CSV)
    print("DEEPSEEK_BASE_URL =", DEEPSEEK_BASE_URL)
    print("DEEPSEEK_MODEL    =", DEEPSEEK_MODEL)
    print("DEEPSEEK_API_KEY  =", "已配置" if DEEPSEEK_API_KEY else "未配置")
    print("TOLERANCE_GOV_BOND =", TOLERANCE_GOV_BOND)
    print("RING_CHANGE_LIMIT  =", RING_CHANGE_LIMIT)
    print("CASH_PROFIT_RATIO  =", CASH_PROFIT_RATIO)
    print("NONREC_RATIO       =", NONREC_RATIO)
    print("NONREC_HIGH_RATIO  =", NONREC_HIGH_RATIO)