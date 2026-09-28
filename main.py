# -*- coding: utf-8 -*-
"""总入口：多报告批处理版。"""
import sys
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import json
import traceback
import pandas as pd

import config
import company_meta
import step1_extract
import step2_standardize as s2
import step3_indicators as s3
import step4_rules as s4
import step5_llm_report as s5
import step6_structured as s6
from config import OUTPUT_DIR


def process_one(stem: str, raw: pd.DataFrame, key_info: dict, log) -> str:
    paths = config.make_report_paths(stem)
    log(f"===== 开始处理：{stem} =====")

    std = s2.run(raw, log, paths)
    if std.empty:
        log(f"[跳过] {stem}：标准化结果为空，请检查 01_原始提取.csv 与 mapping/subject_map.csv")
        return "标准化失败"
    companies, continuity = s2.assemble(std)
    nonrec_df = s2.extract_nonrec(raw)

    all_ind, all_alerts = [], []
    comp = next(iter(companies))
    reports = companies[comp]
    fname, item = next(iter(reports.items()))
    d, evid = item["d"], item["evid"]
    period = f"{item['year']}年{item['period']}"

    log(f"[step3] 计算指标：{comp} {period}")
    ind = s3.compute_indicators(d)
    hits = s3.check_indicators(ind)
    ind["_threshold_hits"] = hits
    gouji = s3.check_gouji(d, ind)

    ring = s4.compute_ring(d, None)
    alerts = s4.scan(d, ind, gouji, continuity, nonrec_df, ring, key_info=key_info)
    log(f"[step4] {stem}：发现异常 {len(alerts)} 项；"
        f"勾稽 {len(gouji)} 项中不通过 "
        f"{sum(1 for r in gouji if r['勾稽校验结论'] == '不通过')} 项")

    for k, v in ind.items():
        if not k.startswith("_"):
            all_ind.append({"公司": comp, "报告期": period, "指标": k,
                            "数值": round(v, 6) if isinstance(v, float) else v})
    for a in alerts:
        a.update({"公司": comp, "报告期": period})
        all_alerts.append(a)
    pd.DataFrame(all_ind).to_csv(paths.IND_CSV, index=False, encoding="utf-8-sig")
    pd.DataFrame(all_alerts).to_csv(paths.ALERT_CSV, index=False, encoding="utf-8-sig")
    evidence = {"科目证据": evid, "环比": ring,
                "指标": {k: v for k, v in ind.items() if not k.startswith("_")},
                "非经常性损益": nonrec_df.to_dict("records") if len(nonrec_df) else [],
                "关键信息": key_info,
                "跨报告衔接": continuity}
    paths.EVIDENCE_JSON.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8")

    pdf_path = config.FILES_DIR / f"{stem}.pdf"
    meta = company_meta.resolve_meta(comp, pdf_path, log)

    alerts, exempt_log = s6.apply_industry_exemption(alerts, meta.get("所属行业", ""))
    if exempt_log:
        log(f"[exempt] {stem}：行业豁免 {len(exempt_log)} 项：" +
            "；".join(f"{e['项目']}({e['原始等级']}→预警)" for e in exempt_log))
    risk = s6.overall_risk(alerts)
    log(f"[risk] {comp} 整体风险等级：{risk[0]}")

    s5.generate(comp, period, ind, alerts, gouji, evid, nonrec_df, d, meta, risk,
                paths, exempt_log, key_info=key_info)

    pkg = s6.build(comp, period, meta, ind, hits, gouji, alerts, evid, paths,
                   exempt_log, key_info=key_info)
    log(f"[step6] {stem}：结构化基准包已生成（勾稽{len(pkg['勾稽校验结果'])}项/"
        f"指标{len(pkg['指标计算结果'])}项/"
        f"异常{sum(1 for x in pkg['指标异常结果'] if x['异常等级'] != '无')}项，"
        f"整体风险：{pkg['汇总风险']['整体风险等级']}）")
    return risk[0]


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    log_lines = []
    def log(msg):
        print(msg)
        log_lines.append(msg)

    summary = []
    try:
        raw_map = step1_extract.run_all(log)   # {stem: {"raw": DataFrame, "key_info": dict}}
        if not raw_map:
            log("[中止] files/ 中没有可处理的PDF")
            return
        for stem, item in raw_map.items():
            try:
                level = process_one(stem, item["raw"], item.get("key_info", {}), log)
                summary.append({"报告名": stem, "整体风险等级": level})
            except Exception:
                log(f"[报告失败] {stem}\n" + traceback.format_exc())
                summary.append({"报告名": stem, "整体风险等级": "处理失败"})
        pd.DataFrame(summary).to_csv(OUTPUT_DIR / "00_批处理汇总.csv",
                                     index=False, encoding="utf-8-sig")
        ok = sum(1 for s in summary if s["整体风险等级"] not in ("处理失败", "标准化失败"))
        log(f"[done] 共处理 {len(summary)} 份报告：成功 {ok} 份；"
            f"汇总见 00_批处理汇总.csv")
    except Exception:
        log("流程异常：\n" + traceback.format_exc())
    finally:
        (OUTPUT_DIR / "run.log").write_text("\n".join(log_lines), encoding="utf-8")


if __name__ == "__main__":
    main()