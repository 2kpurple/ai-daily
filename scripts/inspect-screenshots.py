#!/usr/bin/env python3
"""用 Pillow 核对 PNG，生成长页分段和人工复核拼图。"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

PREVIEW = Path(__file__).resolve().parents[1] / 'preview'
EXPECTED = {
    'home-mobile-390-firstscreen.png': (390, 844),
    'home-mobile-390-full.png': (390, None),
    'home-desktop-firstscreen.png': (1440, 900),
    'home-desktop-full.png': (1440, None),
    'home-mobile-390-dark-firstscreen.png': (390, 844),
    'archive-mobile-390-full.png': (390, None),
    'issue-2026-10-22-mobile-390-full.png': (390, None),
}

for name, (width, height) in EXPECTED.items():
    with Image.open(PREVIEW / name) as image:
        assert image.format == 'PNG'
        assert image.width == width and (height is None or image.height == height)
        image.verify()
    if name.endswith('-full.png'):
        with Image.open(PREVIEW / name) as image:
            if image.height > 16000:
                for n, y in enumerate(range(0, image.height, 16000), 1):
                    image.crop((0, y, image.width, min(y + 16000, image.height))).save(
                        PREVIEW / (Path(name).stem + f'-part-{n:02d}.png'))
            # Show the centered reading column on desktop overviews.
            if image.width == 1440:
                image = image.crop((360, 0, 1080, image.height))
            width, height = image.size
            strip = 2200
            scale = min(1, 360 / width)
            count = (height + strip - 1) // strip
            columns = min(count, 4)
            rows = (count + columns - 1) // columns
            tile_width, tile_height = int(width * scale), int(strip * scale)
            overview = Image.new('RGB', (columns * (tile_width + 8), rows * (tile_height + 32)), '#dddddd')
            draw = ImageDraw.Draw(overview)
            for n, y in enumerate(range(0, height, strip)):
                tile = image.crop((0, y, width, min(y + strip, height))).convert('RGB')
                tile = tile.resize((tile_width, int(tile.height * scale)))
                x, top = (n % columns) * (tile_width + 8), (n // columns) * (tile_height + 32)
                draw.text((x, top + 8), f'{y}-{min(y + strip, height)}px', fill='black')
                overview.paste(tile, (x, top + 32))
            overview.save(PREVIEW / (Path(name).stem + '-overview.png'))

files = ['home-mobile-390-firstscreen.png', 'home-mobile-390-dark-firstscreen.png',
         'home-desktop-firstscreen.png', 'home-mobile-390-card.png',
         'home-mobile-390-dark-card.png', 'archive-mobile-390-full.png']
canvas = Image.new('RGB', (1600, 1420), '#dddddd')
draw = ImageDraw.Draw(canvas)
for n, name in enumerate(files):
    with Image.open(PREVIEW / name) as image:
        image = image.convert('RGB')
        image.thumbnail((500, 650))
        x, y = (n % 3) * 530 + 10, (n // 3) * 710 + 35
        canvas.paste(image, (x, y))
        draw.text((x, y - 22), name, fill='black')
canvas.save(PREVIEW / 'contact-sheet.png')

metadata = []
for path in sorted(PREVIEW.glob('*.png')):
    with Image.open(path) as image:
        assert image.format == 'PNG'
        metadata.append({'path': 'preview/' + path.name, 'width': image.width, 'height': image.height})
        image.verify()
(PREVIEW / 'screenshot-dimensions.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
print(f'Pillow 检查通过：{len(metadata)} 张 PNG，7 张指定截图尺寸正确。')
