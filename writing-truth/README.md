# writing-truth

阅读与写作技能集，全部提炼自李笑来《写作的真相》(The Truth About Writing)。三个 skill 分别对应第一、四、五课，覆盖"钻进作者脑子 → 看逻辑骨架 → 拆修辞层"三个层次。

**Status:** v0.1.0 — Claude Code plugin（在 `jack-cheng-marketplace` 下）。

## Skills

| Skill | 调用 | 出处 | 作用 |
|-------|------|------|------|
| [dissect-author-mind](./skills/dissect-author-mind) | `/writing-truth:dissect-author-mind <文本或路径>` | 第一课·钻进作者的脑子 | 按词性拆解（名词分具体/抽象、形容词、动词、副词），生成彩色标注 HTML，反推作者受教育程度与感知能力。 |
| [logic-template-lens](./skills/logic-template-lens) | `/writing-truth:logic-template-lens <文本或路径>` | 第四课·逻辑模板 | 把文字切成"元素"，标注并列/递进/转折关系，检查三种有力模式；拆范文或诊断草稿。 |
| [rhetoric-lens](./skills/rhetoric-lens) | `/writing-truth:rhetoric-lens <文本/空话/概念>` | 第五课·修辞正义 | 处理修辞层（具象/排比/类比/隐喻）：检测一篇文章或一本书里的全部修辞、把空话写具体、为概念跨界造类比。 |

## 三层叠用

```
dissect-author-mind   → 词性层：作者眼里看到的世界（最底层）
logic-template-lens   → 逻辑层：元素如何排列（并列/递进/转折）
rhetoric-lens         → 修辞层：具象 / 排比 / 类比 / 隐喻
```

读一篇范文，可由下而上叠着看：先 dissect 看感知，再 logic 看骨架，最后 rhetoric 看修辞——"他是怎么做到的"逐层显形。

## Install

本插件随 `jack-cheng-marketplace` 一起分发：

```
/plugin marketplace add <repo 路径或 anzchy/jack-cheng-skills>
/plugin install writing-truth
```

## 依赖说明

`dissect-author-mind` 的首选渲染路径会调用 `anzchy-skills` 插件里的 `jack-html-preview`（命名空间 `/anzchy-skills:jack-html-preview`）。若未安装该插件，会自动回退到"直接生成自包含 HTML"，功能不受影响。

## License

MIT
