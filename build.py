#!/usr/bin/env python3
"""从 content/YYYY-MM-DD.json 构建 GitHub Pages 静态站（仅标准库）。"""
import html
import json
import os
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from pathlib import Path
import re
import shutil
from urllib.parse import urlparse
from parse import CONTENT, ROOT, LINK, plain

SITE_URL = os.environ.get('SITE_URL', 'https://2kpurple.github.io/ai-daily').rstrip('/')
SITE_NAME = 'AI 日报'
SITE_TAGLINE = '面向 AI 初学者的每日资讯：要闻、工具、项目与需求动态。'
OUT = ROOT / 'docs'
TZ = timezone(timedelta(hours=8))


def esc(value):
    return html.escape(str(value), quote=True)


def safe_url(url):
    return url if urlparse(url).scheme in ('https', 'http') else '#'


def link(url, text, cls=''):
    return f'<a href="{esc(safe_url(url))}" target="_blank" rel="noopener noreferrer"' + (f' class="{cls}"' if cls else '') + f'>{esc(text)}</a>'


def inline(text):
    # Escape all source HTML before adding the small supported Markdown subset.
    parts, end = [], 0
    for match in LINK.finditer(text):
        parts.append(inline_marks(text[end:match.start()]))
        parts.append(link(match[2], match[1]))
        end = match.end()
    parts.append(inline_marks(text[end:]))
    return ''.join(parts)


def inline_marks(text):
    text = esc(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'`([^`]+)`', r'<code>\1</code>', text)


def markdown(text):
    # Body continuation lines and nested list bullets are retained as readable blocks.
    result, bullets = [], []
    def flush():
        if bullets:
            result.append('<ul>' + ''.join('<li>' + inline(t) + '</li>' for t in bullets) + '</ul>')
            bullets.clear()
    for line in text.splitlines():
        line = line.strip()
        if not line:
            flush()
        elif line.startswith('- '):
            bullets.append(line[2:])
        else:
            flush()
            result.append('<p>' + inline(line) + '</p>')
    flush()
    return ''.join(result)


def image_block(item, prefix):
    image = item.get('image')
    if not image:
        return ''
    return (f'<figure><img src="{esc(prefix + image["path"])}" width="{image["width"]}" height="{image["height"]}" '
            f'alt="{esc(item["title"])}的原文配图" loading="lazy" decoding="async">'
            f'<figcaption>{esc(image["credit"])} · {link(image["source_url"], "原文链接")}</figcaption></figure>')


def summary_block(item):
    if not item.get('summary', '').strip():
        return ''
    return '<aside class="editor-summary"><h4>编辑简介</h4><p>' + esc(item['summary']) + '</p></aside>'


def actions(item):
    primary = item['primary_url']
    parts = [link(primary, '阅读原文 ↗', 'read-original')] if primary else []
    parts += [link(l['url'], l['text']) for l in item['links'][1:]]
    return '<div class="actions">' + ''.join(parts) + '</div>' if parts else ''


def card(item, prefix, direction=False):
    metadata = [item['source'], item['published'], item['meta']]
    meta = ' · '.join(esc(x) for x in metadata if x)
    parts = [f'<article class="entry-card" id="{esc(item["id"])}"><h3>{esc(item["title"])}</h3>']
    if meta:
        parts.append('<p class="entry-meta">' + meta + '</p>')
    parts += [image_block(item, prefix), summary_block(item)]
    if direction:
        parts += ['<dl class="direction-fields"><dt>切入角度</dt><dd>' + esc(item['angle']) + '</dd>',
                  '<dt>参考素材</dt><dd>' + markdown(item['reference_md']) + '</dd>',
                  '<dt>适合读者</dt><dd>' + esc(item['audience']) + '</dd></dl>']
    elif item['body_md']:
        parts.append('<div class="entry-body"><h4>原文正文要点</h4>' + markdown(item['body_md']) + '</div>')
    parts += [actions(item), '</article>']
    return ''.join(parts)


def issue_body(issue, prefix, title_tag='h1'):
    parts = [f'<header class="issue-head"><{title_tag} class="issue-title">{esc(issue["title"])}</{title_tag}>'
             f'<p class="issue-window">{esc(issue["window"])}</p></header>']
    names = [(s['id'], s['name']) for s in issue['sections']] + [('directions', '今日推荐方向'), ('unverified', '未能核验的来源')]
    parts.append('<nav class="toc" aria-label="本期目录">' + ''.join(f'<a href="#{sid}">{name}</a>' for sid, name in names) + '</nav>')
    parts.append('<section class="summary-card"><h2>今日看点</h2><ul>' + ''.join('<li>' + esc(h) + '</li>' for h in issue['highlights']) + '</ul></section>')
    for section in issue['sections']:
        parts.append(f'<section aria-labelledby="{section["id"]}"><h2 id="{section["id"]}">{section["name"]}</h2>')
        parts += [card(item, prefix) for item in section['items']]
        parts.append('</section>')
    parts.append('<section aria-labelledby="directions"><h2 id="directions">今日推荐方向</h2>')
    parts += [card(item, prefix, True) for item in issue['directions']]
    parts.append('</section><section class="unverified" id="unverified"><details><summary>未能核验的来源 <span>展开查看</span></summary>')
    for item in issue['unverified']:
        parts.append(f'<div class="verification-item" id="{esc(item["id"])}"><h3>{esc(item["title"])}</h3>' + image_block(item, prefix) + summary_block(item) + markdown(item['body_md']) + actions(item) + '</div>')
    parts.append('</details></section>')
    return '\n'.join(parts)


