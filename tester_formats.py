"""
Tests du reenregistrement des photos dans leur format d'origine.

    python tester_formats.py

Une photo rognee ou censuree est reecrite par-dessus l'originale : une erreur
ici l'abime pour de bon, une fois le dossier des sauvegardes vide. Chaque test
fabrique une petite image d'un format particulier dans un dossier temporaire,
la modifie comme le fait la fenetre de tri, puis la relit :

1. ce qui s'affiche : PNG 16 bits, transparence ;
2. ce qui s'enregistre : transparence, WEBP sans perte, MPO, profil CMJN ;
3. ce qui est refuse : GIF ou TIFF deguises en JPEG, images animees ;
4. le HEIC tres detaille, que le decodeur ne relisait plus (quelques secondes).

Aucun fichier de l'utilisateur n'est touche.
"""

import os
import shutil
import sys
import tempfile

import numpy as np
from PIL import Image

import images
from bandeaux import Bandeau
from retouches import enregistrer_retouches
from rognage import rogner_fichier

DOSSIER_ESSAI = tempfile.mkdtemp(prefix="tester_formats_")
resultats = []


def verifier(intitule, reussi, detail=""):
    resultats.append((bool(reussi), intitule))
    print("  [%s] %-60s %s" % ("OK" if reussi else "ECHEC", intitule, detail))


def chemin(nom):
    return os.path.join(DOSSIER_ESSAI, nom)


def profil_factice(espace):
    """En-tete minimal d'un profil de couleurs : seul l'espace (octets 16 a 19) compte ici."""
    entete = bytearray(128)
    entete[0:4] = (128).to_bytes(4, "big")
    entete[16:20] = espace
    entete[36:40] = b"acsp"
    return bytes(entete)


# ----------------------------------------------------------------------

def test_affichage():
    print("\n1. Ce qui s'affiche")
    degrade = np.tile(np.linspace(0, 65535, 320, dtype=np.uint16), (192, 1))
    Image.fromarray(degrade).save(chemin("gris16.png"))
    milieu = images.charger_image(chemin("gris16.png")).getpixel((160, 96))
    verifier("un PNG gris 16 bits s'affiche en degrade, pas en blanc",
             110 <= milieu[0] <= 145, milieu)

    gris_transparent = Image.new("LA", (64, 64), (128, 0))
    gris_transparent.save(chemin("gris_alpha.png"))
    verifier("un PNG gris avec transparence la garde",
             images.charger_image(chemin("gris_alpha.png")).mode == "RGBA")


def test_enregistrement():
    print("\n2. Ce qui s'enregistre")
    # PNG a palette dont la couleur transparente est le noir : le bandeau noir
    # devenait transparent a l'enregistrement.
    palette = Image.new("P", (320, 192), 1)
    palette.putpalette([0, 0, 0, 200, 200, 200] + [0] * 762)
    palette.paste(0, (0, 0, 40, 40))
    palette.save(chemin("palette.png"), transparency=0)
    enregistrer_retouches(chemin("palette.png"), [Bandeau(160, 100, 120, 40, 0)], 0)
    with Image.open(chemin("palette.png")) as relue:
        rgba = relue.convert("RGBA")
    verifier("PNG a couleur transparente : le bandeau reste noir et opaque",
             rgba.getpixel((160, 100)) == (0, 0, 0, 255), rgba.getpixel((160, 100)))
    verifier("PNG a couleur transparente : le fond transparent le reste",
             rgba.getpixel((2, 2))[3] == 0, rgba.getpixel((2, 2)))

    # WEBP sans perte : Pillow le reencodait avec perte, en qualite 80.
    photo = Image.effect_noise((320, 192), 30).convert("RGB")
    photo.save(chemin("sans_perte.webp"), lossless=True)
    avant = images.charger_image(chemin("sans_perte.webp"))
    enregistrer_retouches(chemin("sans_perte.webp"), [Bandeau(280, 160, 30, 12, 0)], 0)
    apres = images.charger_image(chemin("sans_perte.webp"))
    identique = (avant.crop((0, 0, 200, 120)).tobytes()
                 == apres.crop((0, 0, 200, 120)).tobytes())
    verifier("un WEBP sans perte le reste", images.webp_sans_perte(chemin("sans_perte.webp"))
             and identique)

    # MPO (JPEG a plusieurs vues) nomme .jpe : il etait reecrit en PNG.
    vue = Image.new("RGB", (320, 192), (90, 120, 150))
    vue.save(chemin("vues.jpe"), "MPO", save_all=True, append_images=[vue])
    rogner_fichier(chemin("vues.jpe"), (20, 10, 200, 150), 0)
    verifier("un MPO reste un JPEG", images.format_origine(chemin("vues.jpe")) == "JPEG",
             images.format_origine(chemin("vues.jpe")))

    # JPEG CMJN : enregistre en RGB, il gardait son profil CMJN, qui ne le
    # decrivait plus.
    Image.new("CMYK", (320, 192)).save(chemin("cmjn.jpg"), quality=95,
                                       icc_profile=profil_factice(b"CMYK"))
    rogner_fichier(chemin("cmjn.jpg"), (20, 10, 200, 150), 0)
    with Image.open(chemin("cmjn.jpg")) as relue:
        profil = relue.info.get("icc_profile")
    verifier("un JPEG CMJN ne garde pas un profil qui ne le decrit plus",
             not profil or profil[16:20] == b"RGB ")
    verifier("aucun fichier temporaire ne reste",
             not [nom for nom in os.listdir(DOSSIER_ESSAI) if nom.endswith(".tmp")])


