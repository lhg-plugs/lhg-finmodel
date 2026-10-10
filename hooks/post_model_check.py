#!/usr/bin/env python3
"""lhg-finmodel 硬门：模型文件改动后自动跑勾稽校验。

触发：PostToolUse / Edit|Write。当本次编辑的文件是模型目录
（含 assumptions.csv 或 statements*.csv 的目录）下的 .csv/.md 文件时，
自动运行 reconcile_audit.py，把校验结果以 additionalContext 注入，
提醒 agent 处理 blocker。

逃生方式（按推荐度排序）：
  1. LHG_FINMODEL_AUTOCHECK_OFF=1（环境变量，当前会话有效）。
  2. /plugin disable lhg-finmodel（整个插件停用，hooks 不再触发）。

设计原则：这是信息型 hook，不拦截工具调用；内部出错一律
fail-open（直接放行，不注入也不报错）；零第三方依赖。
"""

import json
import os
import subprocess
import sys

AUDIT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "scripts", "audit", "reconcile_audit.py")
MODEL_MARKERS = ("assumptions.csv",)
STATEMENTS_PREFIX = "statements"


def find_model_dir(file_path):
    """向上查找包含 assumptions.csv 的目录；找不到返回 None。"""
    d = os.path.dirname(os.path.abspath(file_path))
    for _ in range(6):
        if any(os.path.isfile(os.path.join(d, m)) for m in MODEL_MARKERS):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def main() -> int:
    if os.environ.get("LHG_FINMODEL_AUTOCHECK_OFF") == "1":
        return 0  # 逃生开关

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # 输入解析失败：fail-open

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""
    if not file_path:
        return 0
    base = os.path.basename(file_path)
    if not (base.endswith(".csv") or base.endswith(".md")):
        return 0  # 非模型文件：快速放行

    try:
        model_dir = find_model_dir(file_path)
        if not model_dir:
            return 0
        r = subprocess.run(
            [sys.executable, os.path.normpath(AUDIT_SCRIPT),
             "--target", model_dir, "--format", "text"],
            capture_output=True, text=True, timeout=60)
        text = (r.stdout or "").strip()
        if not text:
            return 0
        status = "blocker 未清零，请处理后再交付" if r.returncode == 2 else "校验通过"
        msg = ("自动勾稽校验（lhg-finmodel）：%s\n目录：%s\n%s\n"
               "关闭自动校验：export LHG_FINMODEL_AUTOCHECK_OFF=1。"
               % (status, model_dir, text))
        out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                      "additionalContext": msg}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception:
        return 0  # 任何内部错误：fail-open


if __name__ == "__main__":
    sys.exit(main())
