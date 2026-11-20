"""Toss-blue app icon: rounded square with three ascending ledger bars."""
from PIL import Image, ImageDraw

BLUE = (49, 130, 246, 255)
WHITE = (255, 255, 255, 255)


def render(size):
    s = size * 4  # supersample for clean edges
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r = int(s * 0.225)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=r, fill=BLUE)

    # three bars inside a 62% safe area, baseline aligned
    base_x, base_y = int(s * 0.24), int(s * 0.725)
    bar_w = int(s * 0.135)
    gap = int(s * 0.055)
    heights = [int(s * 0.20), int(s * 0.30), int(s * 0.42)]
    radius = bar_w // 2
    x = base_x
    for h in heights:
        d.rounded_rectangle([x, base_y - h, x + bar_w, base_y], radius=radius, fill=WHITE)
        x += bar_w + gap

    # small dot above the tallest bar, like a coin
    dot_r = int(s * 0.032)
    cx = x - gap - bar_w // 2
    d.ellipse([cx - dot_r, base_y - heights[-1] - int(s * 0.085) - dot_r,
               cx + dot_r, base_y - heights[-1] - int(s * 0.085) + dot_r], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


for px in (192, 512):
    render(px).save(f"icon-{px}.png", "PNG")
print("icons written")
