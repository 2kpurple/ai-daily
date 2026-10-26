# AI 日报日更说明

## 数据与文件

每期的公开原稿为 `content/YYYY-MM-DD.md`，结构化结果为同目录同名 JSON。JSON 是构建的唯一内容输入；编辑简介与图片资料保存在 JSON 中，不回写 Markdown。本地网页缓存只供核对、寻找配图，不提交到仓库。

JSON 的 `sections` 包含 `news`、`tools`、`projects`、`cooperation` 四节；`directions`、`unverified` 是单独的条目数组，均带通用条目字段。`highlights` 是纯文本字符串数组。条目 ID 形如 `2026-10-26-news-01`，初次按章节顺序编号；重新解析时优先在同节按 `primary_url` 匹配，随后按标题匹配，保留已有 ID、summary、image 及其状态，避免重新排序后简介错配。相同来源但标题不同的条目应分别审阅；同一节里不建议重复使用同一个主链接。

`title` 来自开头加粗部分；`title_md` 保留原始标题写法；`body_md` 是标题之后的全部说明与缩进子项；`body_text` 去掉 Markdown 标记但保留可读链接文字。`links` 按出现顺序存储 `{text,url}`，第一条为 `primary_url`。无链接的版本观察或核验记录允许空链接。`source` 根据域名和链接文字推断，X 帖子使用账号名。`published` 保存时间说明中的原始片段，不转换时区或日期；`meta` 保存热度片段；多个片段用中文分号分隔。原括号内容完整保存在 `annotations`，正文中也保留原说明，便于逐项核对。

`summary` 为空时 `summary_status=todo`，有内容时为 `done`。`image` 是对象或 null；状态为 `ok`、`none` 或 `failed`，无图必须有 `image_note`。`image.source_url` 是取得配图的引用页，可能是次要素材链接；`remote_url` 保存图片实际下载地址。引用页必须来自条目本身的链接。

## 公开原稿规范

首行 `# AI 日报 · YYYY-MM-DD（周几）`，随后使用 `> 时间窗口：……`。只写时间、范围、重复内容说明和核验依据，不写内部执行安排或个人身份介绍。

二级标题依次固定为 `今日看点`、`今日要闻`、`工具与更新`、`热门项目与玩法`、`需求与合作动态`、`今日推荐方向`、`未能核验的来源`。每张卡片由顶层 `- **标题**` 开始；续行与子项必须缩进，不得另起未缩进的列表。汇总多个仓库或作品时保留一张卡片，子链接全部进入 links。标题和说明必须保持事实、日期、数字、链接与原始资料一致；未经核验的说法保留原有归属、传闻或作者自述限定。

以下示例引用现有期次，仅演示写法。

### 今日看点

```markdown
## 今日看点
- **Claude 应用的自动模式。** 从下周起覆盖 Pro、Max、Team 用户，涉及操作授权与安全检查。
```

### 今日要闻

```markdown
## 今日要闻
- **Claude 模型（Anthropic 托管）在 Google Cloud 正式可用。** 可以使用 Google Cloud 的账号、账单和承诺消费额度。[官方推文](https://x.com/claudeai/status/2113380122468454765)（10-23 05:21）
```

### 工具与更新

```markdown
## 工具与更新
- **Claude Code v2.1.309：** 安全和权限修复。[Release](https://github.com/anthropics/claude-code/releases/tag/v2.1.309)（10-23 06:18）
```

### 热门项目与玩法

```markdown
## 热门项目与玩法
- **GitHub Trending 今日榜：** 以下是本期项目及单日新增星数。
  - [ponytail](https://github.com/DietrichGebert/ponytail)（+2079）：让 Agent 少写代码。
  - [orca](https://github.com/stablyai/orca)（+1541）：同时管理多个编程 Agent。
```

### 需求与合作动态

```markdown
## 需求与合作动态
- **电鸭中小企业 AI 知识库案例：** 上传员工手册和制度，生成内部问答助手，涉及 HR 和客服反复回答同类问题的场景。[电鸭](https://eleduck.com/posts/rdf3VY)（10-22 14:09）
```

客观描述需求、合作方式、价格与市场信号；保留用户自述和核验限制，避免将个案推导为普遍结论。

### 今日推荐方向

```markdown
## 今日推荐方向
- **Claude 自动模式与操作授权**
  - 切入角度：了解逐步批准与风险检查的区别，参考安全修复说明。
  - 参考素材：[官方推文](https://x.com/claudeai/status/2113360845409583307)｜[版本说明](https://github.com/anthropics/claude-code/releases/tag/v2.1.309)
  - 适合读者：希望了解 Claude 操作授权的初学者。
```

