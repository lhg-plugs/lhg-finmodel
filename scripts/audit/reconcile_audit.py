#!/usr/bin/env python3
"""lhg-finmodel 确定性勾稽审计：扫描目标目录下的 assumptions.csv / statements*.csv。

检查：
  FM-ASSUMP-001  必需假设缺失（blocker）
  FM-BS-001     总资产 != 总负债+股东权益（blocker）
  FM-RE-001     期末留存收益 != 期初留存收益+净利润-现金分红（blocker）
  FM-CF-001     现金净增加 != 经营+投资+筹资，或 != 期末现金-期初现金（blocker）
  FM-IS-001     毛利润与 收入×毛利率 偏差过大（warning）
  FM-SEN-001    缺少敏感性表（表=SEN）（warning）
  FM-DCF-001    缺少 DCF 估值表（表=DCF）（warning）

文件格式：
  assumptions.csv : 表头 假设,值,说明；值用小数（如 0.15）
  statements.csv  : 表头 表,项目,年,值；表 ∈ IS/BS/CF/DCF/SEN

用法：
    python3 reconcile_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning]

exit code：0=无命中（按 --fail-on 口径），2=有 blocker，1=仅 warning（且 --fail-on=warning）。
零第三方依赖。规则文案均为本项目原创。
"""

import argparse
import csv
import json
import os
import sys

VERSION = "1.0.0"
TOOL = "lhg-finmodel/reconcile-audit"
TOL = 0.001  # 相对容差 0.1%

REQUIRED_ASSUMPTIONS = ["revenue_growth", "gross_margin", "opex_rate",
                        "tax_rate", "capex_rate", "discount_rate"]


class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {"rule_id": self.rule_id, "severity": self.severity,
                "category": self.category, "title": self.title,
                "file": self.file, "line": self.line,
                "snippet": self.snippet, "detail": self.detail}


findings = []


def add(rule_id, severity, category, title, file, line=0, snippet="", detail=""):
    findings.append(Finding(rule_id, severity, category, title, file, line, snippet, detail))