def absolute(path):
    return SITE_URL + '/' + path if SITE_URL else path or './'


def page(title, desc, prefix, body, path=''):
    canonical = absolute(path)
    absolute_meta = f'<link rel="canonical" href="{esc(canonical)}"><meta property="og:url" content="{esc(canonical)}">' if SITE_URL else ''
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><meta name="color-scheme" content="light dark">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:site_name" content="AI 日报">{absolute_meta}
<link rel="stylesheet" href="{prefix}assets/style.css"><link rel="alternate" type="application/rss+xml" title="AI 日报" href="{prefix}feed.xml"></head>
<body><header class="topbar"><div class="wrap"><a class="brand" href="{prefix or './'}">AI <span>日报</span></a><nav class="topnav" aria-label="主导航"><a href="{prefix or './'}">首页</a><a href="{prefix}archive/">往期</a><a href="{prefix}feed.xml">RSS</a></nav></div></header>
<main class="wrap">{body}</main>
<footer><div class="wrap">AI 日报 · <a href="{prefix}feed.xml">RSS 订阅</a><p>图片版权归原作者/原网站所有，仅作引用说明，点击查看原文。</p></div></footer></body></html>\n'''


def archive(issues, prefix):
    rows = []
    for issue in issues:
        points = issue['highlights'][:3] or [i['title'] for i in issue['sections'][0]['items'][:3]]
        rows.append(f'<li><a class="t" href="{prefix}{issue["date"]}/">{esc(issue["title"])}</a><ul class="s">' + ''.join('<li>' + esc(s) + '</li>' for s in points) + '</ul></li>')
    return '<ul class="archive">' + ''.join(rows) + '</ul>'


def pager(issues, idx):
    older, newer = (issues[idx + 1] if idx + 1 < len(issues) else None), (issues[idx - 1] if idx else None)
    parts = []
    for issue, label, cls in [(older, '← 上一期', 'prev'), (newer, '下一期 →', 'next')]:
        parts.append(f'<a class="{cls}" href="../{issue["date"]}/"><small>{label}</small>{issue["date"]}</a>' if issue else '<span></span>')
    return '<nav class="pager" aria-label="期刊翻页">' + ''.join(parts) + '</nav>'


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def build():
    issues = [json.loads(p.read_text(encoding='utf-8')) for p in sorted(CONTENT.glob('????-??-??.json'), reverse=True)]
    if not issues:
        raise SystemExit('没有 JSON 数据；请先运行 python3 parse.py')
    # Remove generated pages only. Downloaded images survive every build.
    OUT.mkdir(exist_ok=True)
    for child in OUT.iterdir():
        if child.name == 'assets':
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    write(OUT / 'assets/style.css', (ROOT / 'style.css').read_text())
    write(OUT / '.nojekyll', '')
    for idx, issue in enumerate(issues):
        desc = '；'.join(issue['highlights'][:3])
        write(OUT / issue['date'] / 'index.html', page(issue['title'], desc, '../', issue_body(issue, '../') + pager(issues, idx), issue['date'] + '/'))
    latest = issues[0]
    body = '<section class="hero"><h1>AI 日报</h1><p>' + SITE_TAGLINE + '</p></section><p class="latest-label">最新一期</p>'
    body += issue_body(latest, '', 'h2') + '<h2>往期日报</h2>' + archive(issues[1:], '') + '<p><a href="archive/">查看全部往期 →</a></p>'
    write(OUT / 'index.html', page('AI 日报｜每日 AI 资讯', SITE_TAGLINE, '', body))
    write(OUT / 'archive/index.html', page('往期日报｜AI 日报', SITE_TAGLINE, '../', '<section class="hero"><h1>往期日报</h1><p>共 ' + str(len(issues)) + ' 期，按日期倒序。</p></section>' + archive(issues, '../'), 'archive/'))
    rss = []
    for issue in issues[:30]:
        pub = datetime.strptime(issue['date'], '%Y-%m-%d').replace(hour=8, tzinfo=TZ)
        description = '；'.join(issue['highlights'][:3])
        rss.append(f'<item><title>{esc(issue["title"])}</title><link>{esc(absolute(issue["date"] + "/"))}</link><guid isPermaLink="false">ai-daily:{issue["date"]}</guid><pubDate>{format_datetime(pub)}</pubDate><description>{esc(description)}</description></item>')
    write(OUT / 'feed.xml', '<?xml version="1.0" encoding="utf-8"?>\n<rss version="2.0"><channel><title>AI 日报</title><link>' + esc(absolute('')) + '</link><description>' + esc(SITE_TAGLINE) + '</description><language>zh-CN</language>' + ''.join(rss) + '</channel></rss>\n')
    urls = ['', 'archive/'] + [i['date'] + '/' for i in issues]
    write(OUT / 'sitemap.xml', '<?xml version="1.0" encoding="utf-8"?>\n' + ('<!-- 设置 SITE_URL 后使用绝对地址。 -->\n' if not SITE_URL else '') + '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + esc(absolute(u)) + '</loc></url>' for u in urls) + '</urlset>\n')
    write(OUT / 'robots.txt', 'User-agent: *\nAllow: /\n' + (f'Sitemap: {SITE_URL}/sitemap.xml\n' if SITE_URL else ''))
    print(f'构建完成：{len(issues)} 期 -> docs/')


if __name__ == '__main__':
    build()
