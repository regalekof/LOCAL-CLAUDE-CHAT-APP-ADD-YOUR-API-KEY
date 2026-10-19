"""Regenerates icon.ico / icon.png (needs Pillow). The generated files are committed, so you rarely need this."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).parent
S = 1024  # draw big, then downscale for smooth edges

img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.rounded_rectangle((0, 0, S - 1, S - 1), radius=230, fill=(201, 100, 66, 255))   # accent square

# chat bubble
white = (255, 255, 255, 255)
d.rounded_rectangle((200, 230, 824, 700), radius=150, fill=white)
d.polygon([(330, 660), (330, 840), (520, 690)], fill=white)                       # tail

# three typing dots
for cx in (362, 512, 662):
    d.ellipse((cx - 44, 420, cx + 44, 508), fill=(201, 100, 66, 255))

img.resize((256, 256), Image.LANCZOS).save(OUT / 'icon.png')
img.save(OUT / 'icon.ico', sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print('wrote icon.ico and icon.png')
