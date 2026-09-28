# -*- coding: utf-8 -*-
"""Step2：科目映射与标准化。
1) 原始科目 → 标准科目（别名表）
2) 单位统一为元
3) 识别报告期（年报/半年报/一季报/三季报）与年份
4) 资产负债表：本期金额=期末、上期金额=期初；利润/现金流表：本期金额=本期、上期金额=上期
5) 跨报告拼接：用上一年报/上一期报告补齐 _上年初（3期数据，供周转率同比）与口径衔接校验
输出：02_标准化数据.csv（写入该报告自己的输出文件夹）；
并提供 assemble() 供主流程拿到数据字典。"""
import re
import pandas as pd
from config import MAPPING_CSV

UNIT_MULT = {"元": 1.0, "千元": 1e3, "万元": 1e4, "百万元": 1e6, "亿元": 1e8}

PERIOD_PATTERNS = [
    (re.compile(r"第[一1]季度|一季报|1季度"), "一季报"),
    (re.compile(r"半年度|中期|中报"), "半年报"),
    (re.compile(r"第[三3]季度|三季报|3季度"), "三季报"),
    (re.compile(r"第[四4]季度|四季报"), "四季报"),
    (re.compile(r"年度|年报"), "年报"),
]
PERIOD_ORDER = {"一季报": 1, "半年报": 2, "三季报": 3, "四季报": 4, "年报": 4}

PREFIX_RE = re.compile(r"^(?:[一二三四五六七八九十]+、|（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)"
                       r"|\d+[.．、]|（\d+）|\(\d+\)|其中[:：]|减[:：]|加[:：])")

TARGET_STMTS = ("合并资产负债表", "合并利润表", "合并现金流量表")

STMT_CANON = {
    "合并资产负债表": "资产负债表",
    "合并利润表": "利润表",
    "合并现金流量表": "现金流量表",
}

STD_COLS = ["文件名", "公司名称", "年份", "报告期", "期序", "报表", "标准科目",
            "原始科目", "本期值_元", "上期值_元", "原单位", "数据位置"]


def parse_period(filename: str):
    """从文件名解析 (年份, 报告期)"""
    year_m = re.search(r"(20\d{2})", filename)
    year = int(year_m.group(1)) if year_m else None
    period = "年报"
    for pat, name in PERIOD_PATTERNS:
        if pat.search(filename):
            period = name
            break
    return year, period


def normalize_item(name: str) -> str:
    """去掉报表常见的编号前缀，便于别名匹配"""
    s = str(name).strip().replace(" ", "")
    for _ in range(3):
        m = PREFIX_RE.match(s)
        if not m:
            break
        s = s[m.end():].strip()
    return s


def load_alias_map():
    """读取科目别名表（标准科目,报表,别名1|别名2|...）。
    使用csv模块逐行解析，容忍别名中误写英文逗号导致的额外列。"""
    alias2std = {}
    if not MAPPING_CSV.exists():
        raise SystemExit(f"找不到映射表：{MAPPING_CSV}")
    import csv as _csv
    with open(MAPPING_CSV, encoding="utf-8-sig") as f:
        reader = _csv.reader(f)
        next(reader, None)
        for lineno, row in enumerate(reader, start=2):
            if not row or not any(c.strip() for c in row):
                continue
            if len(row) < 3:
                print(f"[warn] 映射表第{lineno}行列数不足({len(row)}列)，已跳过：{row}")
                continue
            std, stmt = row[0].strip(), row[1].strip()
            aliases = ",".join(c.strip() for c in row[2:])
            for a in aliases.split("|"):
                a = a.strip()
                if a:
                    alias2std[(stmt, a)] = std
    return alias2std


def run(raw_df: pd.DataFrame, log, paths) -> pd.DataFrame:
    """标准化单份报告的原始数据，CSV写入 paths.STD_CSV"""
    alias2std = load_alias_map()
    out = []
    for _, r in raw_df.iterrows():
        stmt_raw = str(r["报表"]).strip()
        if stmt_raw not in TARGET_STMTS:
            continue
        stmt = STMT_CANON.get(stmt_raw, stmt_raw)
        raw_item = normalize_item(r["项目"])
        std = alias2std.get((stmt, raw_item))
        if std is None:
            continue
        unit = str(r.get("单位", "元") or "元")
        mult = UNIT_MULT.get(unit, 1.0)
        cur = pd.to_numeric(r.get("本期金额"), errors="coerce")
        pre = pd.to_numeric(r.get("上期金额"), errors="coerce")
        year, period = parse_period(str(r["文件名"]))
        out.append({
            "文件名": r["文件名"], "公司名称": r["公司名称"],
            "年份": year, "报告期": period, "期序": PERIOD_ORDER.get(period, 4),
            "报表": stmt, "标准科目": std, "原始科目": str(r["项目"]).strip(),
            "本期值_元": cur * mult if pd.notna(cur) else None,
            "上期值_元": pre * mult if pd.notna(pre) else None,
            "原单位": unit, "数据位置": r.get("数据位置", ""),
        })
    df = pd.DataFrame(out, columns=STD_COLS)
    df.to_csv(paths.STD_CSV, index=False, encoding="utf-8-sig")
    if df.empty:
        log(f"[step2] ⚠️ {paths.report_name} 标准化 0 行："
            f"请检查 01_原始提取.csv 的『报表/项目』列与映射表是否匹配")
    else:
        log(f"[step2] {paths.report_name}：标准化 {len(df)} 行 → {paths.STD_CSV.name}")
    return df


