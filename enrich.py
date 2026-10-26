#!/usr/bin/env python3
"""下载条目配图、列出待写简介、写入人工简介。"""
import argparse
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from io import BytesIO
import json
from pathlib import Path
import re
import threading
from urllib.parse import urljoin, urlparse
from parse import CONTENT, ROOT, all_items, infer_source, save_json

UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
TIMEOUT = 15
BAD_IMAGE = re.compile(r'avatar|favicon|shields\.io|badge|tracking|pixel|/ads/|/navatar/|profile_images|author_profile_images|abs\.twimg\.com|(?:^|[/_.-])(?:logo|icon|default[-_]?og|og[-_]?default)(?:[/_.-]|$)', re.I)
MAX_BYTES = 20 * 1024 * 1024


def issue_files(date=None):
    paths = sorted(CONTENT.glob(f'{date or "????-??-??"}.json'))
    if not paths:
        raise ValueError('找不到对应日期的 JSON；请先运行 parse.py')
    return paths


def load_issues(date=None):
    return [(p, json.loads(p.read_text(encoding='utf-8'))) for p in issue_files(date)]


def summary_updates(values):
    issues = load_issues()
    index = {item['id']: item for _, issue in issues for item in all_items(issue)}
    unknown = set(values) - index.keys()
    if unknown:
        raise ValueError('未知条目 id：' + ', '.join(sorted(unknown)))
    if any(not isinstance(s, str) or not s.strip() for s in values.values()):
        raise ValueError('简介必须为非空字符串')
    # Validate the complete import before writing any issue.
    for key, summary in values.items():
        index[key].update(summary=summary.strip(), summary_status='done')
    for path, issue in issues:
        if any(item['id'] in values for item in all_items(issue)):
            save_json(path, issue)
    print(f'已写入 {len(values)} 条简介')


