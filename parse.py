#!/usr/bin/env python3
"""将中性 Markdown 解析为同目录 JSON；保留已有的编辑简介和图片。"""
import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / 'content'
SECTIONS = {'今日要闻': 'news', '工具与更新': 'tools', '热门项目与玩法': 'projects', '需求与合作动态': 'cooperation'}
HEADINGS = ['今日看点', *SECTIONS, '今日推荐方向', '未能核验的来源']
LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s]+?)\)')


def plain(text):
    text = LINK.sub(lambda m: m[1], text)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    return html.unescape(text).strip()


def links_in(text):
    links = []
    for m in LINK.finditer(text):
        link = {'text': plain(m[1]), 'url': m[2]}
        if link not in links:
            links.append(link)
    return links


def infer_source(url, label=''):
    host = (urlparse(url).hostname or '').lower().removeprefix('www.')
    if host in ('x.com', 'twitter.com'):
        return 'X @' + urlparse(url).path.strip('/').split('/')[0]
    sources = {'github.com': 'GitHub', 'openai.com': 'OpenAI', 'anthropic.com': 'Anthropic', 'claude.com': 'Anthropic',
               'v2ex.com': 'V2EX', 'news.ycombinator.com': 'Hacker News', 'reddit.com': 'Reddit', 'eleduck.com': '电鸭',
               'aibase.com': 'AIbase', 'ai-\u0062\u006f\u0074.cn': 'AI工具集', 'm.okjike.com': '即刻', 'tldr.tech': 'TLDR AI',
               'simonwillison.net': 'Simon Willison', 'kimi.ai': 'Kimi', 'sspai.com': '少数派',
               '1password.com': '1Password', 'minimaxir.com': 'Max Woolf', 'businessinsider.com': 'Business Insider',
               'lynchlab.net': 'Magnus Lynch', 'theatlantic.com': 'The Atlantic', 'theverge.com': 'The Verge',
               'ruanyifeng.com': '阮一峰', 'producthunt.com': 'Product Hunt', 'indiehackers.com': 'Indie Hackers', 'blog.railway.com': 'Railway'}
    return sources.get(host, plain(label) or host) if host else ''


def entries(lines):
    """顶层列表是一张卡片；缩进子项和续行属于同一张卡片。"""
    result, current = [], []
    for line in lines:
        if line.startswith('- '):
            if current:
                result.append('\n'.join(current).strip())
            current = [line[2:]]
        elif line.strip():
            if not current:
                raise ValueError('条目必须以顶层 - **标题** 开头：' + line)
            current.append(line)
    if current:
        result.append('\n'.join(current).strip())
    return result


def all_items(issue):
    return [i for s in issue['sections'] for i in s['items']] + issue['directions'] + issue['unverified']