# ---------- 组装数据字典 ----------
def assemble(std_df: pd.DataFrame):
    """返回 {公司: {文件名: {'year','period','d':三表字典,'evid':证据,'ring_prior':上一期文件名}}}
    以及跨报告衔接差异列表 continuity"""
    if std_df is None or std_df.empty:
        return {}, []
    companies = {}
    for (comp, fname), g in std_df.groupby(["公司名称", "文件名"]):
        year, period = parse_period(fname)
        d = {"资产负债表": {}, "利润表": {}, "现金流量表": {}}
        evid = {}
        for _, r in g.iterrows():
            stmt, std = r["报表"], r["标准科目"]
            pos = r["数据位置"]
            if stmt == "资产负债表":
                if pd.notna(r["本期值_元"]):
                    d[stmt][f"{std}_期末"] = float(r["本期值_元"])
                    evid[f"{std}_期末"] = pos
                if pd.notna(r["上期值_元"]):
                    d[stmt][f"{std}_期初"] = float(r["上期值_元"])
                    evid[f"{std}_期初"] = pos
            elif stmt == "利润表":
                if pd.notna(r["本期值_元"]):
                    d[stmt][f"{std}_本期"] = float(r["本期值_元"])
                    evid[f"{std}_本期"] = pos
                if pd.notna(r["上期值_元"]):
                    d[stmt][f"{std}_上期"] = float(r["上期值_元"])
                    evid[f"{std}_上期"] = pos
            else:  # 现金流量表
                if pd.notna(r["本期值_元"]):
                    d[stmt][std] = float(r["本期值_元"])
                    evid[std] = pos
        companies.setdefault(comp, {})[fname] = {
            "year": year, "period": period, "d": d, "evid": evid, "ring_prior": None}

    continuity = []
    for comp, reports in companies.items():
        order = sorted(reports.items(),
                       key=lambda kv: (kv[1]["year"] or 0, PERIOD_ORDER.get(kv[1]["period"], 4)))
        for i in range(1, len(order)):
            order[i][1]["ring_prior"] = order[i - 1][0]
        for i in range(1, len(order)):
            prev_f, prev = order[i - 1]
            cur_f, cur = order[i]
            dp, dc = prev["d"], cur["d"]
            # 用上一报告资产负债表的期末值补 _上年初（3期数据）
            for k, v in dp["资产负债表"].items():
                if k.endswith("_期初"):
                    std_key = k[:-3] + "_上年初"
                    if std_key not in dc["资产负债表"]:
                        dc["资产负债表"][std_key] = v
            # 期初/期末一致性校验
            for key, base in [("现金及现金等价物_期末", "现金及现金等价物_期初"),
                              ("所有者权益_期末", "所有者权益_期初")]:
                a = dp["现金流量表"].get(key) or dp["资产负债表"].get(key)
                b = dc["现金流量表"].get(base) or dc["资产负债表"].get(base)
                if a and b and abs(a - b) / abs(a) > 0.005:
                    continuity.append({
                        "公司": comp, "当前报告": cur_f, "上一报告": prev_f,
                        "科目": base, "上期期末": a, "本期期初": b,
                        "差异%": f"{abs(a - b) / abs(a) * 100:.2f}%",
                        "说明": "跨报告期初/期末不一致，可能存在追溯调整、重述或口径变化"})
    return companies, continuity


def extract_nonrec(raw_df: pd.DataFrame):
    """从原始提取中抓取非经常性损益相关科目（通常在附注/利润表补充资料）。
    跳过"合计"行，避免 step4 求和时与明细重复计数。"""
    rows = []
    for _, r in raw_df.iterrows():
        item = str(r["项目"])
        if "非经常性损益" in item or "政府补助" in item:
            if "合计" in item:          # 合计行与明细行重复，跳过
                continue
            cur = pd.to_numeric(r.get("本期金额"), errors="coerce")
            rows.append({"文件名": r["文件名"], "公司名称": r["公司名称"],
                         "项目": item.strip(), "本期金额": cur,
                         "单位": r.get("单位", "元"), "数据位置": r.get("数据位置", "")})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import config
    from pathlib import Path
    raw = pd.read_csv(Path("output") / "raw_tmp.csv", dtype=str)
    run(raw, print, config.make_report_paths("tmp"))