def read_text(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def close(a, b):
    if a == 0 and b == 0:
        return True
    return abs(a - b) <= TOL * max(abs(a), abs(b), 1.0)


def parse_csv(path):
    return list(csv.DictReader(read_text(path).splitlines()))


# ---------------------------------------------------------------- 假设

def check_assumptions(path):
    rows = parse_csv(path)
    have = {}
    for r in rows:
        k = (r.get("假设") or "").strip()
        v = (r.get("值") or "").strip()
        if k:
            try:
                have[k] = float(v)
            except Exception:
                have[k] = None
    missing = [k for k in REQUIRED_ASSUMPTIONS if k not in have or have[k] is None]
    if missing:
        add("FM-ASSUMP-001", "blocker", "假设", "必需假设缺失",
            path, detail="缺少：%s；请回 finmodel-assumption 补齐" % "、".join(missing))
    return have


# ---------------------------------------------------------------- 三表

def build_index(rows):
    """(表, 项目, 年) -> 值。"""
    idx = {}
    for r in rows:
        t = (r.get("表") or "").strip()
        item = (r.get("项目") or "").strip()
        year = (r.get("年") or "").strip()
        try:
            v = float((r.get("值") or "").strip())
        except Exception:
            continue
        idx[(t, item, year)] = v
    return idx


def get(idx, t, item, year):
    return idx.get((t, item, year))


def check_statements(path, assumptions):
    rows = parse_csv(path)
    idx = build_index(rows)
    tables = {r.get("表", "").strip() for r in rows}
    years = sorted({y for (t, i, y) in idx.keys() if t in ("IS", "BS", "CF")})

    for y in years:
        # FM-BS-001：资产 = 负债 + 权益
        ta = get(idx, "BS", "总资产", y)
        tl = get(idx, "BS", "总负债", y)
        te = get(idx, "BS", "股东权益", y)
        if te is None:
            # 权益 = 股本 + 期末留存收益（+ 资本公积，如有）
            parts = [get(idx, "BS", n, y) for n in ("股本", "期末留存收益", "资本公积")]
            if parts[0] is not None and parts[1] is not None:
                te = parts[0] + parts[1] + (parts[2] or 0)
        if ta is not None and tl is not None and te is not None:
            if not close(ta, tl + te):
                add("FM-BS-001", "blocker", "勾稽", "资产≠负债+权益",
                    path, snippet="%s年" % y,
                    detail="%s年：总资产 %.2f ≠ 总负债 %.2f + 股东权益 %.2f（差 %.2f）；先查留存收益滚动，再查现金是否倒挤" % (
                        y, ta, tl, te, ta - tl - te))

        # FM-RE-001：期末留存 = 期初留存 + 净利润 − 分红
        re_end = get(idx, "BS", "期末留存收益", y)
        re_begin = get(idx, "BS", "期初留存收益", y)
        ni = get(idx, "IS", "净利润", y)
        div = get(idx, "BS", "现金分红", y)
        if div is None:
            div = get(idx, "IS", "现金分红", y) or 0
        if re_end is not None and re_begin is not None and ni is not None:
            expect = re_begin + ni - div
            if not close(re_end, expect):
                add("FM-RE-001", "blocker", "勾稽", "留存收益滚动不平",
                    path, snippet="%s年" % y,
                    detail="%s年：期末留存 %.2f ≠ 期初 %.2f + 净利润 %.2f − 分红 %.2f = %.2f；检查分红是否记了两次" % (
                        y, re_end, re_begin, ni, div, expect))

        # FM-CF-001：现金净增加 = 经营+投资+筹资；= 期末现金 − 期初现金
        ncf = get(idx, "CF", "现金净增加额", y)
        op = get(idx, "CF", "经营活动现金流", y)
        inv = get(idx, "CF", "投资活动现金流", y)
        fin = get(idx, "CF", "筹资活动现金流", y)
        cash_end = get(idx, "BS", "现金及等价物", y)
        cash_begin = get(idx, "BS", "期初现金", y)
        if ncf is not None and op is not None and inv is not None and fin is not None:
            if not close(ncf, op + inv + fin):
                add("FM-CF-001", "blocker", "勾稽", "现金净增加≠三项现金流之和",
                    path, snippet="%s年" % y,
                    detail="%s年：净增加 %.2f ≠ 经营 %.2f + 投资 %.2f + 筹资 %.2f；检查营运资本变动符号" % (
                        y, ncf, op, inv, fin))
        if ncf is not None and cash_end is not None and cash_begin is not None:
            if not close(ncf, cash_end - cash_begin):
                add("FM-CF-001", "blocker", "勾稽", "现金净增加≠期末−期初现金",
                    path, snippet="%s年" % y,
                    detail="%s年：净增加 %.2f ≠ 期末现金 %.2f − 期初现金 %.2f；现金应用倒挤法" % (
                        y, ncf, cash_end, cash_begin))

        # FM-IS-001：毛利润 vs 收入×毛利率（warning）
        rev = get(idx, "IS", "营业收入", y)
        gp = get(idx, "IS", "毛利润", y)
        gm = assumptions.get("gross_margin")
        if rev is not None and gp is not None and gm:
            expect = rev * gm
            if abs(gp - expect) > 0.01 * abs(expect):
                add("FM-IS-001", "warning", "复算", "毛利润与假设偏差过大",
                    path, snippet="%s年" % y,
                    detail="%s年：毛利润 %.2f vs 收入×毛利率 %.2f，偏差超 1%%；如为手工调整请标注" % (y, gp, expect))

    if not any(t == "SEN" for t in tables):
        add("FM-SEN-001", "warning", "完整性", "缺少敏感性表",
            path, detail="statements.csv 中无 表=SEN 的行；建议跑 finmodel-scenario 生成敏感性分析")
    if not any(t == "DCF" for t in tables):
        add("FM-DCF-001", "warning", "完整性", "缺少 DCF 估值表",
            path, detail="statements.csv 中无 表=DCF 的行；如需估值请补充")


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True)
    ap.add_argument("--format", default="json", choices=["json", "text"])
    ap.add_argument("--fail-on", default="blocker", choices=["blocker", "warning"])
    args = ap.parse_args()

    target = os.path.abspath(args.target)
    if os.path.isdir(target):
        files = [os.path.join(target, f) for f in sorted(os.listdir(target))]
    else:
        files = [target]

    assumptions = {}
    for p in files:
        base = os.path.basename(p)
        if not os.path.isfile(p):
            continue
        if base == "assumptions.csv":
            assumptions = check_assumptions(p)
        elif base.startswith("statements") and base.endswith(".csv"):
            check_statements(p, assumptions)

    n_blocker = sum(1 for f in findings if f.severity == "blocker")
    n_warning = sum(1 for f in findings if f.severity == "warning")
    summary = {"tool": TOOL, "version": VERSION, "target": target,
               "blocker": n_blocker, "warning": n_warning,
               "total": len(findings)}

    if args.format == "json":
        out = {"summary": summary,
               "findings": [f.to_dict() for f in findings]}
        sys.stdout.write(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        lines = ["[%s] %s blocker=%d warning=%d" % (TOOL, target, n_blocker, n_warning)]
        for f in findings:
            lines.append("%s %s %s:%s %s" % (f.severity.upper(), f.rule_id, f.file, f.line, f.title))
            if f.detail:
                lines.append("    " + f.detail)
        sys.stdout.write("\n".join(lines) + "\n")

    if n_blocker:
        return 2
    if n_warning and args.fail_on == "warning":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
