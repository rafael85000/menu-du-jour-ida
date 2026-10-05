from PIL import Image
import numpy as np, sys

def rogner_story(src, dst):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im.convert("L"))
    w = a.shape[1]
    dark = (a < 200).sum(0)
    # colonne vide entre les deux exemplaires, près du milieu
    vides = [x for x in range(int(w*.4), int(w*.6)) if dark[x] == 0]
    coupe = (vides[0] + vides[-1]) // 2 if vides else w // 2
    menu = im.crop((0, 0, coupe, im.height))
    # retirer les marges blanches
    g = np.asarray(menu.convert("L")) < 230
    ys, xs = np.where(g)
    menu = menu.crop((xs.min(), ys.min(), xs.max()+1, ys.max()+1))
    # placer sur un fond blanc 1080x1920 (format story)
    W, H, marge = 1080, 1920, 50
    r = min((W-2*marge)/menu.width, (H-2*marge)/menu.height)
    menu = menu.resize((int(menu.width*r), int(menu.height*r)), Image.LANCZOS)
    fond = Image.new("RGB", (W, H), "white")
    fond.paste(menu, ((W-menu.width)//2, (H-menu.height)//2))
    fond.save(dst, quality=95)

if __name__ == "__main__":
    rogner_story(sys.argv[1], sys.argv[2])
