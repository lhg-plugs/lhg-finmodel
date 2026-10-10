<!-- About 简介（推送后填写到仓库 About 栏）：
财务建模专家：假设→三表搭建→勾稽校验→敏感性分析 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-finmodel
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, financial-modeling, dcf, valuation -->

# lhg-finmodel：财务建模专家，假设到敏感性分析一条龙

> **一句话介绍**：给 AI 编程助手装上"财务建模专家"——业务假设输入 → 三表搭建（利润表/资产负债表/现金流量表）→ 勾稽校验 → 敏感性分析；**确定性脚本做资产=负债+权益等硬校验，三表不平不许交付**。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-finmodel
> /plugin install lhg-finmodel@lhg-plugs
> ```

## 它是什么

`lhg-finmodel` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **4 个命令**（小白入口）：`finmodel` 建模一条龙，`finmodel-assumption` 假设清单收集，`finmodel-audit` 勾稽校验，`finmodel-scenario` 敏感性分析
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：假设清单化、三表搭建、勾稽校验、敏感性分析
- **2 个专家 agent**：建模专家、勾稽审计专家
- **1 个自动校验 hook**：模型文件改动后自动跑勾稽审计，结果注入提醒（可一键关闭）
- **7 条确定性审计规则**：纯 Python 标准库、零第三方依赖，三条勾稽硬关系 + 假设缺失检查 + 完整性提醒

## 信任机制：三表不平，不许交付

这是本插件与"直接让 AI 建模型"最大的区别：

1. **假设先行**：`assumptions.csv` 定稿前不搭三表；每个假设标注来源（用户给定/公开信息/估计）。
2. **勾稽硬校验**：资产=负债+权益、留存收益滚动、现金流勾稽三条关系每年必验，审计脚本报 blocker 就必须修。
3. **改后自动验**：hook 在模型文件改动后自动跑审计，blocker 未清零会明确提醒。
4. **敏感性标配**：交付必须带 ±20% 敏感性分析，结论只谈"哪个假设最敏感"，不推导买卖。

## 4 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-finmodel:finmodel` | 假设→三表→勾稽→敏感性一条龙 | `/lhg-finmodel:finmodel "某奶茶店，月营收50万，毛利率60%"` |
| `/lhg-finmodel:finmodel-assumption` | 业务描述翻译成假设清单 | `/lhg-finmodel:finmodel-assumption "年营收600万的小工厂"` |
| `/lhg-finmodel:finmodel-audit` | 勾稽校验：三条硬关系逐项过 | `/lhg-finmodel:finmodel-audit ./model` |
| `/lhg-finmodel:finmodel-scenario` | 关键假设 ±20% 敏感性分析 | `/lhg-finmodel:finmodel-scenario ./model` |

## 目录结构

```
lhg-finmodel/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 4 个命令：finmodel / finmodel-assumption / finmodel-audit / finmodel-scenario
├── skills/                  # 4 个平台中立 skill（假设/三表/勾稽/敏感性）
├── agents/                  # 2 个专家 agent（modeler / checker）
├── hooks/                   # 模型改动后自动勾稽校验 hook（fail-open，可一键关闭）
├── scripts/audit/           # 确定性审计：reconcile_audit.py（零第三方依赖）
├── fixtures/                # 好/坏对照用例
├── smoke_test.py            # 冒烟测试
├── ATTRIBUTION.md           # 灵感来源声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**Q：我是财务小白，能用它做公司的财务预测吗？**
A：能，这正是它的目标用户。按 `finmodel` 一条龙走：先回答 3 个问题定范围，再填假设表，剩下的按流程来。勾稽校验会替你把关"表平不平"。

**Q：它能替代投行/财务顾问的专业模型吗？**
A：不能。本插件做的是"小白能用的规范三表+敏感性分析"，保证方法正确、勾稽自洽；复杂交易结构（并购对价、股权激励、可转债）超出范围，请找专业人士。

**Q：模型结果能作为投资依据吗？**
A：不能。模型是决策辅助工具：假设变了结论就变。交付物自带局限性声明和敏感性分析，结论只谈敏感度，不谈买卖。

**Q：一定要用 Claude Code 吗？**
A：`skills/` 下的方法论是平台中立的纯 Markdown，可直接搬到豆包、Workbuddy 等 agent 平台用。只有 commands/agents/hooks 需要 Claude Code。

**Q：hook 每次改文件都跑校验，会不会很烦？**
A：校验是秒级的（纯 CSV 解析）。如果确实不需要，`export LHG_FINMODEL_AUTOCHECK_OFF=1` 关闭；交付前用 `finmodel-audit` 手动跑一次也行。

**Q：和 Excel 里手搭模型有什么区别？**
A：区别在"纪律"：假设清单化（每个数字有来源）、勾稽硬校验（三表不平不许交付）、敏感性标配（±20% 必做）。手搭模型最容易犯的三个错——现金手拍、分红记两次、营运资本符号反——审计脚本全覆盖。

## 自迭代

- 每个 skill 末尾有「自检与反馈」节：质检门 + 标准冒烟用例 + 一键提 issue。
- 发现规则误报/漏报、方法论不合理：到本仓库提 issue（标题带对应 skill 前缀，如 `[lhg-fm-reconcile]`），附模型特征与期望行为。

## 出品：刘洪光

刘洪光（https://github.com/lhg-skills）出品，lhg-plugs「小白专家插件」系列之一。
灵感来源见 [ATTRIBUTION.md](./ATTRIBUTION.md)（借鉴思路，实现与文案均为原创）。

---
*局限性声明：本插件保证建模方法正确、勾稽关系成立，不保证预测准确；模型结论不构成投资建议。*
