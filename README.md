# 财报智析：上市公司年报财务分析流水线

> Annual Report Financial Analyzer  
> 从上市公司年报 PDF 到财务指标、勾稽校验、风险告警与 LLM 归因报告的一站式流水线。

## 项目简介

本项目面向上市公司年度报告分析场景，基于 Python 与 pdfplumber，从年报 PDF 中自动提取合并资产负债表、合并利润表、合并现金流量表，并完成科目映射、单位统一、报告期识别与多报告拼接。系统进一步计算核心财务指标，执行会计勾稽校验，结合规则引擎识别异常并评估风险等级，同时提取审计意见、非经常性损益、现金分红等关键信息，调用 DeepSeek 大模型生成专项归因分析，最终输出 CSV、JSON 与 Markdown 结构化结果。

## 主要功能

- **报表提取**：从年报 PDF 提取合并资产负债表、合并利润表、合并现金流量表。
- **科目标准化**：基于 `mapping/subject_map.csv` 将原始科目映射为标准科目。
- **单位统一**：自动识别千元、万元、百万元、亿元并统一换算为元。
- **多报告拼接**：支持多份报告批处理，并补充上一年期初数据。
- **指标计算**：流动比率、资产负债率、周转率、毛利率、净利率、ROE、增长率等。
- **勾稽校验**：资产负债表平衡、营业利润、净利润、现金净增加、未分配利润等。
- **规则引擎**：审计意见、退市风险、非经常性损益依赖、利润与现金流背离等告警。
- **LLM 归因报告**：调用 DeepSeek 生成专项归因分析。
- **结构化输出**：输出原始提取、标准化数据、指标结果、异常清单、证据链、Markdown 报告与结构化基准包。

## 环境要求

- Python 3.10+
- 依赖见 `requirements.txt`

## 安装

```bash
git clone https://github.com/your-name/annual-report-financial-analyzer.git
cd annual-report-financial-analyzer

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## 配置

1. 将年报 PDF 放入 `files/` 目录。
2. 检查 `mapping/` 下的映射文件：
   - `subject_map.csv`
   - `company_meta.csv`
   - `industry_keywords.csv`
   - `industry_profile.csv`
3. 配置 DeepSeek API Key。推荐使用环境变量，不要写入代码：

```bash
# macOS / Linux
export DEEPSEEK_API_KEY="your-api-key"

# Windows PowerShell
$env:DEEPSEEK_API_KEY="your-api-key"
```

并在 `config.py` 中改为：

```python
import os
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
```

也可以根据需要调整：

```python
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
```

## 运行

```bash
python main.py
```

如需单独检查映射覆盖情况：

```bash
python debug_map.py "贵州茅台：2025年年度报告"
```

## 输出目录

每份报告会在 `output/<报告名>/` 下生成：

| 文件 | 说明 |
|---|---|
| `01_原始提取.csv` | PDF 原始提取结果 |
| `01_审计汇总.csv` | 提取审计汇总 |
| `01_错误日志.csv` | 提取错误日志 |
| `01_关键信息.csv` | 审计意见、行业、分红等 |
| `02_标准化数据.csv` | 科目标准化后的数据 |
| `03_指标结果.csv` | 财务指标计算结果 |
| `04_异常清单.csv` | 规则引擎异常告警 |
| `05_证据链.json` | 科目证据与指标证据 |
| `06_分析报告.md` | 最终 Markdown 分析报告 |
| `07_结构化基准包.json` | 结构化输出总包 |
| `07-1_基础信息.csv` | 基础信息 |
| `07-2_指标计算结果.csv` | 指标计算结果 |
| `07-3_指标异常结果.csv` | 指标异常结果 |
| `07-4_勾稽校验结果.csv` | 勾稽校验结果 |
| `07-5_汇总风险.csv` | 汇总风险 |

## 项目结构

```text
.
├── main.py
├── config.py
├── company_meta.py
├── debug_map.py
├── extract_financial_datav2.py
├── extract_key_info.py
├── step1_extract.py
├── step2_standardize.py
├── step3_indicators.py
├── step4_rules.py
├── step5_llm_report.py
├── step6_structured.py
├── requirements.txt
├── mapping/
│   ├── subject_map.csv
│   ├── company_meta.csv
│   ├── industry_keywords.csv
│   └── industry_profile.csv
├── files/
│   └── .gitkeep
└── output/
    └── .gitkeep
```

## 注意事项

- 本项目输出仅供学习、研究与辅助分析，不构成投资建议。
- LLM 生成内容可能存在偏差，必须人工复核。
- 年报 PDF 可能涉及版权，请勿随意公开上传。
- 请勿将 API Key、密码等敏感信息提交到 Git 仓库。
- 首次运行前建议先用 `debug_map.py` 检查科目映射覆盖情况。

## License

MIT License. 详见 `LICENSE`。