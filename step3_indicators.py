# -*- coding: utf-8 -*-
"""Step3：财务指标计算 + 勾稽校验。
勾稽校验全量输出（通过+不通过），字段：勾稽项名称/理论计算值/报表实际值/
差异率/勾稽校验结论/等级/权重/风险说明。
约定：理论计算值 = 由账面科目推算出的应有值；报表实际值 = 报表实际列示的数值。
含 THRESHOLDS 阈值表与 IND_CLASS 指标分类表。"""
from config import TOLERANCE_GOV_BOND


def g(d, stmt, key, default=None):
    return d.get(stmt, {}).get(key, default)


# ---------------- 指标分类（结构化文件用） ----------------
IND_CLASS = {
    "流动比率": "偿债能力", "现金流量比率": "偿债能力",
    "资产负债率": "偿债能力", "产权比率": "偿债能力",
    "应收账款周转率同比": "营运能力", "存货周转率同比": "营运能力",
    "总资产周转率同比": "营运能力",
    "毛利率": "盈利能力", "毛利率同比pp": "盈利能力",
    "营业利润率同比pp": "盈利能力",
    "净利率同比pp": "盈利能力", "ROE": "盈利能力",
    "营业现金比率": "现金流质量",
    "营业收入增长率": "成长能力", "净利润增长率": "成长能力",
    "资本积累率": "成长能力",
}

# ---------------- 阈值表（判定与理由的单一来源） ----------------
# (显示名, ind键, warn, abn, extreme, higher_better, 权重, 判定理由说明)
THRESHOLDS = [
    ("流动比率", "流动比率", 1.5, 1.0, 0.5, True, 5, "低于1.5预警，低于1异常，低于0.5极度异常"),
    ("资产负债率", "资产负债率", 0.60, 0.70, 0.80, False, 10, "高于60%预警，70%异常，80%极度异常"),
    ("现金流量比率", "现金流量比率", 0.8, 0.5, 0.0, True, 8, "低于0.8预警，0.5异常，低于0极度异常"),
    ("产权比率", "产权比率", 1.0, 2.0, 3.0, False, 7, "高于100%预警，200%异常，300%极度异常"),
    ("应收账款周转率", "应收账款周转率同比", -0.20, -0.30, -0.50, True, 8, "同比下降20%预警，30%异常，50%极度异常"),
    ("存货周转率", "存货周转率同比", -0.20, -0.30, -0.50, True, 7, "同比下降20%预警，30%异常，50%极度异常"),
    ("总资产周转率", "总资产周转率同比", -0.15, -0.25, -0.40, True, 5, "同比下降15%预警，25%异常，40%极度异常"),
    ("毛利率", "毛利率同比pp", -3, -5, -10, True, 5, "同比下降3pp预警，5pp异常，10pp极度异常"),
    ("营业利润率", "营业利润率同比pp", -2, -3, -5, True, 5, "同比下降2pp预警，3pp异常，5pp极度异常"),
    ("净利率", "净利率同比pp", -1.5, -3, -5, True, 8, "同比下降1.5pp预警，3pp异常，5pp极度异常"),
    ("ROE", "ROE", TOLERANCE_GOV_BOND, 0.0, -0.10, True, 10, "低于国债收益率预警，低于0异常，低于-10%极度异常"),
    ("营业现金比率", "营业现金比率", 0.80, 0.50, 0.0, True, 7, "低于80%预警，50%异常，低于0极度异常"),
    ("营业收入增长率", "营业收入增长率", 0.10, 0.0, -0.10, True, 5, "低于10%预警，低于0异常"),
    ("净利润增长率", "净利润增长率", 0.10, 0.0, -0.10, True, 6, "低于10%预警，低于0异常"),
    ("资本积累率", "资本积累率", 0.05, 0.0, -0.10, True, 4, "低于5%预警，低于0异常"),
]

SEVERITY_RANK = {"无": 0, "预警": 1, "异常": 2, "极度异常": 3}