class ImageFetcher:
    def __init__(self):
        import requests
        from bs4 import BeautifulSoup
        self.requests, self.soup = requests, BeautifulSoup
        self.local = threading.local()
        self.lock = threading.Lock()
        self.results = {}
        self.raw = {}
        self.raw_candidates = {}
        self.rejections = json.loads((ROOT / "image_rejections.json").read_text()) if (ROOT / "image_rejections.json").exists() else {}
        self.index_raw()

    def index_raw(self):
        """只使用明确匹配的原文页面/帖子，绝不使用首页上其他文章的图片。"""
        for folder in sorted((ROOT.parent / 'ai-daily').glob('raw-*')):
            for path in sorted(folder.iterdir()):
                if path.suffix == '.html':
                    text = path.read_text(encoding='utf-8', errors='replace')
                    # Parsing all cached pages is inexpensive and also handles arbitrary attribute order.
                    soup = self.soup(text, 'lxml')
                    tags = soup.select('link[rel="canonical"], meta[property="og:url"]')
                    for tag in tags:
                        url = tag.get('href') or tag.get('content') or ''
                        if url.startswith('http'):
                            self.raw[self.key(url)] = text
                elif path.suffix == '.json' and (path.name.startswith(('v_', 'v2', 'r_', 'x-'))):
                    try:
                        data = json.loads(path.read_text())
                    except (ValueError, OSError):
                        continue
                    self.index_json(data)
        print(f'已索引 {len(self.raw)} 个缓存页面、{len(self.raw_candidates)} 组帖子图片', flush=True)

    def index_json(self, data):
        if isinstance(data, list):
            for obj in data:
                self.index_json(obj)
        elif isinstance(data, dict):
            url = data.get('url') or data.get('permalink')
            if url and isinstance(url, str):
                if url.startswith('/r/'):
                    url = 'https://www.reddit.com' + url
                candidates = []
                for key in ('content_rendered', 'selftext_html', 'body_html'):
                    if data.get(key):
                        import html
                        candidates += self.html_candidates(html.unescape(data[key]), url)
                for match in re.finditer(r'!\[[^\]]*\]\(\s*(https?://[^\s)]+)', str(data.get('content') or data.get('selftext') or '')):
                    candidates.append(match[1])
                # Media only, never profile/card imagery from X.
                media = data.get('media') or {}
                if isinstance(media, dict):
                    for entry in media.get('photos', []) + media.get('videos', []):
                        candidate = entry.get('url') or entry.get('thumbnail_url')
                        if candidate:
                            candidates.append(candidate)
                if 'reddit.com' in url:
                    for entry in (data.get('preview') or {}).get('images', []):
                        candidates.append(entry.get('source', {}).get('url', ''))
                if candidates:
                    self.raw_candidates[self.key(url)] = candidates
            for key, val in data.items():
                if key in ('data', 'children'):
                    self.index_json(val)

    @staticmethod
    def key(url):
        p = urlparse(url)
        host = (p.hostname or '').removeprefix('www.').replace('twitter.com', 'x.com')
        return host + p.path.rstrip('/') + ('?' + p.query if p.query else '')

    @property
    def session(self):
        if not hasattr(self.local, 'session'):
            self.local.session = self.requests.Session()
            self.local.session.headers.update({'User-Agent': UA, 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
        return self.local.session

    def get(self, url):
        with self.session.get(url, timeout=TIMEOUT, stream=True) as response:
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ValueError('响应超过 20 MB')
                chunks.append(chunk)
            return b''.join(chunks), response.headers.get('Content-Type', ''), response.url

    def html_candidates(self, text, url):
        soup = self.soup(text, 'lxml')
        result = []
        # A generic site listing does not establish an image for the specific story.
        if urlparse(url).path.rstrip('/') in ('', '/zh/news', '/daily-ai-news'):
            return result
        for selector in ('meta[property="og:image"]', 'meta[name="twitter:image"]', 'meta[property="twitter:image"]', 'meta[name="twitter:image:src"]'):
            for tag in soup.select(selector):
                if tag.get('content'):
                    result.append(urljoin(url, tag['content']))
        if 'github.com' in urlparse(url).netloc:
            main = soup.select_one('article.markdown-body, #readme, article')
        else:
            main = soup.select_one('.topic_content, article, .entry-content, .post-content, main')
        if main:
            for img in main.find_all('img'):
                ancestor = img.find_parent('a', href=True)
                if ancestor:
                    destination = urljoin(url, ancestor['href'])
                    asset = re.search(r'\.(?:png|jpe?g|webp|gif)(?:\?|$)', destination, re.I)
                    if not asset and self.key(destination) != self.key(url):
                        continue
                if img.find_parent(['aside', 'nav']):
                    continue
                if any(re.search(r'(?:related|recommend|content-card|sponsor|advert)', ' '.join(parent.get('class', [])), re.I) for parent in img.parents if parent is not main):
                    continue
                description = ' '.join(str(img.get(k, '')) for k in ('alt', 'class', 'id'))
                if re.search(r'logo|avatar|badge|icon|广告|头像', description, re.I):
                    continue
                src = img.get('data-src') or img.get('data-original') or img.get('src')
                if src:
                    result.append(urljoin(url, src))
            for m in re.finditer(r'!\[[^\]]*\]\(\s*(https?://[^\s)]+)', main.get_text()):
                result.append(m[1])
        return list(dict.fromkeys(result))

    def url_candidates(self, url):
        key = self.key(url)
        result = list(self.raw_candidates.get(key, []))
        reasons = []
        host = urlparse(url).hostname or ''
        if host in ('x.com', 'twitter.com', 'www.twitter.com'):
            match = re.search(r'/([^/]+)/status/(\d+)', urlparse(url).path)
            if match:
                try:
                    payload, _, _ = self.get(f'https://api.fxtwitter.com/{match[1]}/status/{match[2]}')
                    data = json.loads(payload)
                    tweet = data.get('tweet') or {}
                    media = tweet.get('media') or {}
                    for photo in media.get('photos', []):
                        if photo.get('url'):
                            result.append(photo['url'])
                    for video in media.get('videos', []):
                        if video.get('thumbnail_url'):
                            result.append(video['thumbnail_url'])
                    if not result:
                        reasons.append('推文接口未返回媒体图片')
                except Exception as exc:
                    reasons.append(self.error(exc, '推文接口'))
            return result, reasons
        if key in self.raw:
            result += self.html_candidates(self.raw[key], url)
        if not result:
            try:
                payload, content_type, final_url = self.get(url)
                if 'image/' in content_type:
                    result.append(final_url)
                else:
                    result += self.html_candidates(payload.decode('utf-8', errors='replace'), final_url)
                if not result:
                    reasons.append('页面未提供可引用的文章主图')
            except Exception as exc:
                reasons.append(self.error(exc, '原文页面'))
        # GitHub default cards are allowed because they show repository information.
        if host == 'github.com' and len(urlparse(url).path.strip('/').split('/')) >= 2:
            repo = '/'.join(urlparse(url).path.strip('/').split('/')[:2])
            result.append('https://opengraph.githubassets.com/1/' + repo)
        return list(dict.fromkeys(result)), reasons

    @staticmethod
    def error(exc, label):
        if hasattr(exc, 'response') and exc.response is not None:
            return f'{label} HTTP {exc.response.status_code}'
        name = type(exc).__name__
        if 'Timeout' in name:
            return f'{label}超时（15 秒）'
        if 'SSLError' in name:
            return f'{label} TLS 验证失败'
        return f'{label} {name}' if not isinstance(exc, ValueError) else f'{label}：{exc}'

    def image_bytes(self, url):
        from PIL import Image, ImageOps, UnidentifiedImageError
        import html
        url = html.unescape(url)
        rejection = self.rejections.get(url) or self.rejections.get(url.split('?')[0])
        if rejection:
            raise ValueError(rejection)
        if BAD_IMAGE.search(url) or urlparse(url).path.lower().endswith('.svg'):
            raise ValueError('已排除标志、头像、徽章、广告或 SVG')
        payload, kind, _ = self.get(url)
        if 'svg' in kind:
            raise ValueError('已排除 SVG')
        try:
            with Image.open(BytesIO(payload)) as original:
                original.load()
                im = ImageOps.exif_transpose(original)
                if min(im.size) < 300:
                    raise ValueError(f'图片过小（{im.width}×{im.height}）')
                if im.width / im.height > 6 or im.height / im.width > 6:
                    raise ValueError('图片比例不适合正文配图')
                im.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
                if min(im.size) < 300:
                    raise ValueError('压缩后短边不足 300px')
                if 'A' in im.getbands() or im.mode == 'P':
                    rgba = im.convert('RGBA')
                    rgb = Image.new('RGB', rgba.size, 'white')
                    rgb.paste(rgba, mask=rgba.getchannel('A'))
                    im = rgb
                else:
                    im = im.convert('RGB')
                buffer = BytesIO()
                im.save(buffer, format='JPEG', quality=80, optimize=True)
                return buffer.getvalue(), im.width, im.height
        except UnidentifiedImageError:
            raise ValueError('响应不是 Pillow 可识别的位图')

    def fetch_url(self, url):
        with self.lock:
            future = self.results.get(url)
            owner = future is None
            if owner:
                future = self.results[url] = Future()
        if not owner:
            return future.result()
        try:
            candidates, notes = self.url_candidates(url)
            for candidate in candidates[:16]:
                try:
                    data, width, height = self.image_bytes(candidate)
                    result = {'bytes': data, 'width': width, 'height': height, 'remote_url': candidate, 'source_url': url}
                    future.set_result((result, []))
                    return result, []
                except Exception as exc:
                    notes.append(self.error(exc, '候选图片'))
            result = (None, list(dict.fromkeys(notes)) or ['未发现可用主图'])
        except Exception as exc:
            result = (None, [self.error(exc, '图片检查')])
        future.set_result(result)
        return result

    def enrich_item(self, date, item, force=False):
        existing = item.get('image')
        if existing and not force and (ROOT / 'docs' / existing['path']).is_file():
            return 'skipped'
        notes, found = [], None
        for link in item['links']:
            found, failures = self.fetch_url(link['url'])
            if found:
                break
            notes += failures
        if found:
            path = f'assets/img/{date}/{item["id"]}.jpg'
            target = ROOT / 'docs' / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(found['bytes'])
            source = infer_source(found['source_url'])
            item.update(image={'path': path, 'width': found['width'], 'height': found['height'],
                               'credit': '图片来源：' + source, 'source_url': found['source_url'], 'remote_url': found['remote_url']},
                        image_status='ok', image_note='')
            return 'ok'
        if existing:
            old_path = ROOT / 'docs' / existing['path']
            if old_path.is_file():
                old_path.unlink()
        notes = list(dict.fromkeys(notes))
        note = '；'.join(notes) if notes else '条目未提供原文链接'
        failed = any(re.search(r'HTTP|超时|Error|失败', x) for x in notes)
        item.update(image=None, image_status='failed' if failed else 'none', image_note=note)
        return item['image_status']


def images(date=None, force=False, workers=8):
    issues = load_issues(date)
    fetcher = ImageFetcher()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(fetcher.enrich_item, issue['date'], item, force): item for _, issue in issues for item in all_items(issue)}
        for n, task in enumerate(as_completed(jobs), 1):
            item = jobs[task]
            print(f'[{n}/{len(jobs)}] {item["id"]}: {task.result()}', flush=True)
    for path, issue in issues:
        save_json(path, issue)
    print('\n未取得图片的条目：')
    for _, issue in issues:
        items = all_items(issue)
        print(f'{issue["date"]}: {len(items)} 条，{sum(bool(i["image"]) for i in items)} 张配图')
        for item in items:
            if not item['image']:
                print(f'{item["id"]}\t{item["title"]}\t{item["image_note"]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    img = sub.add_parser('images')
    img.add_argument('date', nargs='?')
    img.add_argument('--force', action='store_true')
    img.add_argument('--workers', type=int, default=8)
    todo = sub.add_parser('todo')
    todo.add_argument('date', nargs='?')
    todo.add_argument('--include-optional', action='store_true', help='同时列出推荐方向与未核验来源的空简介')
    single = sub.add_parser('set-summary')
    single.add_argument('id')
    single.add_argument('summary')
    imp = sub.add_parser('import-summaries')
    imp.add_argument('file', type=Path)
    args = ap.parse_args()
    try:
        if args.command == 'images':
            if not 1 <= args.workers <= 32:
                raise ValueError('--workers 必须介于 1 和 32')
            images(args.date, args.force, args.workers)
        elif args.command == 'todo':
            total = 0
            for _, issue in load_issues(args.date):
                items = all_items(issue) if args.include_optional else [item for section in issue['sections'] for item in section['items']]
                for item in items:
                    if not item['summary'].strip():
                        print(f'{item["id"]}\t{item["title"]}\t{item["primary_url"] or "（无链接）"}')
                        total += 1
            print(f'待写简介：{total} 条')
        elif args.command == 'set-summary':
            summary_updates({args.id: args.summary})
        else:
            values = json.loads(args.file.read_text(encoding='utf-8'))
            if not isinstance(values, dict):
                raise ValueError('导入文件必须是 {id: summary} 对象')
            summary_updates(values)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))


if __name__ == '__main__':
    main()
