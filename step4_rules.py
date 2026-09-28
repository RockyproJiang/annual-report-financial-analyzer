# -*- coding: utf-8 -*-
"""Step4：规则引擎。含审计意见/退市风险/净资产为负/非经常性损益依赖等定性告警。
要点：
1) 审计意见判定顺序不可调换（"保留意见"是"标准无保留意见"的子串）；
2) 非经常性损益优先用 key_info 的"非经常性损益合计"（已含税与少数股东减项），
   明细行求和仅作回退；占比 ≥30% 预警、≥50% 异常。"""
from config import (RING_CHANGE_LIMIT, CASH_PROFIT_RATIO,
                    NONREC_RATIO, NONREC_HIGH_RATIO)


def _key_info_value(key_info, key, default=""):
    if not key_info:
        return default
    v = key_info.get(key, default)
    return v if v is not None else default


def _to_float(v):
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return None


def _audit_level(audit: str):
    """返回 (等级, 权重, 说明) 或 None。判定顺序不可调换。"""
    if not audit:
        return None
    if "无法表示意见" in audit:
        return ("极高", 15, "审计机构对财务报表出具无法表示意见，报表可靠性严重存疑")
    if "否定意见" in audit:
        return ("极高", 15, "审计机构否定意见，报表未公允反映财务状况")
    if "带强调事项段" in audit:
        return ("高风险", 10, "审计意见带强调事项段，存在需提请注意的重大事项")
    if "无保留" in audit:          # 标准无保留意见/无保留意见 → 标准意见，不告警
        return None
    if "保留意见" in audit:
        return ("高风险", 10, "审计机构保留意见，存在重大不确定性")
    return None