def compute_indicators(d):
    ind = {}
    if g(d, "资产负债表", "流动负债_期末"):
        if g(d, "资产负债表", "流动资产_期末") is not None:
            ind["流动比率"] = g(d, "资产负债表", "流动资产_期末") / g(d, "资产负债表", "流动负债_期末")
        ind["现金流量比率"] = g(d, "现金流量表", "经营活动现金净流量", 0) / g(d, "资产负债表", "流动负债_期末")
    if g(d, "资产负债表", "总资产_期末"):
        if g(d, "资产负债表", "总负债_期末") is not None:
            ind["资产负债率"] = g(d, "资产负债表", "总负债_期末") / g(d, "资产负债表", "总资产_期末")
            if g(d, "资产负债表", "所有者权益_期末"):
                ind["产权比率"] = g(d, "资产负债表", "总负债_期末") / g(d, "资产负债表", "所有者权益_期末")

    # 三大周转率同比（需3期数据：期末/期初/上年初）
    for name, item, denom_key in [
        ("应收账款周转率同比", "应收账款", "营业收入"),
        ("存货周转率同比", "存货", "营业成本"),
        ("总资产周转率同比", "总资产", "营业收入")]:
        cur = g(d, "利润表", f"{denom_key}_本期"); pre = g(d, "利润表", f"{denom_key}_上期")
        e0 = g(d, "资产负债表", f"{item}_期末"); e1 = g(d, "资产负债表", f"{item}_期初")
        e2 = g(d, "资产负债表", f"{item}_上年初")
        if None not in (cur, pre, e0, e1, e2) and e1 and e2:
            cur_t = cur / ((e0 + e1) / 2); pre_t = pre / ((e1 + e2) / 2)
            if pre_t:
                ind[name] = cur_t / pre_t - 1
                if name == "总资产周转率同比":
                    ind["_总资产周转率"] = cur_t

    # 盈利/成长类同比
    rev, rev_p = g(d, "利润表", "营业收入_本期"), g(d, "利润表", "营业收入_上期")
    if rev and rev_p:
        cost, cost_p = g(d, "利润表", "营业成本_本期"), g(d, "利润表", "营业成本_上期")
        if None not in (cost, cost_p):
            ind["毛利率"] = (rev - cost) / rev
            ind["毛利率同比pp"] = ((rev - cost) / rev - (rev_p - cost_p) / rev_p) * 100
        op, op_p = g(d, "利润表", "营业利润_本期"), g(d, "利润表", "营业利润_上期")
        if None not in (op, op_p):
            ind["营业利润率同比pp"] = (op / rev - op_p / rev_p) * 100
        ni, ni_p = g(d, "利润表", "净利润_本期"), g(d, "利润表", "净利润_上期")
        if None not in (ni, ni_p):
            ind["净利率同比pp"] = (ni / rev - ni_p / rev_p) * 100
            ind["营业收入增长率"] = rev / rev_p - 1
            ind["净利润增长率"] = ni / ni_p - 1

    # 内部变量（供 step4 净现比检查用）——不依赖上期是否有净利润
    if rev:
        ind["_营业收入_本期"] = rev
        ni = g(d, "利润表", "净利润_本期")
        if ni is not None:
            ind["_净利润_本期"] = ni
        ocf = g(d, "现金流量表", "经营活动现金净流量")
        if ocf is not None:
            ind["_经营现金流_本期"] = ocf

    # ROE / 营业现金比率 / 资本积累率
    ni = g(d, "利润表", "净利润_本期")
    e_e = g(d, "资产负债表", "所有者权益_期末")
    e_b = g(d, "资产负债表", "所有者权益_期初")
    if None not in (ni, e_e, e_b) and (e_e + e_b):
        ind["ROE"] = ni / ((e_e + e_b) / 2)
    if rev and g(d, "现金流量表", "经营活动现金净流量") is not None:
        ind["营业现金比率"] = g(d, "现金流量表", "经营活动现金净流量") / rev
    if None not in (e_e, e_b) and e_b:
        ind["资本积累率"] = (e_e - e_b) / e_b
    return ind


def _band(v, warn, abn, extreme, hb=True):
    """hb=True: 越低越坏；hb=False: 越高越坏"""
    if hb:
        if v >= warn: return None
        if v >= abn:  return ("预警", v)
        if v >= extreme: return ("异常", v)
        return ("极度异常", v)
    else:
        if v <= warn: return None
        if v <= abn:  return ("预警", v)
        if v <= extreme: return ("异常", v)
        return ("极度异常", v)


def check_indicators(ind):
    R = []
    for disp, key, warn, abn, extreme, hb, w, desc in THRESHOLDS:
        if key not in ind:
            continue
        res = _band(ind[key], warn, abn, extreme, hb)
        if res:
            R.append({"指标": disp, "数值": res[1], "等级": res[0], "权重": w, "说明": desc})
    # 特判：流动比率>5 资金闲置
    if "流动比率" in ind and ind["流动比率"] > 5:
        R.append({"指标": "流动比率", "数值": ind["流动比率"], "等级": "极度异常",
                  "权重": 5, "说明": "流动比率>5，资金闲置或异常"})
    return R


