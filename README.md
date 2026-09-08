# Agent Skills

本仓库收录可直接放入 Agent 技能目录使用的技能（Skills）。每个技能自成一个顶层文件夹，内含 `SKILL.md` 主文件、脚本与资产。

## 技能列表

| 文件夹 | 技能 | 用途 |
| --- | --- | --- |
| [`Tong Zhihui Academic Writing Skill/`](Tong%20Zhihui%20Academic%20Writing%20Skill/) | 仝志辉·乡村治理学术论文写作法 | 以人物方法论为核心的学术论文写作技能，覆盖选题、概念建构、材料处理与论证组织 |
| [`Literature Snowball Skill/`](Literature%20Snowball%20Skill/) | 文献检索拓展（引文滚雪球） | 论文写作初期用一组起点文献滚雪球，逐轮拓展可检索线索，收束时用引用网络重排文献地位并生成研究提炼文档 |

## 安装

各技能遵循通用的 Agent Skill 约定（YAML frontmatter + Markdown 正文 + 可选脚本与资产）。把对应文件夹整体复制到你的技能目录即可：

- WorkBuddy：`~/.workbuddy/skills/`
- Claude Code / CodeBuddy 类工具：`~/.claude/skills/` 或 `~/.codebuddy/skills/`
- 其他支持 Skill 约定的 Agent：放至其约定的技能目录

具体依赖与用法见各技能文件夹内的 `README.md`。

## 许可

各技能采用 MIT License，详见对应文件夹内的 `LICENSE`。