def save_json(path, data):
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def make_item(raw, date, sid, index, old_items, used):
    m = re.match(r'^\*\*(.+?)\*\*(.*)$', raw, re.S)
    if not m:
        raise ValueError(f'{date} {sid}: 缺少加粗标题：{raw[:80]}')
    title_md, body_md = m.groups()
    links = links_in(raw)
    primary = links[0]['url'] if links else ''
    title = plain(title_md).rstrip('：:')
    item_id = f'{date}-{sid}-{index:02d}'
    # URL 匹配优先；无链接条目使用标题匹配。仅以序号匹配会把重排后的简介配错。
    old = next((x for x in old_items if x['id'] not in used and primary and x.get('primary_url') == primary), None)
    if old is None:
        old = next((x for x in old_items if x['id'] not in used and x.get('title') == title), None)
    if old:
        item_id = old['id']
        used.add(item_id)
    elif item_id in {x['id'] for x in old_items} or item_id in used:
        n = max([int(ident.rsplit('-', 1)[-1]) for ident in ({x['id'] for x in old_items} | used) if ident.rsplit('-', 1)[-1].isdigit()] + [index]) + 1
        item_id = f'{date}-{sid}-{n:02d}'
    used.add(item_id)
    # Chinese parentheses may contain nested ASCII parentheses; preserve complete annotations.
    annotations = re.findall(r'（([^（）]*)）', raw)
    for match in re.finditer(LINK.pattern + r'\s*\(([^()]*)\)', raw):
        annotations.append(match[3])
    published, metas = [], []
    publication_notes = [m[3] or m[4] for m in re.finditer(LINK.pattern + r'\s*(?:（([^（）]*)）|\(([^()]*)\))', raw)]
    date_re = re.compile(r'\d{1,2}-\d{2}|\d{4}|\d{1,2}:\d{2}|October|Show HN.*窗口|feed 发布时间|美国时间')
    heat_re = re.compile(r'\d[^，；｜]*?(?:赞|浏览|收藏|回复|评论|评|分(?!钟)|星)|热度第一')
    for note in annotations:
        # Split only at Chinese commas/semicolons; original date/time characters are retained.
        for piece in re.split(r'[，；]', note):
            if heat_re.search(piece) or re.match(r'^[+＋]\d+', piece):
                if piece not in metas:
                    metas.append(piece)
            elif note in publication_notes and date_re.search(piece) and (re.search(r'\d{1,2}-\d{2}|\d{4}-\d{2}|\d{1,2}:\d{2}|October', piece) or '窗口' in piece or '美国时间' in piece):
                if piece not in published:
                    published.append(piece)
    # Heat counts can occur outside parentheses (e.g. HN window score).
    for match in re.finditer(r'(?:HN\s*窗口内)?约?\s*\d[\d.]*\s*(?:万\s*)?(?:分(?!钟)|条回复|条评论|评|赞|收藏|浏览)|[+＋]\d+\s*星', plain(raw)):
        value = match[0].strip()
        if not any(value in x for x in metas):
            metas.append(value)
    item = {'id': item_id, 'title': title, 'title_md': title_md, 'body_md': body_md.strip(),
            'body_text': plain(body_md), 'source': infer_source(primary, links[0]['text'] if links else ''),
            'published': '；'.join(published), 'meta': '；'.join(metas), 'annotations': annotations,
            'primary_url': primary, 'links': links, 'summary': '', 'summary_status': 'todo',
            'image': None, 'image_status': 'none', 'image_note': '尚未检查图片'}
    if old:
        for key in ('summary', 'summary_status', 'image', 'image_status', 'image_note'):
            if key in old:
                item[key] = old[key]
    item['summary_status'] = 'done' if item['summary'].strip() else 'todo'
    if sid == 'directions':
        def field(name):
            match = re.search(r'^\s+- ' + name + r'：(.*?)(?=\n\s+- (?:切入角度|参考素材|适合读者)：|\Z)', body_md, re.M | re.S)
            return match[1].strip() if match else ''
        item.update(name=title, angle=plain(field('切入角度')), audience=plain(field('适合读者')), reference_md=field('参考素材'))
        if not item['angle'] or not item['audience'] or not field('参考素材'):
            raise ValueError(f'{item_id}: 推荐方向缺少必填字段')
    return item


def parse_issue(path):
    text = path.read_text(encoding='utf-8')
    sections, current = {}, None
    title, window = '', []
    for line in text.splitlines():
        if line.startswith('# '):
            title = line[2:]
        elif line.startswith('> '):
            window.append(line[2:])
        elif line.startswith('## '):
            current = line[3:]
            if current not in HEADINGS or current in sections:
                raise ValueError(f'{path.name}: 未知或重复二级标题 {current}')
            sections[current] = []
        elif current:
            sections[current].append(line)
        elif line.strip():
            raise ValueError(f'{path.name}: 标题与时间窗口以外的前言不受支持')
    if not title or set(sections) != set(HEADINGS):
        raise ValueError(f'{path.name}: 标题或固定章节不完整')
    output = path.with_suffix('.json')
    old = json.loads(output.read_text()) if output.exists() else {'sections': [], 'directions': [], 'unverified': []}
    used = set()
    issue = {'date': path.stem, 'title': title, 'window': '\n'.join(window),
             'highlights': [plain(s) for s in entries(sections['今日看点'])], 'sections': [], 'directions': [], 'unverified': []}
    for name, sid in [*SECTIONS.items(), ('今日推荐方向', 'directions'), ('未能核验的来源', 'unverified')]:
        old_items = (next((s['items'] for s in old['sections'] if s['id'] == sid), []) if sid in SECTIONS.values() else old.get(sid, []))
        items = [make_item(raw, path.stem, sid, idx, old_items, used) for idx, raw in enumerate(entries(sections[name]), 1)]
        if sid in SECTIONS.values():
            issue['sections'].append({'id': sid, 'name': name, 'items': items})
        else:
            issue[sid] = items
    save_json(output, issue)
    print(f'{path.stem}: {len(all_items(issue))} 条目 -> {output.relative_to(ROOT)}')
    return issue


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('date', nargs='?')
    args = ap.parse_args()
    paths = sorted(CONTENT.glob(f'{args.date or "????-??-??"}.md'))
    if not paths:
        ap.error('找不到对应日期的 Markdown')
    for path in paths:
        parse_issue(path)