def scan(d, ind, gouji, continuity, nonrec_df, ring, key_info=None):
    A = []
    key_info = key_info or {}

    # --- 0) 勾稽不通过项转告警 ---
    for r in gouji:
        if r.get("勾稽校验结论") != "不通过":
            continue
        A.append({"类别": "勾稽校验", "项目": r["勾稽项名称"], "数值": r.get("差异率", ""),
                  "等级": r["等级"], "权重": r["权重"],
                  "说明": f"理论值{r.get('理论计算值')} vs 实际值{r.get('报表实际值')}，{r['风险说明']}"})

    # --- 1) 指标阈值 ---
    for r in ind.get("_threshold_hits", []):
        v = r["数值"]
        if isinstance(v, float):
            note = f"{r['说明']}（同比变动 {v:.4f}pp）" if "pp" in r["说明"] else f"{r['说明']}（当前值 {v:.4f}）"
        else:
            note = r["说明"]
        A.append({"类别": "指标阈值", "项目": r["指标"], "数值": round(v, 4) if isinstance(v, float) else v,
                  "等级": r["等级"], "权重": r["权重"], "说明": note})

    # --- 2) 审计意见非标 ---
    audit = str(_key_info_value(key_info, "审计意见类型", "")).strip()
    hit = _audit_level(audit)
    if hit:
        A.append({"类别": "审计意见", "项目": audit, "数值": audit,
                  "等级": hit[0], "权重": hit[1], "说明": hit[2]})

    # --- 3) 退市风险：净资产为负 ---
    e_e = d.get("资产负债表", {}).get("所有者权益_期末")
    if e_e is not None and e_e < 0:
        A.append({"类别": "退市风险", "项目": "净资产为负", "数值": f"{e_e:,.2f}",
                  "等级": "极高", "权重": 15,
                  "说明": "期末净资产为负，触及退市风险警示"})

    # --- 4) 持续经营迹象 ---
    if e_e is not None and e_e < 0 and (ind.get("现金流量比率") or 0) < 0:
        A.append({"类别": "持续经营", "项目": "资不抵债+经营现金流为负", "数值": "存在重大不确定性",
                  "等级": "高风险", "权重": 12,
                  "说明": "所有者权益为负且经营现金流净流出，持续经营能力存在重大不确定性"})

    # --- 5) 利润与现金流背离 ---
    ni = ind.get("_净利润_本期"); ocf = ind.get("_经营现金流_本期")
    if ni is not None and ocf is not None:
        if ni > 0 and ocf < 0:
            A.append({"类别": "利润现金流背离", "项目": "净现比背离",
                      "数值": f"净利润{ni:,.0f}/经营现金流{ocf:,.0f}",
                      "等级": "高风险", "权重": 10,
                      "说明": "盈利但经营现金流为负，纸面利润，需核查应收/存货挂账与收入确认政策"})
        elif ni > 0 and ocf / ni < CASH_PROFIT_RATIO:
            A.append({"类别": "利润现金流背离", "项目": "净现比偏低",
                      "数值": round(ocf / ni, 3), "等级": "预警", "权重": 7,
                      "说明": f"经营现金流/净利润={ocf/ni:.2f}，低于{CASH_PROFIT_RATIO}，盈利质量存疑"})

    # --- 6) 非经常性损益依赖（优先用"合计"字段，分档告警） ---
    nonrec_total = _to_float(_key_info_value(key_info, "非经常性损益合计", ""))
    if nonrec_total is None and nonrec_df is not None and len(nonrec_df):
        try:
            nonrec_total = float(nonrec_df["本期金额"].sum())
        except Exception:
            nonrec_total = None
    ni_for_nonrec = _to_float(_key_info_value(key_info, "归母净利润", ""))
    if ni_for_nonrec is None:
        ni_for_nonrec = ni
    if nonrec_total is not None and ni_for_nonrec and ni_for_nonrec > 0:
        ratio = abs(nonrec_total) / ni_for_nonrec
        if ratio >= NONREC_HIGH_RATIO:
            A.append({"类别": "非经常性损益", "项目": "非经常性损益占归母净利润比例",
                      "数值": round(ratio, 4), "等级": "异常", "权重": 8,
                      "说明": f"非经常性损益合计{nonrec_total:,.2f}元，占归母净利润{ratio:.2%}"
                              f"（≥{NONREC_HIGH_RATIO:.0%}），利润高度依赖一次性项目"})
        elif ratio >= NONREC_RATIO:
            A.append({"类别": "非经常性损益", "项目": "非经常性损益占归母净利润比例",
                      "数值": round(ratio, 4), "等级": "预警", "权重": 5,
                      "说明": f"非经常性损益合计{nonrec_total:,.2f}元，占归母净利润{ratio:.2%}"
                              f"（≥{NONREC_RATIO:.0%}），需以扣非口径评估主业真实盈利"})

    # --- 7) 会计口径变化 ---
    for c in continuity:
        A.append({"类别": "会计口径变化", "项目": f"期初衔接:{c['科目']}", "数值": c["差异%"],
                  "等级": "高", "权重": 9,
                  "说明": f"{c['当前报告']}期初数与{c['上一报告']}期末数不一致，"
                          f"提示追溯调整/重述/合并范围变化，需核对附注"})

    # --- 8) 环比骤变 ---
    for k, v in (ring or {}).items():
        if v is None:
            continue
        if abs(v) > RING_CHANGE_LIMIT:
            A.append({"类别": "环比骤变", "项目": k, "数值": round(v, 4), "等级": "预警", "权重": 6,
                      "说明": f"环比变动超{RING_CHANGE_LIMIT:.0%}，注意季节性、单季确认集中或口径变化"})

    # --- 9) 趋势高压线 ---
    if ind.get("营业收入增长率") is not None and ind["营业收入增长率"] < -0.5:
        A.append({"类别": "趋势高压线", "项目": "营收同比下降>50%",
                  "数值": round(ind["营业收入增长率"], 4),
                  "等级": "高风险", "权重": 10, "说明": "营收同比下降超50%，判定为高风险异常"})
    if ind.get("净利润增长率") is not None and ind["净利润增长率"] < -0.5:
        A.append({"类别": "趋势高压线", "项目": "净利润同比下降>50%",
                  "数值": round(ind["净利润增长率"], 4),
                  "等级": "高风险", "权重": 10, "说明": "净利润同比下降超50%，判定为高风险异常"})

    return A


def compute_ring(cur_d, prior_d):
    ring = {}
    if not prior_d:
        return ring
    for std, label in [("营业收入_本期", "营业收入环比"), ("净利润_本期", "净利润环比")]:
        a = cur_d.get("利润表", {}).get(std)
        b = prior_d.get("利润表", {}).get(std)
        if a is not None and b:
            ring[label] = a / b - 1
    return ring
