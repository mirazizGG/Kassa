from PIL import Image, ImageDraw

SIZE = 1024
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded square background with a purple->indigo gradient, matching the
# app's brand colors.
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

# Cash register glyph: screen on top, body, and a sliding cash drawer below.
cx = SIZE // 2
white = (255, 255, 255, 255)
accent = (79, 70, 229, 255)  # same as gradient bottom, used for the seam cutout

# Screen (the small display on top of the register)
screen_w = int(SIZE * 0.30)
screen_h = int(SIZE * 0.14)
screen_top = int(SIZE * 0.20)
draw.rounded_rectangle(
    [(cx - screen_w // 2, screen_top), (cx + screen_w // 2, screen_top + screen_h)],
    radius=int(SIZE * 0.03),
    fill=white,
)

# Neck connecting the screen to the body
neck_w = int(SIZE * 0.14)
neck_top = screen_top + screen_h
neck_bottom = int(SIZE * 0.40)
draw.rectangle(
    [(cx - neck_w // 2, neck_top), (cx + neck_w // 2, neck_bottom)],
    fill=white,
)

# Body (main housing)
body_w = int(SIZE * 0.50)
body_top = neck_bottom
body_bottom = int(SIZE * 0.60)
draw.rounded_rectangle(
    [(cx - body_w // 2, body_top), (cx + body_w // 2, body_bottom)],
    radius=int(SIZE * 0.05),
    fill=white,
)

# Cash drawer (wider than the body, sits below it)
drawer_w = int(SIZE * 0.64)
drawer_top = body_bottom - int(SIZE * 0.02)
drawer_bottom = int(SIZE * 0.76)
draw.rounded_rectangle(
    [(cx - drawer_w // 2, drawer_top), (cx + drawer_w // 2, drawer_bottom)],
    radius=int(SIZE * 0.04),
    fill=white,
)

# Seam between body and drawer
seam_y = body_bottom + int(SIZE * 0.005)
draw.rectangle(
    [(cx - drawer_w // 2 + int(SIZE * 0.03), seam_y), (cx + drawer_w // 2 - int(SIZE * 0.03), seam_y + int(SIZE * 0.012))],
    fill=accent,
)

# Drawer handle
handle_w = int(SIZE * 0.16)
handle_h = int(SIZE * 0.03)
handle_y = drawer_top + int(SIZE * 0.045)
draw.rounded_rectangle(
    [(cx - handle_w // 2, handle_y), (cx + handle_w // 2, handle_y + handle_h)],
    radius=handle_h // 2,
    fill=accent,
)

sizes = [16, 24, 32, 48, 64, 128, 256]
img.save("icon.ico", sizes=[(s, s) for s in sizes])
img.resize((512, 512), Image.LANCZOS).save("icon.png")
print("done")
