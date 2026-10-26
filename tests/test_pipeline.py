"""Regression checks for editorial preservation, metadata and publication references."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import parse
import enrich
import build
import check


class PipelineTests(unittest.TestCase):
    def test_reordering_and_insertions_preserve_editorial_fields(self):
        old = [parse.make_item(f'**标题 {n}** 正文。[原文](https://example.com/{n})', '2026-10-26', 'news', n, [], set()) for n in (1, 2)]
        old[0].update(summary='人工简介。用于检查合并。', summary_status='done', image={'path': 'assets/img/existing.jpg'}, image_status='ok', image_note='人工复核通过')
        used = set()
        raw = ['**新增 A** [原文](https://example.com/a)', '**新增 B** [原文](https://example.com/b)', '**更新标题** [原文](https://example.com/1)', '**标题 2** [原文](https://example.com/2)']
        items = [parse.make_item(s, '2026-10-26', 'news', n, old, used) for n, s in enumerate(raw, 1)]
        self.assertEqual(len({i['id'] for i in items}), 4)
        self.assertEqual(items[2]['id'], old[0]['id'])
        for key in ('summary', 'summary_status', 'image', 'image_status', 'image_note'):
            self.assertEqual(items[2][key], old[0][key])

    def test_metadata_nested_lists_and_link_order(self):
        raw = '**发布标题。** 说明。[官方推文](https://x.com/dotey/status/123)（10-22 03:09，4.2 万赞）｜[讨论](https://news.ycombinator.com/item?id=1)（339 分，305 条评论）\n  - [项目](https://github.com/example/project)（+2079）'
        item = parse.make_item(raw, '2026-10-26', 'news', 1, [], set())
        self.assertEqual(item['title'], '发布标题。')
        self.assertEqual(item['source'], 'X @dotey')
        self.assertEqual(item['published'], '10-22 03:09')
        self.assertIn('339 分', item['meta'])
        self.assertIn('305 条评论', item['meta'])
        self.assertEqual(len(item['links']), 3)
        self.assertNotIn('https://', item['body_text'])
        self.assertEqual(item['annotations'][0], '10-22 03:09，4.2 万赞')
        product_dates = parse.make_item('**产品回顾** 产品 A（8-11）、B（9-08）。[推文](https://x.com/dotey/status/1)', '2026-10-26', 'news', 1, [], set())
        self.assertEqual(product_dates['published'], '')
        trending = parse.make_item('**榜单** [项目](https://github.com/example/project)（+2079）', '2026-10-26', 'projects', 1, [], set())
        self.assertEqual(trending['meta'], '+2079')

    def test_invalid_summary_import_is_atomic(self):
        item = {'id': 'known', 'summary': '', 'summary_status': 'todo'}
        issue = {'sections': [{'items': [item]}], 'directions': [], 'unverified': []}
        with patch.object(enrich, 'load_issues', return_value=[(Path('unused.json'), issue)]), patch.object(enrich, 'save_json') as save:
            with self.assertRaises(ValueError):
                enrich.summary_updates({'known': '两句简介。保留原文事实。', 'unknown': '说明。'})
            save.assert_not_called()
            self.assertEqual(item['summary'], '')

    def test_image_candidates_exclude_related_story_and_avatars(self):
        fetcher = enrich.ImageFetcher.__new__(enrich.ImageFetcher)
        from bs4 import BeautifulSoup
        fetcher.soup = BeautifulSoup
        markup = '<main><img src="/article.jpg"><aside><img src="/ad.jpg"></aside><a href="/other-story"><img src="/unrelated.jpg"></a><img src="/author_profile_images/a.jpg"></main>'
        urls = fetcher.html_candidates(markup, 'https://example.com/story')
        self.assertNotIn('https://example.com/unrelated.jpg', urls)
        self.assertNotIn('https://example.com/ad.jpg', urls)
        self.assertTrue(enrich.BAD_IMAGE.search('https://example.com/author_profile_images/a.jpg'))
        self.assertIn('https://example.com/article.jpg', urls)

    def test_build_preserves_images_and_hides_empty_summaries(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / 'docs'
            image = out / 'assets/img/test.jpg'
            image.parent.mkdir(parents=True)
            image.write_bytes(b'preserved')
            fixture_content = Path(temp) / 'content'
            fixture_content.mkdir()
            issue_path = next(parse.CONTENT.glob('????-??-??.json'))
            fixture = json.loads(issue_path.read_text())
            for item in parse.all_items(fixture):
                item.update(summary='', summary_status='todo', image=None)
            (fixture_content / issue_path.name).write_text(json.dumps(fixture))
            with patch.object(build, 'OUT', out), patch.object(build, 'CONTENT', fixture_content), contextlib.redirect_stdout(StringIO()):
                build.build()
            self.assertEqual(image.read_bytes(), b'preserved')
            page = (out / 'index.html').read_text()
            self.assertNotIn('编辑简介', page)
            self.assertIn('未能核验的来源', page)
            self.assertIn('<details>', page)

    def test_links_are_escaped_and_safe(self):
        rendered = build.markdown('恶意 <script>alert(1)</script> [原文](https://example.com/?a=1&b=2)')
        self.assertNotIn('<script>', rendered)
        self.assertIn('&lt;script&gt;', rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)
        self.assertIn('&amp;b=2', rendered)


if __name__ == '__main__':
    unittest.main()