方向名、切入角度、参考素材、适合读者四项必填。参考素材可分行列出，链接子项再缩进两格。只解释读者可以了解什么，不写传播策略、情绪诱导或个人获利承诺。补充阅读方向也遵守相同结构。

### 未能核验的来源

```markdown
## 未能核验的来源
- **打不开或被限流：** r/ClaudeAI 返回 429；OpenAI 文章页返回 403，改用官方 RSS 正文摘要核验。
```

记录当前期次实际遇到的时间窗口、可访问性或日期依据问题。核验记录通常没有主图；页面以可展开列表呈现。

## 日更步骤

1. 将可公开的中性新原稿放入 `content/`，不要把未经整理的私人原稿直接复制进公开目录。
2. 运行 `python3 parse.py`，或指定 `python3 parse.py 2026-10-26`。检查 JSON 的标题、时间、热度、主链接和子链接。
3. 运行 `python3 enrich.py images 2026-10-26`，再运行 `python3 enrich.py todo 2026-10-26` 列出四个栏目简介待写条目的 ID、标题、主链接。日期省略时处理全部期次；推荐方向与未核验来源不要求简介，需要查看时加 `--include-optional`。
4. 按下面的要求撰写简介，用 `python3 enrich.py set-summary 2026-10-26-news-01 "简介内容"` 写入；批量写入用 `python3 enrich.py import-summaries summaries.json`，文件结构为 `{ "条目id": "简介内容" }`。导入先校验所有 ID 和内容，有错误时不写入。
5. 运行 `python3 build.py`，再运行 `python3 check.py`。用 `python3 -m http.server -d docs 8000` 预览，检查窄屏、深浅色、图片与原文链接。
6. 检查通过后，提交 `content/`、脚本和 `docs/` 并推送到 `main`，GitHub Actions 会自动构建并发布。

### 简介写作

每条 2–4 句中文，面向 AI 新手，说明“是什么、为什么值得了解、适用场景或使用边界”。只基于本期日报与引用原文，不编造功能、收益、数字或结论；作者自述与传闻须明确归属。简介应提供理解线索，避免复述标题、制造焦虑或提出未经原文支持的承诺。简介为空时不在页面显示占位文案。

### 图片处理与复核

图片命令使用浏览器 UA，单次请求超时 15 秒；优先原文的 og:image、twitter:image 或正文大图。GitHub 使用仓库社交图或 README 非徽章大图，允许显示仓库信息的默认生成卡片；X 使用推文媒体图片或视频封面，尝试 fxtwitter 接口。可使用明确匹配到原文 URL 的本地网页或帖子缓存，不能使用首页其他条目的图充数。

排除头像、标志、图标、广告、追踪图、徽章、SVG、任一边不足 300px 的图片。压缩为 JPEG，最长边不超过 1200px，质量 80，移除元数据，以条目 ID 命名保存到 `docs/assets/img/YYYY-MM-DD/`。图像显示原比例，不裁切，写入宽高属性，图下标注“图片来源：来源名 · 原文链接”。图片版权归原作者/原网站所有，仅作引用说明。

已有图片默认跳过；使用 `--force` 重抓。必须以 Pillow 核对实际尺寸并人工查看缩略图；将误取的通用标志或推广图片 URL 及原因写入 `image_rejections.json`，再重抓相应期次。排除记录会在以后重抓时继续生效。没有可用图就保留 null、none/failed 和具体原因，不补无关图片。原文正文、日期、图中内容或账号信息有冲突时以原稿为依据并人工复核，不从图片扩写新事实。

### 用语检查

完整规则保存在 `check.py` 的 Unicode 转义清单中，涵盖推广运营用语、个人身份说明与内部执行措辞。事实性的产品名和原始 URL 仅按脚本中的明确例外保留；常规检查会列出命中的事实例外。新增例外须是原文中的真实名称或链接。

推荐执行 `python3 check.py`，失败时返回非零退出码。需要独立使用 grep 时，下面命令先排除明确事实例外，再从脚本取得规则，扫描公开文件：

```bash
python3 check.py --scan-text | grep -nE "$(python3 check.py --pattern)"
```

grep 无输出且退出码为 1 表示没有命中；日常自动检查应使用 `python3 check.py` 的退出码。文本扫描覆盖 content、docs、仓库文档、脚本与样式，忽略 preview、reports、缓存和版本控制目录。
