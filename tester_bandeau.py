"""
Tests du bandeau : couvre-t-il bien les yeux, et rien de plus ?

    python tester_bandeau.py                   tests automatiques
    python tester_bandeau.py --photos DOSSIER   planche de controle sur vos photos

Le bandeau doit couvrir entierement les yeux, sans monter inutilement sur le
front. Ces deux exigences se contredisent : plus le bandeau est fin, plus il
risque de laisser voir un oeil. On cherche donc la plus petite epaisseur qui
couvre encore tous les yeux.

Deux tests separes, car deux questions separees :

1. LA GEOMETRIE (test 1). En supposant les yeux parfaitement reperes, quelle
   epaisseur faut-il ? La reponse ne depend que des proportions du visage
   humain, qui sont connues et mesurees : le test est donc exact et
   reproductible, sans aucune photo.

2. LE REPERAGE (test 2). Les yeux sont-ils bien reperes ? Cela ne se verifie
   qu'avec des photos. Les visages dessines par ce fichier suffisent a montrer
   que la detection fonctionne de bout en bout, mais PAS a mesurer sa
   precision : YuNet est entraine sur des photographies, et il place les yeux
   d'un visage dessine a 7 % voire 30 % d'ecart de leur position reelle, bien
   plus que sur une vraie photo. Pour juger la precision, utilisez --photos sur
   vos propres photos.
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

from bandeaux import FACTEUR_EPAISSEUR, FACTEUR_LONGUEUR, Bandeau

# ----------------------------------------------------------------------
# Proportions du visage humain
# ----------------------------------------------------------------------
# Toutes exprimees en ecarts inter-pupillaires (l'ecart des deux pupilles,
# environ 63 mm chez l'adulte). Sources : mesures anthropometriques classiques
# du visage (Farkas). Chaque grandeur est donnee sous forme d'intervalle, car
# elle varie d'une personne a l'autre : le bandeau doit convenir a toutes.

HAUTEURS_OEIL = [0.16, 0.175, 0.19, 0.21]       # ouverture de la paupiere
BAS_DU_SOURCIL = [0.25, 0.27, 0.29, 0.32]       # pupille -> bord bas du sourcil
LARGEUR_OEIL = 0.48                             # d'un coin de l'oeil a l'autre

# Ecart vertical possible entre le point donne par la detection et la vraie
# pupille. Sur une photographie nette, il reste faible ; on va jusqu'a 8 % pour
# garder de la marge.
ERREURS_DE_REPERE = [0.00, 0.02, 0.04, 0.06, 0.08]

resultats = []


def verifier(intitule, fonction):
    try:
        detail = fonction()
        resultats.append((True, intitule))
        print("  [OK]    %-46s %s" % (intitule, detail or ""))
    except AssertionError as erreur:
        resultats.append((False, intitule))
        print("  [ECHEC] %-46s %s" % (intitule, erreur))
    except Exception as erreur:
        resultats.append((False, intitule))
        print("  [ERREUR] %-45s %s" % (intitule, erreur))


# ----------------------------------------------------------------------
# Test 1 - La geometrie, yeux parfaitement reperes
# ----------------------------------------------------------------------

def balayer_les_morphologies(facteur_epaisseur):
    """Sur combien de morphologies ce bandeau couvre-t-il les yeux ? epargne-t-il le front ?

    Renvoie (part d'yeux entierement couverts, part de sourcils non atteints),
    chacune entre 0 et 1.
    """
    demi_epaisseur = facteur_epaisseur / 2
    couverts = epargnes = total = 0

    for hauteur_oeil in HAUTEURS_OEIL:
        for bas_sourcil in BAS_DU_SOURCIL:
            for erreur in ERREURS_DE_REPERE:
                total += 1
                # Le bandeau est centre sur le point repere, qui peut etre
                # decale de `erreur` par rapport a la vraie pupille : il
                # deborde alors moins d'un cote que de l'autre.
                debord_haut = demi_epaisseur + erreur
                debord_bas = demi_epaisseur - erreur
                if min(debord_haut, debord_bas) >= hauteur_oeil / 2:
                    couverts += 1
                if debord_haut <= bas_sourcil:
                    epargnes += 1

    return couverts / total, epargnes / total


def test_epaisseur_couvre_tous_les_yeux():
    couverts, _ = balayer_les_morphologies(FACTEUR_EPAISSEUR)
    assert couverts == 1.0, (
        "l'epaisseur %.2f laisse un oeil visible sur %.0f %% des morphologies"
        % (FACTEUR_EPAISSEUR, 100 * (1 - couverts)))
    return "epaisseur %.2f, 100 %% des morphologies" % FACTEUR_EPAISSEUR


def test_epaisseur_est_la_plus_petite_possible():
    """Une epaisseur nettement plus faible doit, elle, laisser voir des yeux.

    C'est ce qui justifie la valeur retenue : elle n'est pas choisie au hasard,
    c'est le minimum. Si ce test echoue, c'est que le bandeau est plus epais
    que necessaire et couvre du visage pour rien.
    """
    couverts, _ = balayer_les_morphologies(FACTEUR_EPAISSEUR - 0.05)
    assert couverts < 1.0, (
        "une epaisseur de %.2f suffirait deja : le bandeau est trop epais"
        % (FACTEUR_EPAISSEUR - 0.05))
    return "%.2f ne suffirait pas (%.0f %% des yeux couverts)" % (
        FACTEUR_EPAISSEUR - 0.05, 100 * couverts)


def test_bandeau_ne_monte_pas_sur_le_front():
    """Le bandeau doit rester dans la zone des yeux et des sourcils.

    Le front commence au-dessus du sourcil le plus haut ; on prend le cas le
    plus defavorable, celui du sourcil le plus bas place.
    """
    haut_du_front = max(BAS_DU_SOURCIL) + 0.12   # bas du sourcil + son epaisseur
    debord = FACTEUR_EPAISSEUR / 2 + max(ERREURS_DE_REPERE)
    assert debord <= haut_du_front, (
        "le bandeau monte a %.2f, au-dela du sourcil (%.2f)" % (debord, haut_du_front))
    _, epargnes = balayer_les_morphologies(FACTEUR_EPAISSEUR)
    return "sourcils entierement epargnes sur %.0f %% des visages" % (100 * epargnes)


def test_longueur_depasse_les_coins_des_yeux():
    """Un bandeau qui s'arreterait aux yeux ne cacherait pas la personne."""
    demi_longueur = FACTEUR_LONGUEUR / 2
    coin_externe = 0.5 + LARGEUR_OEIL / 2
    assert demi_longueur > coin_externe + 0.2, (
        "longueur %.2f trop courte : elle s'arrete pres du coin de l'oeil"
        % FACTEUR_LONGUEUR)
    return "demi-longueur %.2f contre %.2f au coin de l'oeil" % (demi_longueur, coin_externe)


def test_bandeau_suit_l_inclinaison_de_la_tete():
    """Tete penchee : le bandeau doit pencher d'autant (section 9.3)."""
    for angle_voulu in (-40, -12, 0, 7, 25, 61):
        radians = math.radians(angle_voulu)
        ecart = 100
        oeil_droit = (0, 0)
        oeil_gauche = (ecart * math.cos(radians), ecart * math.sin(radians))
        bandeau = Bandeau.depuis_yeux(oeil_droit, oeil_gauche)
        assert abs(bandeau.angle - angle_voulu) < 0.001, (
            "tete penchee de %d degres, bandeau a %.1f" % (angle_voulu, bandeau.angle))
        # Les deux yeux doivent tomber dans le bandeau, quelle que soit l'inclinaison.
        assert bandeau.contient(*oeil_droit) and bandeau.contient(*oeil_gauche), (
            "un oeil sort du bandeau a %d degres" % angle_voulu)
    return "6 inclinaisons, de -40 a +61 degres"


# ----------------------------------------------------------------------
# Test 2 - Le reperage, de bout en bout
# ----------------------------------------------------------------------

def dessiner_un_visage(ecart=90, inclinaison=0.0):
    """Dessine une tete dont on connait exactement la position des yeux.

    Le dessin respecte les proportions ci-dessus : les yeux, les sourcils, le
    nez et la bouche sont places a leur distance reelle de la pupille.
    Renvoie (image, position des deux pupilles).
    """
    largeur_visage = ecart * 2.19
    image = Image.new("RGB", (int(largeur_visage * 2.0), int(largeur_visage * 2.4)),
                      (160, 170, 180))
    dessin = ImageDraw.Draw(image)
    centre_x, centre_y = image.width / 2, image.height * 0.42

    def place(dx, dy):
        """Point donne en ecarts inter-pupillaires, puis penche avec la tete."""
        angle = math.radians(inclinaison)
        x, y = dx * ecart, dy * ecart
        return (centre_x + x * math.cos(angle) - y * math.sin(angle),
                centre_y + x * math.sin(angle) + y * math.cos(angle))

    peau = (226, 190, 164)
    haut, bas = place(0, -0.98), place(0, 1.24)
    dessin.polygon([place(-0.35, 1.5), place(0.35, 1.5),
                    place(0.35, 0.9), place(-0.35, 0.9)],
                   fill=tuple(int(c * 0.9) for c in peau))
    dessin.ellipse([min(haut[0], bas[0]) - largeur_visage / 2, min(haut[1], bas[1]),
                    max(haut[0], bas[0]) + largeur_visage / 2, max(haut[1], bas[1])],
                   fill=peau)
    dessin.chord([centre_x - largeur_visage * 0.58, centre_y - ecart * 1.15,
                  centre_x + largeur_visage * 0.58, centre_y + ecart * 0.45],
                 180 + inclinaison, 360 + inclinaison, fill=(60, 45, 38))

    pupilles = {}
    for cote, position in (("droit", -0.5), ("gauche", 0.5)):
        coin_a = place(position - LARGEUR_OEIL / 2, -0.175 / 2)
        coin_b = place(position + LARGEUR_OEIL / 2, 0.175 / 2)
        dessin.ellipse([min(coin_a[0], coin_b[0]), min(coin_a[1], coin_b[1]),
                        max(coin_a[0], coin_b[0]), max(coin_a[1], coin_b[1])],
                       fill=(248, 246, 244), outline=(120, 100, 90))
        pupille = place(position, 0)
        for rayon, couleur in ((ecart * 0.096, (74, 56, 44)),
                               (ecart * 0.043, (12, 10, 10))):
            dessin.ellipse([pupille[0] - rayon, pupille[1] - rayon,
                            pupille[0] + rayon, pupille[1] + rayon], fill=couleur)
        dessin.line([place(position - LARGEUR_OEIL / 2, -0.325),
                     place(position + LARGEUR_OEIL / 2, -0.325)],
                    fill=(70, 52, 42), width=int(ecart * 0.11))
        pupilles[cote] = pupille

    dessin.line([place(-0.05, 0.25), place(0, 0.62), place(0.14, 0.62)],
                fill=(196, 158, 134), width=max(2, int(ecart * 0.05)))
    dessin.arc([place(-0.42, 0.72)[0], place(0, 0.72)[1],
                place(0.42, 0.72)[0], place(0, 1.02)[1]],
               0, 180, fill=(150, 90, 84), width=max(2, int(ecart * 0.07)))

    return image.filter(ImageFilter.GaussianBlur(max(0.6, ecart * 0.006))), pupilles


def test_detection_de_bout_en_bout():
    """La chaine complete fonctionne : detection, puis bandeau pose sur les yeux.

    On verifie ici que le programme va bien de la photo au bandeau, et non que
    le reperage est precis (voir l'entete du fichier).
    """
    from visages import DetecteurVisages

    detecteur = DetecteurVisages()
    trouves = 0
    essais = [(45, 0), (70, 10), (70, -10), (110, 0), (160, 12)]
    for ecart, inclinaison in essais:
        image, pupilles = dessiner_un_visage(ecart, inclinaison)
        visages = detecteur.detecter(image)
        if not visages:
            continue
        trouves += 1
        visage = visages[0]
        bandeau = Bandeau.depuis_yeux(visage.oeil_droit, visage.oeil_gauche)
        assert bandeau.contient(*pupilles["droit"], marge=ecart * 0.1), (
            "le bandeau ne couvre pas l'oeil droit (ecart %d px)" % ecart)
        assert bandeau.contient(*pupilles["gauche"], marge=ecart * 0.1), (
            "le bandeau ne couvre pas l'oeil gauche (ecart %d px)" % ecart)

    assert trouves >= 4, "seulement %d visages trouves sur %d" % (trouves, len(essais))
    return "%d visages sur %d, bandeaux poses sur les pupilles" % (trouves, len(essais))


# ----------------------------------------------------------------------
# Controle sur de vraies photos
# ----------------------------------------------------------------------

def planche_de_controle(dossier, sortie="planche_de_controle.jpg", maximum=12):
    """Pose les bandeaux sur de vraies photos et rassemble les visages sur une planche.

    C'est le seul moyen de juger la precision du reperage : on regarde. Aucune
    photo n'est modifiee, la planche est un nouveau fichier.
    """
    from dossiers import photos_du_dossier
    from images import charger_image
    from visages import DetecteurVisages

    detecteur = DetecteurVisages()
    vignettes = []
    for nom in photos_du_dossier(dossier):
        if len(vignettes) >= maximum:
            break
        image = charger_image(os.path.join(dossier, nom))
        if image is None:
            continue
        for visage in detecteur.detecter(image):
            if len(vignettes) >= maximum:
                break
            bandeau = Bandeau.depuis_yeux(visage.oeil_droit, visage.oeil_gauche)
            bandeau.dessiner(image)
            # On decoupe autour du visage, avec une marge, pour bien voir.
            marge = max(visage.largeur, visage.hauteur) * 0.5
            decoupe = image.crop((int(visage.x - marge), int(visage.y - marge),
                                  int(visage.x + visage.largeur + marge),
                                  int(visage.y + visage.hauteur + marge)))
            decoupe.thumbnail((260, 260))
            vignettes.append(decoupe)

    if not vignettes:
        print("Aucun visage trouve dans %s" % dossier)
        return

    colonnes = 4
    lignes = (len(vignettes) + colonnes - 1) // colonnes
    planche = Image.new("RGB", (colonnes * 270, lignes * 270), (255, 255, 255))
    for index, vignette in enumerate(vignettes):
        planche.paste(vignette, ((index % colonnes) * 270 + 5,
                                 (index // colonnes) * 270 + 5))
    planche.save(sortie, quality=92)
    print("%d visages -> %s" % (len(vignettes), os.path.abspath(sortie)))


# ----------------------------------------------------------------------

def main():
    if "--photos" in sys.argv:
        dossier = sys.argv[sys.argv.index("--photos") + 1]
        planche_de_controle(dossier)
        return 0

    print("\nTests du bandeau")
    print("=" * 72)

    print("\n1. Geometrie (yeux parfaitement reperes, %d morphologies)"
          % (len(HAUTEURS_OEIL) * len(BAS_DU_SOURCIL) * len(ERREURS_DE_REPERE)))
    verifier("l'epaisseur couvre tous les yeux", test_epaisseur_couvre_tous_les_yeux)
    verifier("elle est la plus petite possible", test_epaisseur_est_la_plus_petite_possible)
    verifier("le bandeau ne monte pas sur le front", test_bandeau_ne_monte_pas_sur_le_front)
    verifier("la longueur depasse les coins des yeux", test_longueur_depasse_les_coins_des_yeux)
    verifier("le bandeau suit l'inclinaison de la tete",
             test_bandeau_suit_l_inclinaison_de_la_tete)

    print("\n2. Detection de bout en bout (visages dessines)")
    verifier("detection puis pose du bandeau", test_detection_de_bout_en_bout)

    echecs = [intitule for reussi, intitule in resultats if not reussi]
    print("\n" + "=" * 72)
    if echecs:
        print("%d test(s) en echec sur %d." % (len(echecs), len(resultats)))
        return 1
    print("Les %d tests passent." % len(resultats))
    print("\nPour juger le reperage sur vos propres photos :")
    print("    python tester_bandeau.py --photos CHEMIN/DU/DOSSIER")
    return 0


if __name__ == "__main__":
    sys.exit(main())
