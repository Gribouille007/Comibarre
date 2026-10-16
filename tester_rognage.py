"""
Tests du rognage par les bords.

    python tester_rognage.py

Le rognage consiste a reduire les bords de la photo, comme sur un telephone :
on tire l'un des quatre bords, l'un des quatre coins, ou le cadre entier. Ces
calculs sont faciles a casser sans s'en apercevoir, parce que trois reperes s'y
croisent :

- les pixels de l'ecran, ou se trouve la souris ;
- les pixels de la photo telle qu'elle est affichee, apres la rotation
  d'examen (touche R), ou vit le cadre ;
- les pixels de la photo dans son sens d'origine, qui sont ceux du fichier.

Une erreur de signe dans l'un des passages ne se voit pas : le cadre bouge
normalement a l'ecran, et c'est le mauvais cote qui disparait du fichier. Le
test 2 verifie donc le resultat sur le fichier, et non a l'ecran.

Ces tests ouvrent une vraie fenetre Tkinter et lui envoient de faux evenements
de souris : ils passent par exactement le meme code que l'utilisateur. Aucune
photo n'est lue ni ecrite sur le disque.
"""

import sys
import tkinter as tk

from PIL import Image

import visionneuse as vis
from images import fabriquer_apercu
from rognage import rogner_image

# Dimensions de la fenetre d'essai. Une fenetre plus petite que la photo, pour
# que la photo soit reduite a l'affichage comme elle l'est en usage reel.
FENETRE = "900x700"

resultats = []


def verifier(intitule, obtenu, attendu, tolerance=1.5):
    """Compare un resultat a ce qui etait attendu, et retient le verdict.

    La tolerance est indispensable : un cadre passe des pixels de l'ecran a
    ceux de la photo et en revient, ce qui laisse des arrondis d'un demi-pixel.
    """
    if isinstance(attendu, tuple) and isinstance(obtenu, tuple):
        reussi = (len(obtenu) == len(attendu)
                  and all(abs(a - b) <= tolerance for a, b in zip(obtenu, attendu)))
    elif isinstance(attendu, float) or isinstance(obtenu, float):
        reussi = abs(obtenu - attendu) <= tolerance
    else:
        reussi = obtenu == attendu
    resultats.append((reussi, intitule))
    print("  [%s] %-50s %s" % ("OK" if reussi else "ECHEC", intitule, obtenu))


