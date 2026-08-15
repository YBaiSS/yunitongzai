# 仝志辉·乡村治理学术论文写作法 (Tong Zhihui Academic Writing Skill)

A reusable, executable writing-methodology skill that distills the academic-paper
craft of **Professor Tong Zhihui (仝志辉)** — a leading Chinese scholar of rural
governance at Renmin University of China — into a structured workflow for writing
papers in rural governance, agriculture–rural–farmers (三农), and political
sociology.

> **Disclaimer:** This skill is an AI perspective derived from Professor Tong
> Zhihui's public works and documented thinking patterns. It does **not** represent
> his actual views, and he is not affiliated with this repository. Tong Zhihui is a
> real public figure; this project is an independent, non-endorsed reconstruction
> for research and educational use.

## English Description (recommended for the GitHub "About" field)

This skill distills the academic paper writing methodology of Professor Tong Zhihui (仝志辉), a leading Chinese scholar of rural governance at Renmin University of China, into a reusable, executable workflow for producing high-quality papers in the fields of rural governance, agriculture, rural areas and farmers (三农), and political sociology.

At its core, the skill teaches a six-step writing method: (1) problem discovery through "policy problematization"—turning repeatedly-deployed yet underperforming policies into objective academic questions; (2) concept construction first, where every study must advance a core concept or proposition (e.g., "de-departmentalization," "village community," "social connectedness"); (3) a four-actor analytical framework—state, government departments, local government, and farmers—whose relationships matter more than the actors themselves; (4) three canonical argument structures for policy diagnosis, theory-borrowing case analysis, and academic dispute response; (5) thick description of anonymized yet data-rich village cases; and (6) standardized output norms for titles, abstracts, and footnotes.

The skill encodes Tong's distinctive intellectual stance: centering farmer subjectivity, farmer organization, and the village community, while critically interrogating China's departmental governance structure. It preserves his signature moves—defining concepts before deployment, using concession-plus-elevation rhetoric, and reframing rather than rejecting mainstream narratives. A built-in "anti-AI" self-check guards against mechanical phrasing, and an expression-layer module switches between academic and natural written registers. For interview-based reports, it enforces empirical discipline: explicit source attribution, removal of bracketed asides, and verification of speaker identity. Papers are evaluated against four criteria—concept validity, mechanism disclosure, explanatory increment, and the farmer-subjectivity stance. It covers the full range of paper types Tong pioneered: policy-diagnosis essays, theory-borrowing case studies, academic dispute responses, historical case research, and single-village thick descriptions. Built from 48 first-hand papers, it is a practical companion for researchers and graduate students writing within the Chinese rural studies tradition, activated as a first-person "author" persona with an AI-perspective disclaimer.

## 中文简介

本 skill 将仝志辉的学术论文写作方法，封装为一套可执行的流程，用于撰写乡村治理、
三农与政治社会学领域的学术论文。核心包括：

- **六步写作法**：选题入口 → 概念建构 → 四方主体框架 → 论证骨架 → 案例深描 → 规范输出
- **四方主体分析框架**：国家—部门—地方政府—农户
- **表达层规则**：思维层/表达层分离、语体开关、反 AI 味自检清单、访谈报告实证纪律
- **人格层**：以"笔者"视角回应的首人称 persona，以及永久禁用"不是……而是……"对举句式

## 仓库结构

```
tongzhihui-skill/
├── SKILL.md            # 合并后的完整 skill（默认入口）
├── work_skill.md       # 源·工作能力（PART A）
├── persona_skill.md    # 源·人物性格（PART B）
├── manifest.json       # 打包清单 / 引擎配置
├── meta.json           # 元数据（名称、标签、描述）
├── LICENSE
└── README.md
```

> 说明：`work_skill.md` / `persona_skill.md` 是 `manifest.json` 中声明的源文件
> （对应 entrypoints），`SKILL.md` 由 dot-skill 引擎将其合并压缩而成。修改请改两份
> 源文件，而非 `SKILL.md`。

## 使用方法

- **作为 dot-skill 元技能安装**：用 dot-skill 引擎从本仓库安装，会自动解析
  `manifest.json` 并生成 slash command（默认 `celebrity-tongzhihui-academic-writing`）。
- **手动放入 WorkBuddy**：将整个目录复制到 `~/.workbuddy/skills/tongzhihui-academic-writing/`
  即可在对话中调用。

## 数据来源与隐私

本 skill 的方法论从 48 篇公开/授权的一手论文（2016–2024）反推而来。原始复盘记录中
涉及的真实地名、企业名与受访人均已**匿名化**（如"某县""甲企业""受访者甲"），
仅保留可复用的写作方法论，不含可识别的私人信息。

## License

[MIT](./LICENSE) © 2026 <YOUR-NAME>
