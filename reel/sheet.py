import sys, glob
from PIL import Image, ImageDraw
d, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3]); fs = sorted(glob.glob(d + "/f_*.jpg"))
ims = [Image.open(f).convert("RGB") for f in fs]; w = 300; h = int(ims[0].height * w / ims[0].width)
rows = -(-len(ims) // cols); S = Image.new("RGB", (cols * w, rows * h))
for i, (im, f) in enumerate(zip(ims, fs)):
    im = im.resize((w, h)); ImageDraw.Draw(im).text((6, 6), f.split("f_")[1][:-4], fill=(255, 255, 0)); S.paste(im, ((i % cols) * w, (i // cols) * h))
S.save(out)
