#!/usr/bin/env python3
"""AudioScope Pro Icon Generator.

Generates high-resolution multi-size icons:
- packaging/assets/icon.png (1024x1024)
- packaging/assets/icon.ico (16, 24, 32, 48, 64, 128, 256)
- packaging/assets/icon.icns (Apple ICNS container)
"""

import math
import os
import struct
from PIL import Image, ImageDraw

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(SCRIPT_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)

size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

pad = 64
rect = [pad, pad, size - pad, size - pad]
radius = 200

# Base dark plate
draw.rounded_rectangle(rect, radius=radius, fill=(18, 20, 26, 255), outline=(45, 52, 70, 255), width=8)
draw.rounded_rectangle([pad + 12, pad + 12, size - pad - 12, size - pad - 12], radius=radius - 10, outline=(0, 210, 255, 60), width=4)

center_y = size // 2
center_x = size // 2

# Grid lines
for y in range(pad + 120, size - pad - 120, 100):
    draw.line([(pad + 80, y), (size - pad - 80, y)], fill=(32, 38, 52, 180), width=2)
for x in range(pad + 80, size - pad - 80, 100):
    draw.line([(x, pad + 120), (x, size - pad - 120)], fill=(32, 38, 52, 180), width=2)

draw.line([(pad + 80, center_y), (size - pad - 80, center_y)], fill=(0, 210, 255, 80), width=3)

# Waveform
points = []
for x in range(pad + 80, size - pad - 80, 4):
    rel_x = (x - center_x) / (size / 2 - pad - 80)
    y_val = math.sin(rel_x * 9.0) * math.exp(-rel_x**2 * 1.5) * 220 + math.sin(rel_x * 22.0) * 40
    points.append((x, center_y + y_val))

for offset in [4, 2]:
    glow_points = [(p[0], p[1]) for p in points]
    draw.line(glow_points, fill=(0, 210, 255, 70), width=16)

draw.line(points, fill=(0, 230, 255, 255), width=8)
draw.line(points, fill=(255, 255, 255, 220), width=3)

# Level meters
bar_x_start = size - pad - 220
bar_width = 18
bar_spacing = 8
heights = [360, 420, 480, 310]
colors = [(0, 230, 118, 255), (0, 230, 118, 255), (255, 171, 0, 255), (255, 61, 113, 255)]
for i, (h, col) in enumerate(zip(heights, colors)):
    bx = bar_x_start + i * (bar_width + bar_spacing)
    by_top = center_y + 180 - h
    by_bot = center_y + 180
    draw.rounded_rectangle([bx, by_top, bx + bar_width, by_bot], radius=4, fill=col)

draw.ellipse([center_x - 120, center_y - 120, center_x + 120, center_y + 120], outline=(0, 210, 255, 140), width=3)
draw.ellipse([center_x - 4, center_y - 4, center_x + 4, center_y + 4], fill=(255, 255, 255, 255))

# Save PNG
png_path = os.path.join(ASSETS_DIR, "icon.png")
img.save(png_path, "PNG")

# Save ICO
ico_path = os.path.join(ASSETS_DIR, "icon.ico")
ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
img.save(ico_path, format="ICO", sizes=ico_sizes)

# Save ICNS
icns_path = os.path.join(ASSETS_DIR, "icon.icns")
try:
    img.save(icns_path, format="ICNS")
except Exception:
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    elem_tag = b"ic10"
    elem_len = 8 + len(png_bytes)
    total_len = 8 + elem_len
    with open(icns_path, "wb") as f:
        f.write(b"icns" + struct.pack(">I", total_len))
        f.write(elem_tag + struct.pack(">I", elem_len))
        f.write(png_bytes)

print(f"Icons saved to {ASSETS_DIR}: icon.png, icon.ico, icon.icns")
