#!/usr/bin/env python3
"""检查公开文本用语、结构化数据和构建文件引用。"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse
from parse import ROOT, CONTENT, all_items, plain

# Unicode escapes keep the checker's own source compatible with its text policy.
TERMS = [
    '\u516c\u4f17\u53f7\u9009\u9898', '\u516c\u4f17\u53f7', '\u6296\u97f3', '\u5c0f\u7ea2\u4e66',
    '\u63a5\u5355', '\u6da8\u7c89', '\u53d8\u73b0', '\u7206\u6b3e', '\u5f15\u6d41', '\u6da8\u4e92\u52a8',
    '\u9009\u9898', '\u81ea\u52a8\u6293\u53d6', '\u961f\u53cb',
]
PATTERN = '|'.join(re.escape(x) for x in TERMS) + r'|[0-9]+\s*\u5e74\s*Android\s*\u5f00\u53d1\u8005|\b[Bb][Oo][Tt]\b'
# Only these factual product/URL strings are exceptions.
PRODUCT = 'Grok ' + '\u0042\u006f\u0074'
URL_EXCEPTION = re.compile(r'https?://(?:www\.)?ai-\u0062\u006f\u0074\.cn(?![A-Za-z0-9.-])(?:[/?#][A-Za-z0-9._~:/?#@!$&%*+,;=+-]*)?')
TEXT_SUFFIXES = {'.md', '.json', '.py', '.html', '.xml', '.txt', '.css', '.yml', '.yaml', '.tsv', '.js', '.cjs', '.mjs', '.sh'}


def files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and p.suffix in TEXT_SUFFIXES and not {'.git', 'preview', 'reports', '__pycache__'}.intersection(p.relative_to(ROOT).parts))


def sanitized(text):
    return URL_EXCEPTION.sub('[事实链接]', text.replace(PRODUCT, '[产品名]'))


def text_check():
    issues, exceptions = [], set()
    for path in files():
        text = path.read_text(encoding='utf-8')
        exceptions.update(URL_EXCEPTION.findall(text))
        if PRODUCT in text:
            exceptions.add(PRODUCT)
        for n, line in enumerate(sanitized(text).splitlines(), 1):
            for match in re.finditer(PATTERN, line, re.I):
                issues.append(f'{path.relative_to(ROOT)}:{n}: {match[0]}')
    return issues, exceptions


class PageRefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs, self.ids, self.images, self.external = [], [], [], []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag in ('a', 'link', 'img'):
            ref = attrs.get('src') if tag == 'img' else attrs.get('href')
            if ref:
                self.refs.append(ref)
                if ref.startswith('http') and tag == 'a':
                    self.external.append(attrs)
        if tag == 'img':
            self.images.append(attrs)


def data_check():
    errors, ids = [], set()
    for path in sorted(CONTENT.glob('????-??-??.json')):
        issue = json.loads(path.read_text())
        for section in issue['sections']:
            for item in section['items']:
                if not item.get('summary', '').strip():
                    errors.append(item['id'] + '：栏目简介为空')
        for item in all_items(issue):
            ident = item['id']
            if ident in ids:
                errors.append('重复 id：' + ident)
            ids.add(ident)
            if item['primary_url'] != (item['links'][0]['url'] if item['links'] else ''):
                errors.append(ident + '：主链接与首链接不一致')
            if item['body_text'] != plain(item['body_md']):
                errors.append(ident + '：纯文本正文与 Markdown 不一致')
            if item['summary_status'] != ('done' if item['summary'].strip() else 'todo'):
                errors.append(ident + '：简介状态不一致')
            image = item['image']
            if image:
                target = (ROOT / 'docs' / image['path']).resolve()
                if not target.is_relative_to(ROOT / 'docs/assets/img') or not target.is_file():
                    errors.append(ident + '：图片路径不存在或越界')
                if min(image['width'], image['height']) < 300 or max(image['width'], image['height']) > 1200:
                    errors.append(ident + '：图片尺寸不合要求')
                if image['source_url'] not in [x['url'] for x in item['links']]:
                    errors.append(ident + '：图片引用页不在条目链接内')
                if item['image_status'] != 'ok':
                    errors.append(ident + '：有图但图片状态异常')
            elif item['image_status'] not in ('none', 'failed') or not item['image_note']:
                errors.append(ident + '：缺少图片状态或原因')
    for path in (ROOT / 'docs').rglob('*.html'):
        parser = PageRefs()
        parser.feed(path.read_text())
        if len(parser.ids) != len(set(parser.ids)):
            errors.append(str(path.relative_to(ROOT)) + '：页面锚点重复')
        for url in parser.refs:
            parts = urlparse(url)
            if parts.scheme or parts.netloc:
                continue
            target = path.parent / unquote(parts.path) if parts.path else path
            if target.is_dir():
                target /= 'index.html'
            if not target.is_file():
                errors.append(f'{path.relative_to(ROOT)}：引用不存在 {url}')
            elif parts.fragment:
                other = parser
                if target.resolve() != path.resolve():
                    other = PageRefs()
                    other.feed(target.read_text())
                if parts.fragment not in other.ids:
                    errors.append(f'{path.relative_to(ROOT)}：锚点不存在 {url}')
        for image in parser.images:
            if urlparse(image.get('src', '')).scheme or urlparse(image.get('src', '')).netloc:
                errors.append(f'{path.relative_to(ROOT)}：图片不是本地资源')
            if not image.get('width') or not image.get('height') or not image.get('alt'):
                errors.append(f'{path.relative_to(ROOT)}：图片缺少尺寸或替代文本')
        for attrs in parser.external:
            if attrs.get('target') != '_blank' or 'noopener' not in attrs.get('rel', ''):
                errors.append(f'{path.relative_to(ROOT)}：外部链接缺少安全属性')
    return errors, len(ids)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pattern', action='store_true', help='输出供 grep 使用的规则')
    ap.add_argument('--scan-text', action='store_true', help='输出去除事实例外后的公开文本')
    args = ap.parse_args()
    if args.pattern:
        # POSIX grep does not understand Unicode escapes in a regular expression.
        print(PATTERN.replace(r'\u5e74', '\u5e74').replace(r'\u5f00\u53d1\u8005', '\u5f00\u53d1\u8005'))
        return
    if args.scan_text:
        for path in files():
            print(sanitized(path.read_text()))
        return
    errors, exceptions = text_check()
    data_errors, count = data_check()
    errors += data_errors
    for error in errors:
        print(error)
    print(f'禁用词检查：{"未通过" if errors else "通过"}；{count} 个结构化条目；{len(errors)} 项问题')
    print('事实例外：')
    for exception in sorted(exceptions):
        print('  ' + exception)
    sys.exit(bool(errors))


if __name__ == '__main__':
    main()
