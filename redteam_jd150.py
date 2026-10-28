"""redteam_jd150 —— 把红队与内容安全工程师·模型热切换的一致性切成可核查的片段并标出关键位置。

把输入按语义边界切成独立单元，逐单元核对红队与内容安全工程师·模型热切换的一致性相关的特征并标出命中位置

定位：
  只做切分与定位，不做语义改写——判断依据全部落在可指认的位置上

岗位对应：
  目标岗位　MiniMax · 资深红队与内容安全工程师
  技能主线　安全对齐、LLM评测、Python
  领域标签　AI安全对齐

设计约束：
  1. **只报告能定位到具体位置的结论**，不做语义猜测。
  2. **规则表公开**，每条命中都能对应到岗位要求的一条明示规则。
  3. **输入为空或格式不对时明确报错**，不静默返回空结果。

仅依赖 Python 标准库。

用法:
    python redteam_jd150.py --help
    python redteam_jd150.py --file input.txt
    python redteam_jd150.py --text "示例内容"
    python redteam_jd150.py --file input.txt --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys

# 岗位规则表：每条规则独立可核查，命中即报，不做推断。
# 规则由岗位 JD 的技能线与领域标签派生——每条都能对回岗位要求。
# 目标岗位：MiniMax · 资深红队与内容安全工程师
RULES: list[dict] = [
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·缺失",
        "why": "岗位要求「安全对齐」在输入里找不到对应内容",
        "severity": "high",
        "keywords": ['missing', 'absent', '缺少', '没有', '未提供', '安全对齐'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·冲突",
        "why": "两处关于「LLM评测」的描述互相矛盾",
        "severity": "high",
        "keywords": ['conflict', 'contradict', '矛盾', '不一致', '相反', 'LLM评测'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·越界",
        "why": "「Python」的取值超出岗位场景的常规范围",
        "severity": "medium",
        "keywords": ['out of range', 'outlier', '越界', '超限', '超过', 'Python'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·退化",
        "why": "「AI安全对齐」相关的信息量不足以支撑判断",
        "severity": "medium",
        "keywords": ['degrade', 'insufficient', '不足', '太少', '无法', 'AI安全对齐'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·泄漏",
        "why": "「红队与内容安全工程师」相关的内容被意外暴露",
        "severity": "high",
        "keywords": ['leak', 'expose', '泄漏', '暴露', '明文', '红队与内容安全工程师'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·重复#2",
        "why": "同一处「安全对齐」信息被反复传递",
        "severity": "low",
        "keywords": ['duplicate', 'repeat', '重复', 'again', '安全对齐'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·陈旧#2",
        "why": "「LLM评测」的时效性已过期",
        "severity": "medium",
        "keywords": ['stale', 'expired', '过期', '陈旧', '旧版', 'LLM评测'],
    },
    {
        "name": "红队与内容安全工程师·模型热切换的一致性·不可核#2",
        "why": "关于「Python」的说法无法追溯到具体证据",
        "severity": "high",
        "keywords": ['unverifiable', 'no evidence', '无法追溯', '没有来源', 'Python'],
    },
]


def redteam_jd150_split_units(text: str) -> list[str]:
    """把输入切成语义单元：优先按行，其次按句。"""
    units: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = re.split(r"(?<=[。！？；;])\s*|(?<=[.!?])\s+(?=[A-Z一-鿿])", line)
        for p in parts:
            p = p.strip()
            if p:
                units.append(p)
    return units


def redteam_jd150_hit_any(text: str, keywords: list[str]) -> list[str]:
    """返回命中的关键词列表（去重、保序）。"""
    low = text.lower()
    out: list[str] = []
    for k in keywords:
        if k.lower() in low and k not in out:
            out.append(k)
    return out


def redteam_jd150_scan_units(text: str) -> list[dict]:
    """逐单元套规则，产出命中记录。"""
    units = redteam_jd150_split_units(text)
    findings: list[dict] = []
    for idx, unit in enumerate(units):
        for rule in RULES:
            hits = redteam_jd150_hit_any(unit, rule["keywords"])
            if hits:
                findings.append({
                    "unit_index": idx,
                    "text": unit,
                    "rule": rule["name"],
                    "why": rule["why"],
                    "severity": rule["severity"],
                    "hits": hits,
                })
    return findings


def redteam_jd150_analyze(text: str) -> dict:
    """主分析：返回单元数、命中与覆盖情况。"""
    units = redteam_jd150_split_units(text)
    findings = redteam_jd150_scan_units(text)
    by_rule: dict[str, int] = {}
    for f in findings:
        by_rule[f["rule"]] = by_rule.get(f["rule"], 0) + 1
    return {
        "unit_count": len(units),
        "findings": findings,
        "by_rule": by_rule,
        "unmatched": len(units) - len({f["unit_index"] for f in findings}),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def render(result: dict) -> str:
    """把结果渲染成人读的文本。每个工具的版式不同。"""
    out: list[str] = []
    if not result.get("ok", True):
        out.append(f"无法分析：{{result.get('error', '未知原因')}}")
        return "\n".join(out)
    out.append(f"单元数：{result['unit_count']}")
    out.append(f"命中 {result['hit_count'] if 'hit_count' in result else sum(result['by_rule'].values())} 处")
    out.append("")
    for rule in RULES:
        n = result["by_rule"].get(rule["name"], 0)
        if not n:
            continue
        out.append(f"[{rule['name']}] {n} 处  ({rule['severity']})")
        for f in result["findings"]:
            if f["rule"] == rule["name"]:
                out.append(f"  #{f['unit_index']}: {f['text'][:100]}")
        out.append("")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="redteam_jd150",
        description="把输入按语义边界切成独立单元，逐单元核对红队与内容安全工程师·模型热切换的一致性相关的特征并标出命中位置（仅依赖标准库）",
        epilog=(
            "示例:\n"
            "  python redteam_jd150.py --file input.txt\n"
            "  python redteam_jd150.py --text '示例内容'\n"
            "  python redteam_jd150.py --file input.txt --json\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", help="输入文件路径")
    src.add_argument("--text", help="直接给出输入内容")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            print(f"读不了文件：{{e}}", file=sys.stderr)
            return 2
    else:
        content = args.text

    if not content.strip():
        print("输入是空的。", file=sys.stderr)
        return 2

    result = redteam_jd150_analyze(content)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(render(result))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
