"""Render the branded 1200x630 sharing card. Maintainer tool: requires Pillow."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

scale = 2
image = Image.new("RGB", (1200 * scale, 630 * scale), "#f8faf6")
draw = ImageDraw.Draw(image)
regular_candidates = [Path("/System/Library/Fonts/Supplemental/Arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")]
bold_candidates = [Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]
regular = next((p for p in regular_candidates if p.exists()), None)
bold = next((p for p in bold_candidates if p.exists()), None)
if not regular or not bold:
    raise SystemExit("Install Arial or DejaVu Sans before rendering the share image.")

# Native drawing keeps the sharing card reproducible without external services.
draw.rounded_rectangle((64*scale, 54*scale, 122*scale, 112*scale), radius=15*scale, fill="#286953")
draw.line([(93*scale,65*scale),(111*scale,75*scale),(111*scale,95*scale),(93*scale,105*scale),(75*scale,95*scale),(75*scale,75*scale),(93*scale,65*scale)], fill="#d2e7ba", width=3*scale)
draw.text((139*scale,59*scale), "optimus.", font=ImageFont.truetype(str(bold),40*scale), fill="#233e30")
draw.text((65*scale,162*scale), "YOUR LOCAL BUILD WORKSPACE", font=ImageFont.truetype(str(bold),15*scale), fill="#718763")
draw.text((62*scale,206*scale), "You bring the idea.", font=ImageFont.truetype(str(bold),61*scale), fill="#233e30")
draw.text((62*scale,281*scale), "Build it with your AI.", font=ImageFont.truetype(str(bold),61*scale), fill="#819770")
draw.text((65*scale,386*scale), "A clear plan. Parallel workers. Visible progress.", font=ImageFont.truetype(str(regular),23*scale), fill="#6c7c6b")
draw.rounded_rectangle((64*scale,455*scale,353*scale,502*scale), radius=8*scale, fill="#e9f0e0")
draw.text((81*scale,468*scale), "FREE  •  OPEN SOURCE", font=ImageFont.truetype(str(bold),16*scale), fill="#286953")
draw.line((64*scale,549*scale,1136*scale,549*scale), fill="#dfe6d8", width=scale)
draw.text((65*scale,570*scale), "optimus.weeyuga.com", font=ImageFont.truetype(str(regular),19*scale), fill="#6c7c6b")
draw.text((882*scale,570*scale), "macOS  /  Linux  /  Windows", font=ImageFont.truetype(str(regular),16*scale), fill="#6c7c6b")

# Connected cube motif echoes the application's worker-team illustration.
draw.rounded_rectangle((902*scale,173*scale,1136*scale,460*scale), radius=30*scale, fill="#eff5e6", outline="#dfe6d8", width=scale)
draw.line((1019*scale,282*scale,1019*scale,327*scale), fill="#aac291", width=3*scale)
draw.line((953*scale,327*scale,1085*scale,327*scale), fill="#aac291", width=3*scale)
for x in [953,1019,1085]:
    draw.line((x*scale,327*scale,x*scale,353*scale), fill="#aac291", width=3*scale)
    draw.rounded_rectangle(((x-20)*scale,353*scale,(x+20)*scale,393*scale), radius=11*scale, fill="#f8faf6", outline="#bfd0ac", width=2*scale)
    draw.rectangle(((x-7)*scale,366*scale,(x+7)*scale,379*scale), outline="#819770", width=2*scale)
draw.rounded_rectangle((978*scale,205*scale,1060*scale,287*scale), radius=22*scale, fill="#286953")
draw.line([(1019*scale,220*scale),(1041*scale,233*scale),(1041*scale,258*scale),(1019*scale,271*scale),(997*scale,258*scale),(997*scale,233*scale),(1019*scale,220*scale)], fill="#d2e7ba", width=3*scale)
draw.text((945*scale,418*scale), "ONE PLAN. YOUR TEAM.", font=ImageFont.truetype(str(bold),11*scale), fill="#718763")
destination = Path(__file__).resolve().parents[1] / "dist/optimus-share-v1.png"
image.resize((1200,630), Image.Resampling.LANCZOS).save(destination, optimize=True)
print(destination)