def check_gouji(d, ind):
    """勾稽校验——全量输出（通过+不通过）。
    字段：勾稽项名称/理论计算值/报表实际值/差异率/勾稽校验结论/等级/权重/风险说明
    数据缺失的勾稽项不进表。"""
    R = []
    rev = g(d, "利润表", "营业收入_本期")
    ni  = g(d, "利润表", "净利润_本期")

    def add(no, name, calc, base, tol, level, w, desc):
        if calc is None or base is None or base == 0:
            return
        diff = abs(calc - base) / abs(base)
        passed = diff <= tol
        R.append({
            "勾稽项名称": f"{no}.{name}",
            "理论计算值": round(calc, 2),
            "报表实际值": round(base, 2),
            "差异率": f"{diff * 100:.4f}%",
            "勾稽校验结论": "通过" if passed else "不通过",
            "等级": "通过" if passed else level,
            "权重": 0 if passed else w,
            "风险说明": "差异在容差范围内" if passed else desc,
        })

    # 1 资产负债表平衡
    a = g(d, "资产负债表", "总资产_期末")
    l = g(d, "资产负债表", "总负债_期末")
    e = g(d, "资产负债表", "所有者权益_期末")
    if None not in (a, l, e):
        add(1, "资产负债表平衡", l + e, a, 0.0001, "极高", 10, "会计恒等式不成立")

    # 2 营业利润勾稽
    k2 = ["营业收入_本期", "营业成本_本期", "税金及附加", "销售费用",
          "管理费用", "研发费用", "财务费用", "营业利润_本期"]
    v2 = [g(d, "利润表", k) for k in k2]
    if all(v is not None for v in v2):
        add(2, "营业利润勾稽", v2[0] - sum(v2[1:7]), v2[7],
            0.005, "高", 8, "可能存在利润操纵或科目分类错误")

    # 3 净利润勾稽
    tp = g(d, "利润表", "利润总额_本期")
    tax = g(d, "利润表", "所得税费用_本期")
    if None not in (ni, tp, tax):
        add(3, "净利润勾稽", tp - tax, ni, 0.001, "高", 8, "所得税或利润总额错误")

    # 4 现金净增加勾稽
    ce = g(d, "现金流量表", "现金及现金等价物_期末")
    cb = g(d, "现金流量表", "现金及现金等价物_期初")
    cn = g(d, "现金流量表", "现金及现金等价物净增加额")
    if None not in (ce, cb, cn):
        add(4, "现金净增加勾稽", ce - cb, cn, 0.001, "高", 8, "三大活动分类错误")

    # 5 未分配利润勾稽
    # 容差1%：现金流量表"分配股利、利润或偿付利息支付的现金"含利息支付，
    # 与纯分红口径存在结构性差异，0.5%容差会误报
    re_e = g(d, "资产负债表", "未分配利润_期末")
    re_b = g(d, "资产负债表", "未分配利润_期初")
    div = g(d, "现金流量表", "现金分红")
    if None not in (re_e, re_b, div, ni):
        add(5, "未分配利润勾稽", re_b + ni - div, re_e,
            0.01, "高", 8, "利润分配未入账、含利息支付口径差异或差错更正")

    # 7 营收现金含量：理论值=营业收入；实际值=销售收现（含增值税，容差18%）
    scash = g(d, "现金流量表", "销售商品提供劳务收到的现金")
    if scash is not None and rev:
        add(7, "营收现金含量", rev, scash, 0.18, "高", 8, "可能存在虚增收入或提前确认收入")

    # 8 成本现金支付：理论值=营业成本；实际值=购买商品付现
    # 容差25%：重资产行业折旧摊销、人工等非采购付现项目占比高，属正常口径差
    pcash = g(d, "现金流量表", "购买商品接受劳务支付的现金")
    cost = g(d, "利润表", "营业成本_本期")
    if pcash is not None and cost:
        add(8, "成本现金支付", cost, pcash, 0.25, "中", 6, "需核查存货变动及应付账款变化")

    # 11 连续期勾稽（本期期初 vs 上一报告期末，多报告模式由 step2 补 _上年初）
    re_b_prev = g(d, "资产负债表", "未分配利润_上年初")
    if re_b is not None and re_b_prev is not None:
        diff = abs(re_b - re_b_prev) / abs(re_b_prev) if re_b_prev else 0
        passed = diff <= 0.005
        R.append({
            "勾稽项名称": "11.连续期勾稽",
            "理论计算值": round(re_b_prev, 2),
            "报表实际值": round(re_b, 2),
            "差异率": f"{diff * 100:.4f}%",
            "勾稽校验结论": "通过" if passed else "不通过",
            "等级": "通过" if passed else "极高",
            "权重": 0 if passed else 10,
            "风险说明": "期初与上期期末衔接一致" if passed else "期初期末不一致，可能存在篡改、追溯调整未披露",
        })
    return R