class FausseSouris:
    """Un evenement de souris, tel que Tkinter en fabrique."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class Banc:
    """Une visionneuse prete a l'emploi, avec une photo et un cadre de rognage."""

    def __init__(self, racine, taille_photo, rotation=0, photo=None):
        self.racine = racine
        racine.geometry(FENETRE)
        racine.update()

        self.vue = vis.Visionneuse(racine)
        self.vue.canvas.pack(fill="both", expand=True)
        racine.update()

        self.photo = photo if photo is not None else Image.new("RGB", taille_photo,
                                                               (90, 120, 150))
        largeur = max(self.vue.canvas.winfo_width(), 1)
        hauteur = max(self.vue.canvas.winfo_height(), 1)
        self.vue.montrer(self.photo, fabriquer_apercu(self.photo, (largeur, hauteur)))
        for _ in range(rotation // 90):
            self.vue.pivoter()
        racine.update()

    def commencer(self):
        self.vue.commencer_rognage()
        self.racine.update()
        return self

    def bords_a_l_ecran(self):
        """Les quatre bords du cadre, en pixels de l'ecran."""
        gauche, haut = self.vue._vers_ecran(self.vue.cadre[0], self.vue.cadre[1])
        droite, bas = self.vue._vers_ecran(self.vue.cadre[2], self.vue.cadre[3])
        return gauche, haut, droite, bas

    def tirer(self, depuis, vers):
        """Appuie en `depuis`, glisse jusqu'a `vers`, relache."""
        self.vue._souris_pressee(FausseSouris(*depuis))
        self.vue._souris_glissee(FausseSouris(*vers))
        self.vue._souris_relachee(FausseSouris(*vers))
        self.racine.update()

    def detruire(self):
        self.vue.canvas.destroy()


# ----------------------------------------------------------------------
# Test 1 : la geometrie du cadre
# ----------------------------------------------------------------------

def test_geometrie(racine):
    print("\n1. Geometrie du cadre")
    largeur_photo, hauteur_photo = 1000, 500
    banc = Banc(racine, (largeur_photo, hauteur_photo)).commencer()
    vue = banc.vue
    facteur = vue._facteur()

    verifier("au depart, le cadre epouse la photo entiere", vue.cadre,
             (0, 0, largeur_photo, hauteur_photo))
    verifier("au depart, il n'y a rien a rogner", vue.cadre_de_rognage(), None)

    # Ce que la souris attrape, selon l'endroit ou elle se trouve.
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    milieu_x, milieu_y = (gauche + droite) / 2, (haut + bas) / 2
    for intitule, point, attendu in (
            ("bord gauche", (gauche, milieu_y), "gauche"),
            ("bord droit", (droite, milieu_y), "droite"),
            ("bord haut", (milieu_x, haut), "haut"),
            ("bord bas", (milieu_x, bas), "bas"),
            ("coin haut-gauche", (gauche, haut), "haut_gauche"),
            ("coin bas-droite", (droite, bas), "bas_droite"),
            ("interieur du cadre", (milieu_x, milieu_y), "interieur"),
            ("en dehors du cadre", (gauche - 60, milieu_y), None)):
        verifier("la souris attrape : %s" % intitule,
                 vue._prise_sous_la_souris(*point), attendu)

    # Tirer un bord ne doit deplacer que celui-la.
    banc.commencer()
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    banc.tirer((gauche, milieu_y), (gauche + 100, milieu_y))
    verifier("tirer le bord gauche ne deplace que lui", vue.cadre,
             (100 / facteur, 0, largeur_photo, hauteur_photo))

    # Tirer un coin doit en deplacer deux.
    banc.commencer()
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    banc.tirer((droite, bas), (droite - 80, bas - 40))
    verifier("tirer un coin deplace ses deux cotes", vue.cadre,
             (0, 0, largeur_photo - 80 / facteur, hauteur_photo - 40 / facteur))

    # Glisser dans le cadre le deplace sans le redimensionner.
    banc.commencer()
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    banc.tirer((gauche, haut), (gauche + 120, haut + 60))
    avant = vue.cadre
    taille_avant = (avant[2] - avant[0], avant[3] - avant[1])
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    banc.tirer(((gauche + droite) / 2, (haut + bas) / 2),
               ((gauche + droite) / 2 - 30, (haut + bas) / 2 - 20))
    verifier("glisser dans le cadre ne change pas sa taille",
             (vue.cadre[2] - vue.cadre[0], vue.cadre[3] - vue.cadre[1]), taille_avant)
    verifier("glisser dans le cadre le deplace bien",
             vue.cadre[0] < avant[0] and vue.cadre[1] < avant[1], True)

    # Les dimensions annoncees a l'utilisateur doivent etre celles du cadre.
    cadre = vue.cadre_de_rognage()
    verifier("les dimensions annoncees sont celles du cadre", vue.taille_du_cadre(),
             (cadre[2] - cadre[0], cadre[3] - cadre[1]), tolerance=0)
    banc.detruire()


# ----------------------------------------------------------------------
# Test 2 : le bon cote est coupe, meme sur une photo pivotee
# ----------------------------------------------------------------------

BANDE = 60
COULEURS = {"haut": (255, 0, 0), "bas": (0, 255, 0),
            "gauche": (0, 0, 255), "droite": (255, 255, 0)}


def photo_aux_bords_colores(largeur, hauteur):
    """Une photo dont chaque bord porte une couleur differente.

    C'est ce qui permet de dire, en regardant le fichier obtenu, quel cote a
    reellement ete coupe.
    """
    image = Image.new("RGB", (largeur, hauteur), (128, 128, 128))
    boites = {"haut": (0, 0, largeur, BANDE),
              "bas": (0, hauteur - BANDE, largeur, hauteur),
              "gauche": (0, 0, BANDE, hauteur),
              "droite": (largeur - BANDE, 0, largeur, hauteur)}
    for nom, couleur in COULEURS.items():
        image.paste(couleur, boites[nom])
    return image


def test_rotation(racine):
    """Tirer le bord gauche de l'ecran coupe-t-il le bon cote du fichier ?

    Quand la photo est pivotee a l'ecran, le bord gauche de l'ecran ne
    correspond plus au bord gauche de la photo : apres un quart de tour a
    droite, c'est son bord bas qui se retrouve a gauche. C'est exactement ce
    que ce test controle, pour les quatre orientations.
    """
    print("\n2. Le bon cote est coupe, meme apres une rotation (touche R)")
    largeur_photo, hauteur_photo = 1000, 500
    origine = photo_aux_bords_colores(largeur_photo, hauteur_photo)

    # Quel bord de la photo se retrouve a gauche de l'ecran, selon la rotation.
    bord_a_gauche_de_l_ecran = {0: "gauche", 90: "bas", 180: "droite", 270: "haut"}

    for rotation, bande_attendue in bord_a_gauche_de_l_ecran.items():
        banc = Banc(racine, None, rotation=rotation, photo=origine).commencer()
        gauche, haut, droite, bas = banc.bords_a_l_ecran()
        # Assez loin pour emporter toute la bande coloree, et un peu plus.
        recul = BANDE * banc.vue._facteur() + 12
        banc.tirer((gauche, (haut + bas) / 2), (gauche + recul, (haut + bas) / 2))

        rognee = rogner_image(origine, banc.vue.cadre_de_rognage(), rotation)
        presentes = {couleur for _, couleur in rognee.convert("RGB").getcolors(999999)}
        disparues = {nom for nom, couleur in COULEURS.items()
                     if couleur not in presentes}
        # Pas de guillemets « » dans ce message : certaines consoles Windows ne
        # savent pas les afficher, et le test echouerait sur son propre
        # affichage plutot que sur ce qu'il mesure.
        verifier("rotation %3d : tirer a gauche coupe le bord du %s"
                 % (rotation, bande_attendue), disparues, {bande_attendue})
        banc.detruire()


# ----------------------------------------------------------------------
# Test 3 : le cadre ne sort jamais de la photo et reste saisissable
# ----------------------------------------------------------------------

def test_limites(racine):
    """Le cadre doit rester dans la photo, et garder un cote attrapable.

    Sans cote minimal, un geste un peu vif reduirait le cadre a un trait dont
    plus aucun bord ne pourrait etre saisi : l'utilisateur serait coince.
    """
    print("\n3. Limites : le cadre reste dans la photo et reste saisissable")
    cas = [("photo ordinaire", (1200, 800)),
           ("photo minuscule", (30, 20)),
           ("photo tres large", (8000, 200)),
           ("photo tres haute", (200, 8000))]

    for intitule, taille in cas:
        for rotation in (0, 90):
            banc = Banc(racine, taille, rotation=rotation).commencer()
            vue = banc.vue
            largeur_affichee, hauteur_affichee = vue._dimensions()
            gauche, haut, droite, bas = banc.bords_a_l_ecran()

            # On malmene le cadre bien au-dela des bords de la fenetre.
            banc.tirer((gauche, haut), (droite + 900, bas + 900))
            banc.tirer((droite, bas), (-900, -900))
            banc.tirer(((gauche + droite) / 2, (haut + bas) / 2), (9999, 9999))

            gauche_cadre, haut_cadre, droite_cadre, bas_cadre = vue.cadre
            dans_la_photo = (0 <= gauche_cadre < droite_cadre <= largeur_affichee
                             and 0 <= haut_cadre < bas_cadre <= hauteur_affichee)
            verifier("%-18s rotation %3d : cadre reste dans la photo"
                     % (intitule, rotation), dans_la_photo, True)
            banc.detruire()

    # Et le cote minimal, mesure sur une photo ordinaire.
    banc = Banc(racine, (1200, 800)).commencer()
    gauche, haut, droite, bas = banc.bords_a_l_ecran()
    banc.tirer((gauche, (haut + bas) / 2), (droite + 500, (haut + bas) / 2))
    largeur_restante = (banc.vue.cadre[2] - banc.vue.cadre[0]) * banc.vue._facteur()
    verifier("cadre ecrase : largeur ramenee au cote minimal",
             largeur_restante, float(vis.COTE_MINIMAL_ECRAN))
    banc.detruire()


# ----------------------------------------------------------------------
# Test 4 : la forme du pointeur
# ----------------------------------------------------------------------

def test_pointeur(racine):
    """La forme du pointeur annonce ce qu'un appui va faire, et revient ensuite.

    Le pointeur doit aussi redevenir une fleche ordinaire apres le rognage :
    hors du mode barrer, plus rien ne le remettrait en place ensuite, et il
    resterait bloque sur une fleche d'angle.
    """
    print("\n4. Forme du pointeur")
    banc = Banc(racine, (1200, 800)).commencer()
    vue = banc.vue
    gauche, haut, droite, bas = banc.bords_a_l_ecran()

    for intitule, point, attendu in (
            ("sur un coin", (gauche, haut), "top_left_corner"),
            ("sur un bord vertical", (gauche, (haut + bas) / 2), "sb_h_double_arrow"),
            ("sur un bord horizontal", ((gauche + droite) / 2, haut),
             "sb_v_double_arrow"),
            ("dans le cadre", ((gauche + droite) / 2, (haut + bas) / 2), "fleur"),
            ("hors du cadre", (4, 4), "")):
        vue._souris_bougee(FausseSouris(*point))
        verifier("pointeur %s" % intitule, vue.curseur, attendu)

    vue._souris_bougee(FausseSouris(gauche, haut))
    vue.arreter_rognage()
    verifier("pointeur rendu a la fleche apres le rognage", vue.curseur, "")
    banc.detruire()


def main():
    print("\nTests du rognage par les bords")
    print("=" * 72)

    racine = tk.Tk()
    try:
        test_geometrie(racine)
        test_rotation(racine)
        test_limites(racine)
        test_pointeur(racine)
    finally:
        racine.destroy()

    echecs = [intitule for reussi, intitule in resultats if not reussi]
    print("\n" + "=" * 72)
    if echecs:
        print("%d test(s) sur %d echouent :" % (len(echecs), len(resultats)))
        for intitule in echecs:
            print("  - %s" % intitule)
        return 1
    print("Les %d tests passent." % len(resultats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
