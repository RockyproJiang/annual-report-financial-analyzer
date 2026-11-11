# 上市公司年报财务分析流水线

面向上市公司年度报告的 Python 财务分析流水线——从 PDF 年报自动提取合并三大报表、科目标准化、单位换算、报告期识别、指标计算、会计勾稽校验、规则引擎风险识别，并可调用 DeepSeek 生成专项分析报告。

## 功能特性

- **三大报表提取**：用 `pdfplumber` 从年报 PDF 提取合并资产负债表、合并利润表、合并现金流量表，保留页码作为证据。
- **科目标准化与单位换算**：基于 `mapping/subject_map.csv` 映射标准科目，自动识别千元/万元/百万元/亿元并统一换算为元；支持报告期识别与多报告拼接。
- **核心指标计算**：偿债、营运、盈利、成长、现金流质量五大类指标（流动比率、资产负债率、周转率、毛利率、净利率、ROE、增长率等）。
- **会计勾稽校验**：资产负债表平衡、营业利润、净利润、现金净增加、未分配利润等。
- **规则引擎风险识别**：审计意见、退市风险、非经常性损益依赖、利润与现金流背离等告警，并给出整体风险等级。
- **关键信息提取**：审计意见、非经常性损益、现金分红、总股本、合并范围变化等。
- **大模型专项报告**：调用 DeepSeek 生成归因分析（`step5_llm_report.py`）。
- **结构化输出**：按报告输出到 `output/<报告名>/`，含 CSV、JSON 与 Markdown（原始提取、标准化数据、指标结果、异常清单、证据链、分析报告、结构化基准包）。

## 技术栈 / 依赖

- Python 3.10+
- `pandas>=2.0`、`pdfplumber>=0.10`、`openai>=1.30`、`fpdf2>=2.7`（见 `requirements.txt`）
- 可选：DeepSeek API（兼容 OpenAI 协议的 LLM 归因分析，仅在配置密钥后启用）

## 目录结构

```text
annual-report-financial-analyzer/
├── main.py                       # 总入口：多报告批处理，串联各 step
├── config.py                     # 路径、API、阈值；含极简 .env 加载器
├── company_meta.py               # 公司/行业元数据解析
├── debug_map.py                  # 科目映射覆盖情况检查
├── extract_financial_datav2.py   # 三大报表提取
├── extract_key_info.py           # 关键信息（审计意见、分红等）提取
├── step1_extract.py              # 步骤一：PDF 提取
├── step2_standardize.py          # 步骤二：科目标准化、单位换算、报告拼接
├── step3_indicators.py           # 步骤三：指标计算与勾稽校验
├── step4_rules.py                # 步骤四：规则引擎异常扫描
├── step5_llm_report.py           # 步骤五：DeepSeek 归因报告（需 API Key）
├── step6_structured.py           # 步骤六：风险汇总与结构化输出
├── requirements.txt
├── .gitignore
├── LICENSE                       # MIT
├── README.md
├── files/                        # 待分析的年报 PDF 样本（7 份）
├── mapping/                      # 科目与行业映射 CSV
│   ├── subject_map.csv
│   ├── company_meta.csv
│   ├── industry_keywords.csv
│   └── industry_profile.csv
└── output/                       # 结果：CSV / JSON / MD / PDF（按报告分目录）
```

## 快速开始

1. 克隆与安装依赖：

```bash
git clone https://github.com/RockyproJiang/annual-report-financial-analyzer.git
cd annual-report-financial-analyzer
pip install -r requirements.txt
```

2. 将待分析的年报 PDF 放入 `files/` 目录。

3. 运行流水线（总入口会按 step 顺序处理 `files/` 下所有报告并输出到 `output/`）：

```bash
python main.py
```

可先用 `python debug_map.py "贵州茅台：2025年年度报告"` 单独检查科目映射覆盖情况；也可按 `step1_extract.py` → `step6_structured.py` 的顺序逐步调试。

## 配置与安全说明

- **API Key 处理方式**：调用大模型的归因分析需要设置环境变量 `DEEPSEEK_API_KEY`。`config.py` 第 71 行为 `DEEPSEEK_API_KEY = _env_str("DEEPSEEK_API_KEY", "")`，即**空默认值、不硬编码任何密钥**；未配置时 `step5` 的 LLM 环节不可用，但其余步骤正常运行。`config.py` 自带一个不依赖第三方库的极简 `.env` 加载器（`_load_dotenv`），会读取项目根目录的 `.env` 且不覆盖已有环境变量。
- **仓库中不含任何真实 API Key**。请勿把密钥写进代码或提交到 Git；配置时只使用明显占位值，例如在项目根目录 `.env` 中写：

```bash
DEEPSEEK_API_KEY=sk-xxx
```

  或在 shell 中 `export DEEPSEEK_API_KEY=你的密钥`。请确认 `.gitignore` 已忽略 `.env`（当前已包含 `.env` 与 `.env.*`）。`DEEPSEEK_BASE_URL`（默认 `https://api.deepseek.com`）与 `DEEPSEEK_MODEL` 同样可通过环境变量覆盖。
- `files/` 内年报 PDF 与 `output/` 内结果仅作样本与演示，注意不得包含敏感内部资料；年报可能涉及版权，请勿随意公开上传。
- 已清理误提交的 `__pycache__/*.pyc` 并补充 `.gitignore`（忽略 `__pycache__/`、`*.py[cod]`、`.env` 等），避免缓存与密钥入库。
- 本项目输出仅供学习、研究与辅助分析，不构成投资建议；LLM 生成内容须人工复核。

## 许可证

本项目采用 MIT License，详见 `LICENSE`（Copyright (c) 2026 Rocky）。
