"""
Verification de l'installation.

A lancer une fois apres l'installation des bibliotheques, pour s'assurer que
tout est en place avant de traiter de vraies photos :

    python verifier_installation.py

Le script n'a besoin d'aucune photo : il fabrique lui-meme ses images de test
dans un dossier temporaire, qu'il efface ensuite. Il ne touche a aucun de vos
fichiers.
"""

import math
import os
import shutil
import sys
import tempfile

resultats = []


def verifier(intitule, fonction):
    """Execute une verification et retient son resultat."""
    try:
        detail = fonction()
        resultats.append((True, intitule, detail))
        print("  [OK]    %-42s %s" % (intitule, detail or ""))
    except Exception as erreur:
        resultats.append((False, intitule, str(erreur)))
        print("  [ECHEC] %-42s %s" % (intitule, erreur))


def main():
    print("\nVerification de l'installation")
    print("=" * 70)

    # ------------------------------------------------------------------
    print("\n1. Version de Python")
    # ------------------------------------------------------------------
    def version_python():
        if sys.version_info < (3, 11):
            raise RuntimeError("Python 3.11 ou superieur est requis, "
                               "vous avez %d.%d" % sys.version_info[:2])
        return "Python %d.%d.%d" % sys.version_info[:3]

    verifier("Version de Python", version_python)

    # ------------------------------------------------------------------
    print("\n2. Bibliotheques")
    # ------------------------------------------------------------------
    def bibliotheque_tkinter():
        import tkinter
        return "Tk %s" % tkinter.TkVersion

    def bibliotheque_pillow():
        from PIL import Image
        return "Pillow %s" % Image.__version__

    def bibliotheque_heif():
        import pillow_heif
        return "pillow-heif %s" % pillow_heif.__version__

    def bibliotheque_opencv():
        import cv2
        if not hasattr(cv2, "FaceDetectorYN"):
            raise RuntimeError("cette version d'OpenCV ne fournit pas YuNet")
        return "OpenCV %s" % cv2.__version__

    verifier("Tkinter (interface graphique)", bibliotheque_tkinter)
    verifier("Pillow (images)", bibliotheque_pillow)
    verifier("pillow-heif (photos iPhone)", bibliotheque_heif)
    verifier("OpenCV (detection de visages)", bibliotheque_opencv)

    # ------------------------------------------------------------------
    print("\n3. Modele de detection")
    # ------------------------------------------------------------------
    def modele_present():
        from visages import CHEMIN_MODELE
        if not os.path.isfile(CHEMIN_MODELE):
            raise FileNotFoundError("fichier absent : %s" % CHEMIN_MODELE)
        taille = os.path.getsize(CHEMIN_MODELE) // 1024
        return "%s (%d Ko)" % (os.path.basename(CHEMIN_MODELE), taille)

    def modele_chargeable():
        from visages import DetecteurVisages
        DetecteurVisages()
        return "le detecteur se charge correctement"

    verifier("Presence du modele", modele_present)
    verifier("Chargement du modele", modele_chargeable)

    # ------------------------------------------------------------------
    print("\n4. Lecture et enregistrement des images")
    # ------------------------------------------------------------------
    dossier = tempfile.mkdtemp(prefix="verification_photos_")
    try:
        from PIL import Image, ImageDraw
        from images import charger_image, enregistrer_au_format_origine, format_origine
        from bandeaux import Bandeau

        def aller_retour(extension, format_attendu):
            """Ecrit une image, y pose un bandeau, la relit, et compare."""
            chemin = os.path.join(dossier, "essai" + extension)
            Image.new("RGB", (200, 140), (190, 130, 70)).save(chemin)
            format_lu = format_origine(chemin)

            image = charger_image(chemin)
            Bandeau(100, 70, 90, 30, 20).dessiner(ImageDraw.Draw(image))
            enregistrer_au_format_origine(image, chemin, format_lu)

            with Image.open(chemin) as relue:
                format_final = relue.format
                taille = relue.size
                pixel = relue.convert("RGB").getpixel((100, 70))

            if format_final != format_attendu:
                raise RuntimeError("format %s au lieu de %s" % (format_final, format_attendu))
            if taille != (200, 140):
                raise RuntimeError("la taille a change : %s" % (taille,))
            if sum(pixel) > 40:
                raise RuntimeError("le bandeau n'a pas ete incruste")
            return "format %s conserve, bandeau incruste" % format_final

        verifier("Photo JPEG", lambda: aller_retour(".jpg", "JPEG"))
        verifier("Photo PNG", lambda: aller_retour(".png", "PNG"))
        verifier("Photo HEIC (iPhone)", lambda: aller_retour(".heic", "HEIF"))

        def orientation_exif():
            """La photo doit etre remise dans le bon sens, une fois et une seule."""
            chemin = os.path.join(dossier, "orientation.jpg")
            image = Image.new("RGB", (300, 150), (40, 150, 90))
            etiquettes = image.getexif()
            etiquettes[274] = 6          # 6 = a pivoter d'un quart de tour
            image.save(chemin, exif=etiquettes)

            orientee = charger_image(chemin)
            if orientee.size != (150, 300):
                raise RuntimeError("la photo n'a pas ete remise dans le bon sens")

            Bandeau(75, 200, 60, 24, 0).dessiner(ImageDraw.Draw(orientee))
            enregistrer_au_format_origine(orientee, chemin, "JPEG")

            relue = charger_image(chemin)
            if relue.size != (150, 300):
                raise RuntimeError("l'orientation a change a l'enregistrement")
            if sum(relue.getpixel((75, 200))) > 40:
                raise RuntimeError("le bandeau ne s'est pas retrouve au bon endroit")
            return "pas de double rotation"

        verifier("Orientation EXIF", orientation_exif)

        # --------------------------------------------------------------
        print("\n5. Detection de visages et geometrie des bandeaux")
        # --------------------------------------------------------------
        def detection_fonctionne():
            from visages import DetecteurVisages
            detecteur = DetecteurVisages()
            # Une image unie ne contient aucun visage : on verifie surtout que la
            # detection s'execute sans erreur et ne trouve rien d'imaginaire.
            trouves = detecteur.detecter(Image.new("RGB", (640, 480), (120, 120, 120)))
            if trouves:
                raise RuntimeError("%d visage(s) trouve(s) sur une image unie" % len(trouves))
            return "la detection s'execute (0 visage sur une image unie)"

        def bandeau_incline():
            """Le bandeau doit suivre l'inclinaison de la tete."""
            droit = Bandeau.depuis_yeux((100, 200), (140, 200))
            penche = Bandeau.depuis_yeux((100, 200), (140, 240))
            if abs(droit.angle) > 0.001:
                raise RuntimeError("yeux au meme niveau : angle %.2f attendu 0" % droit.angle)
            if abs(penche.angle - 45) > 0.001:
                raise RuntimeError("tete penchee : angle %.2f attendu 45" % penche.angle)
            if not (droit.contient(100, 200) and droit.contient(140, 200)):
                raise RuntimeError("le bandeau ne couvre pas les deux yeux")
            return "0 degre a plat, 45 degres tete penchee"

        verifier("Detection de visages", detection_fonctionne)
        verifier("Inclinaison du bandeau", bandeau_incline)

    finally:
        shutil.rmtree(dossier, ignore_errors=True)

    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    echecs = [intitule for reussi, intitule, _ in resultats if not reussi]
    if echecs:
        print("%d verification(s) en echec sur %d :" % (len(echecs), len(resultats)))
        for intitule in echecs:
            print("   - %s" % intitule)
        print("\nReinstallez les bibliotheques avec :")
        print("   pip install -r requirements.txt")
        return 1

    print("Les %d verifications passent. L'installation est fonctionnelle." % len(resultats))
    print("\nVous pouvez lancer le logiciel avec :   python main.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
