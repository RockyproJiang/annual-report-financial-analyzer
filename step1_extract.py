# -*- coding: utf-8 -*-
"""Step1：逐份解析 files/ 下所有PDF。
输出：01_原始提取.csv / 01_审计汇总.csv / 01_错误日志.csv / 01_关键信息.csv
返回 {报告名: {"raw": DataFrame, "key_info": dict}} 供主流程逐份处理。"""
import pandas as pd

import extract_financial_datav2 as v2
import extract_key_info as ki
import config
from config import FILES_DIR


def run_all(log) -> dict:
    if not FILES_DIR.is_dir():
        raise SystemExit(f"未找到PDF目录：{FILES_DIR}")
    pdfs = sorted(FILES_DIR.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"{FILES_DIR} 中没有PDF文件")

    result = {}
    for pdf in pdfs:
        stem = pdf.stem
        log(f"[step1] 解析 {pdf.name}")
        paths = config.make_report_paths(stem)
        paths.mkdir()

        rows, audits, errors = [], [], []
        try:
            rows, file_audits = v2.extract_from_pdf(pdf)
            audits.extend(file_audits)
        except Exception as exc:
            errors.append({"文件名": pdf.name, "错误类型": type(exc).__name__,
                           "错误信息": str(exc)})
            log(f"[step1] 失败 {pdf.name}: {exc}")

        df = pd.DataFrame(rows, columns=v2.OUTPUT_FIELDS)
        df.to_csv(paths.RAW_CSV, index=False, encoding="utf-8-sig")
        pd.DataFrame(audits).to_csv(paths.AUDIT_CSV, index=False, encoding="utf-8-sig")
        pd.DataFrame(errors).to_csv(paths.ERROR_CSV, index=False, encoding="utf-8-sig")

        key_info = {}
        try:
            key_info = ki.extract_key_info(pdf)
        except Exception as exc:
            log(f"[step1] 关键信息提取失败 {pdf.name}: {exc}")

        ki_rows = []
        for k, v in key_info.items():
            if isinstance(v, list):
                v = " | ".join(str(x) for x in v)
            ki_rows.append({"字段": k, "值": str(v)})
        pd.DataFrame(ki_rows).to_csv(paths.KEY_INFO_CSV, index=False, encoding="utf-8-sig")

        log(f"[step1] {stem}：原始提取 {len(df)} 行；关键信息 {len(ki_rows)} 条；错误 {len(errors)} 条 → output/{paths.report_name}/")
        result[stem] = {"raw": df, "key_info": key_info}
    return result


if __name__ == "__main__":
    run_all(lambda m: print(m))