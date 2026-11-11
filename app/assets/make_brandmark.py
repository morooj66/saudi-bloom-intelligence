"""Generates app/assets/brandmark.png (browser-tab icon) with Pillow. Geometric mark: eight radial rounded bars of
different lengths (reads as a bloom and as a radial bar chart). Purely decorative; encodes no data."""
import math
from pathlib import Path
from PIL import Image, ImageDraw

SIZE, SS = 128, 4
LENGTHS = [17, 11, 20, 13, 18, 10, 21, 14]
ROSE, PURPLE, BG = (217, 112, 143), (167, 139, 218), (18, 16, 20)
img = Image.new("RGBA", (SIZE * SS, SIZE * SS), BG + (255,))
d = ImageDraw.Draw(img)
c = SIZE * SS / 2
k = SIZE * SS / 48
for i, L in enumerate(LENGTHS):
    a = math.radians(i * 45 - 90)
    t = i / 7
    col = tuple(int(ROSE[j] * (1 - t) + PURPLE[j] * t) for j in range(3))
    x0, y0 = c + math.cos(a) * 6.5 * k, c + math.sin(a) * 6.5 * k
    x1, y1 = c + math.cos(a) * L * k, c + math.sin(a) * L * k
    w = 3.4 * k
    d.line([(x0, y0), (x1, y1)], fill=col, width=int(w))
    for (x, y) in ((x0, y0), (x1, y1)):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=col)
img.resize((SIZE, SIZE), Image.LANCZOS).convert("RGB").save(Path(__file__).with_name("brandmark.png"))
print("written")
