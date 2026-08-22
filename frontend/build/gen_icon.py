from PIL import Image, ImageDraw

SIZE = 1024
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded square background with a purple->indigo gradient, matching the
# Login page's branding colors.
def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))

top = (99, 102, 241)      # indigo-500
bottom = (79, 70, 229)    # indigo-600 / purple

grad = Image.new("RGB", (SIZE, SIZE), top)
gdraw = ImageDraw.Draw(grad)
for y in range(SIZE):
    t = y / SIZE
    color = lerp(top, bottom, t)
    gdraw.line([(0, y), (SIZE, y)], fill=color)

mask = Image.new("L", (SIZE, SIZE), 0)
mdraw = ImageDraw.Draw(mask)
radius = int(SIZE * 0.22)
mdraw.rounded_rectangle([(0, 0), (SIZE, SIZE)], radius=radius, fill=255)

img = Image.composite(grad.convert("RGBA"), img, mask)
draw = ImageDraw.Draw(img)

# House / roof shape (matches the roof-and-bars glyph used on the Login page).
cx, cy = SIZE // 2, SIZE // 2
white = (255, 255, 255, 255)

roof_w = int(SIZE * 0.46)
roof_top_y = int(SIZE * 0.28)
roof_bottom_y = int(SIZE * 0.5)
draw.polygon(
    [
        (cx, roof_top_y),
        (cx - roof_w // 2, roof_bottom_y),
        (cx - roof_w // 2 + int(SIZE * 0.05), roof_bottom_y),
        (cx, roof_top_y + int(SIZE * 0.08)),
        (cx + roof_w // 2 - int(SIZE * 0.05), roof_bottom_y),
        (cx + roof_w // 2, roof_bottom_y),
    ],
    fill=white,
)

body_left = cx - int(SIZE * 0.16)
body_right = cx + int(SIZE * 0.16)
body_top = roof_bottom_y
body_bottom = int(SIZE * 0.72)
line_w = int(SIZE * 0.045)
draw.rounded_rectangle(
    [(body_left, body_top), (body_left + line_w, body_bottom)],
    radius=line_w // 2,
    fill=white,
)
draw.rounded_rectangle(
    [(body_right - line_w, body_top), (body_right, body_bottom)],
    radius=line_w // 2,
    fill=white,
)

# Small bar chart (sales/POS motif) beneath the roof
bar_w = int(SIZE * 0.06)
gap = int(SIZE * 0.03)
base_y = int(SIZE * 0.72)
bars = [0.10, 0.16, 0.12]
start_x = cx - (len(bars) * bar_w + (len(bars) - 1) * gap) // 2
for i, h_frac in enumerate(bars):
    h = int(SIZE * h_frac)
    x0 = start_x + i * (bar_w + gap)
    x1 = x0 + bar_w
    y1 = base_y
    y0 = y1 - h
    draw.rounded_rectangle([(x0, y0), (x1, y1)], radius=bar_w // 3, fill=white)

sizes = [16, 24, 32, 48, 64, 128, 256]
img.save("icon.ico", sizes=[(s, s) for s in sizes])
img.resize((512, 512), Image.LANCZOS).save("icon.png")
print("done")