def test_refus():
    print("\n3. Ce qui est refuse")
    Image.new("RGB", (32, 32)).save(chemin("normale.jpg"))
    verifier("un vrai JPEG se modifie", images.est_modifiable(chemin("normale.jpg")))

    Image.new("RGB", (32, 32)).save(chemin("anime.jpg"), "GIF", save_all=True,
                                    append_images=[Image.new("RGB", (32, 32), (9, 9, 9))])
    verifier("un GIF nomme .jpg est refuse", not images.est_modifiable(chemin("anime.jpg")))

    Image.new("RGB", (32, 32)).save(chemin("scan.jpg"), "TIFF")
    verifier("un TIFF nomme .jpg est refuse", not images.est_modifiable(chemin("scan.jpg")))

    Image.new("RGB", (32, 32)).save(chemin("anime.png"), save_all=True,
                                    append_images=[Image.new("RGB", (32, 32), (9, 9, 9))])
    verifier("un PNG anime est refuse", not images.est_modifiable(chemin("anime.png")))


def test_heic_detaille():
    print("\n4. HEIC tres detaille (quelques secondes)")
    # Du bruit tres fort : en qualite 95, le fichier depasse 16 Mio, et le
    # decodeur livre avec pillow-heif ne le relisait plus.
    generateur = np.random.default_rng(3)
    bruit = generateur.integers(-80, 81, size=(3000, 4000, 3), dtype=np.int16)
    image = Image.fromarray(np.clip(bruit + 128, 0, 255).astype(np.uint8), "RGB")
    image.save(chemin("detaille.heic"), "HEIF", quality=50)
    images.enregistrer_au_format_origine(images.charger_image(chemin("detaille.heic")),
                                         chemin("detaille.heic"), "HEIF")
    try:
        relue = images.charger_image(chemin("detaille.heic"))
        lisible = relue.size == (4000, 3000)
    except Exception:
        lisible = False
    verifier("un HEIC tres detaille reenregistre se relit",
             lisible, "%.1f Mio" % (os.path.getsize(chemin("detaille.heic")) / 2 ** 20))


# ----------------------------------------------------------------------

def main():
    print("\nTests des formats d'image")
    print("=" * 78)
    try:
        test_affichage()
        test_enregistrement()
        test_refus()
        test_heic_detaille()
    finally:
        shutil.rmtree(DOSSIER_ESSAI, ignore_errors=True)

    echecs = [intitule for reussi, intitule in resultats if not reussi]
    print("\n" + "=" * 78)
    if echecs:
        print("%d test(s) sur %d echouent :" % (len(echecs), len(resultats)))
        for intitule in echecs:
            print("  - " + intitule)
        return 1
    print("Les %d tests passent." % len(resultats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
