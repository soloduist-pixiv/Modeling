# Modeling Skills（工作区权威目录）

本目录是仓库内 **Skill 正文的权威位置**。Cursor 运行时还会从 `.cursor/skills/` 与 `~/.cursor/skills/` 加载同名包（内容应保持同步）。

| Skill | 目录 | 用途 |
|-------|------|------|
| **math-modeling** | [`math-modeling/`](math-modeling/) | 做题：自治建模 → 实验 → 红队 → 改稿 → 终稿包 |
| **math-paper-comprehend** | [`math-paper-comprehend/`](math-paper-comprehend/) | 读论文：每个模型/检验讲清楚 |

## 目录树

```
Skill/
├── README.md
├── math-modeling/
│   ├── SKILL.md
│   └── references/
│       ├── architect.md      # S1
│       ├── experiment.md     # S2
│       ├── critic.md         # S3
│       ├── paper-writer.md   # S4
│       └── judge.md          # 评委
└── math-paper-comprehend/
    ├── SKILL.md
    ├── examples.md
    └── references/
        ├── models.md         # 原 ComprehendModels
        └── tests.md          # 原 ComprehendTests
```

## 用法

- 做题：`按 math-modeling 自治求解并一次交终稿包`（逐步确认时加 `交互模式`）
- 读论文：`用 math-paper-comprehend / Comprehend 精读这篇`

根目录 `Math*.md`、`Comprehend*.md` 仅为兼容跳转，**以本目录内 `SKILL.md` 为准**。

## 同步约定

改 Skill 时先改 `Skill/<name>/`，再复制到：

1. `.cursor/skills/<name>/`（项目 Cursor）
2. `~/.cursor/skills/<name>/`（全局 Cursor）
