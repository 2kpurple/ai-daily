# AI 日报

面向 AI 初学者的每日资讯静态站，包含要闻、工具、项目、需求与合作动态和推荐阅读方向。手机优先，窄栏居中，随系统切换深浅色，无需 JavaScript。

在线阅读：<https://2kpurple.github.io/ai-daily/>　·　RSS：<https://2kpurple.github.io/ai-daily/feed.xml>

## 文件结构

```text
content/YYYY-MM-DD.md     每期原稿
content/YYYY-MM-DD.json   结构化数据、编辑简介与图片信息
parse.py                  Markdown → JSON，合并保留简介与图片
enrich.py                 配图处理与简介管理
build.py                  JSON → docs/，仅用 Python 标准库
check.py                  用语、数据、页面引用检查
style.css                 样式源文件
scripts/                  浏览器布局与截图核对脚本
image_rejections.json     人工复核排除的图片 URL 与原因
docs/                     GitHub Pages 产物及配图
tests/                    单元测试
.github/workflows/pages.yml  GitHub Pages 构建与部署
```

`build.py` 只读取仓库内的 JSON，不访问网络、不下载资源。

## 本地运行

Python 3.10+。解析、构建、文字检查仅用标准库；图片命令需要 requests、beautifulsoup4、lxml、Pillow。

```bash
python3 parse.py
python3 enrich.py images
python3 enrich.py todo
SITE_URL=https://2kpurple.github.io/ai-daily python3 build.py
python3 check.py
python3 -m unittest discover -s tests
python3 -m http.server -d docs 8000
```

原稿规范、简介写作与配图规则见 [DAILY.md](DAILY.md)。

## 部署

推送到 `main` 后由 `.github/workflows/pages.yml` 构建并发布到 GitHub Pages。工作流只从已提交的 JSON 构建，不在 CI 中抓图。`SITE_URL` 用于生成 canonical、RSS 与 sitemap 的绝对地址，未设置时使用相对路径，方便本地预览。

## 版权说明

各条目内容与配图的版权归原作者及原网站所有，本站仅作引用与导读，每张配图下均标注来源与原文链接。
