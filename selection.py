"""
Habillage visuel du bandeau selectionne : son contour et ses poignees.

Tkinter dessine sans lissage : un cercle ou une ligne oblique traces
directement sur le canvas montrent leurs marches d'escalier. L'habillage est
donc peint ici avec Pillow, sur un calque agrandi puis reduit, exactement comme
les bords du bandeau lui-meme (voir bandeaux.remplir_polygone_lisse). Le trait
obtenu est net et adouci, et il est identique sur Windows, macOS et Linux.

Toutes les coordonnees recues sont exprimees en pixels de l'image affichee, et
non en pixels de la photo : les poignees gardent ainsi exactement la meme
taille a l'ecran, quelle que soit la taille de la photo ou de la fenetre.
"""

import math

from PIL import Image, ImageDraw

# Meme facteur de suréchantillonnage que pour les bandeaux : chaque pixel reel
# est calcule a partir de 4 x 4 petits pixels, ce qui donne 16 nuances de bord.
SURECHANTILLONNAGE = 4

# Tailles, en pixels ecran.
RAYON_POIGNEE = 6.0            # pastille blanche au bord du bandeau
RAYON_POIGNEE_SURVOLEE = 8.0   # la meme, quand la souris est dessus
EPAISSEUR_CONTOUR = 1.6
EPAISSEUR_OMBRE = 4.2          # trait sombre sous le contour blanc
TRAIT_POINTILLE = 4.0
VIDE_POINTILLE = 4.0

# Couleurs. Le contour est blanc, pose sur un trait sombre a peine visible :
# c'est ce qui le rend lisible aussi bien sur un ciel clair que sur un costume
# noir, sans avoir besoin de choisir une couleur voyante.
BLANC = (255, 255, 255)
NOIR = (0, 0, 0)
ACCENT = (10, 132, 255)        # bleu, reserve a la poignee de rotation

OPACITE_OMBRE = 80             # sur 255
OPACITE_CONTOUR = 235


def dessiner_habillage(image, coins, poignees, poignee_survolee=None):
    """Dessine le contour et les poignees sur l'image deja affichee a l'ecran.

    `coins`    : les quatre sommets du bandeau, en pixels ecran ;
    `poignees` : nom -> (x, y), en pixels ecran ;
    `poignee_survolee` : nom de la poignee sous la souris, ou None.

    Le dessin se fait en trois passes, du fond vers le dessus : l'ombre, puis
    le blanc, puis le bleu. Chaque passe peint une couleur unie a travers un
    masque lisse ; c'est ce qui evite les franges sombres que donnerait la
    reduction d'un calque en couleurs.
    """
    points_utiles = list(coins) + list(poignees.values())
    marge = RAYON_POIGNEE_SURVOLEE + EPAISSEUR_OMBRE + 2

    gauche = max(0, math.floor(min(x for x, _ in points_utiles) - marge))
    haut = max(0, math.floor(min(y for _, y in points_utiles) - marge))
    droite = min(image.width, math.ceil(max(x for x, _ in points_utiles) + marge))
    bas = min(image.height, math.ceil(max(y for _, y in points_utiles) + marge))
    if droite <= gauche or bas <= haut:
        return      # bandeau entierement hors de la partie visible

    echelle = SURECHANTILLONNAGE
    taille_agrandie = ((droite - gauche) * echelle, (bas - haut) * echelle)

    def agrandir(point):
        """Passe d'un point ecran au meme point sur le calque agrandi."""
        return ((point[0] - gauche) * echelle, (point[1] - haut) * echelle)

    contour = [agrandir(point) for point in coins]
    contour_ferme = contour + [contour[0]]

    # Le trait pointille part du milieu du bord haut du bandeau : les deux
    # premiers coins sont ceux de ce bord (voir Bandeau.coins).
    milieu_haut = ((contour[0][0] + contour[1][0]) / 2,
                   (contour[0][1] + contour[1][1]) / 2)

    # --- Passe 1 : l'ombre, un peu plus large que tout le reste ------------
    ombre = Image.new("L", taille_agrandie, 0)
    dessin = ImageDraw.Draw(ombre)
    dessin.line(contour_ferme, fill=255,
                width=max(1, round(EPAISSEUR_OMBRE * echelle)), joint="curve")
    for nom, point in poignees.items():
        _disque(dessin, agrandir(point),
                (_rayon(nom, poignee_survolee) + 1.0) * echelle, 255)
    _peindre(image, ombre, NOIR, OPACITE_OMBRE, (gauche, haut, droite, bas))

    # --- Passe 2 : le contour blanc, le pointille et les pastilles ---------
    blanc = Image.new("L", taille_agrandie, 0)
    dessin = ImageDraw.Draw(blanc)
    dessin.line(contour_ferme, fill=255,
                width=max(1, round(EPAISSEUR_CONTOUR * echelle)), joint="curve")
    if "rotation" in poignees:
        _ligne_pointillee(dessin, milieu_haut, agrandir(poignees["rotation"]),
                          max(1, round(EPAISSEUR_CONTOUR * echelle)), echelle)
    for nom, point in poignees.items():
        _disque(dessin, agrandir(point), _rayon(nom, poignee_survolee) * echelle, 255)
    _peindre(image, blanc, BLANC, OPACITE_CONTOUR, (gauche, haut, droite, bas))

    # --- Passe 3 : le point bleu de la poignee de rotation, et de la -------
    #               poignee survolee, pour montrer ce que l'on tient.
    accent = Image.new("L", taille_agrandie, 0)
    dessin = ImageDraw.Draw(accent)
    a_du_bleu = False
    for nom, point in poignees.items():
        if nom == "rotation" or nom == poignee_survolee:
            _disque(dessin, agrandir(point),
                    _rayon(nom, poignee_survolee) * 0.45 * echelle, 255)
            a_du_bleu = True
    if a_du_bleu:
        _peindre(image, accent, ACCENT, 255, (gauche, haut, droite, bas))


def _rayon(nom, poignee_survolee):
    return RAYON_POIGNEE_SURVOLEE if nom == poignee_survolee else RAYON_POIGNEE


def _disque(dessin, centre, rayon, valeur):
    x, y = centre
    dessin.ellipse([x - rayon, y - rayon, x + rayon, y + rayon], fill=valeur)


def _ligne_pointillee(dessin, depart, arrivee, largeur, echelle):
    """Trace une ligne en pointilles reguliers entre deux points du calque."""
    dx = arrivee[0] - depart[0]
    dy = arrivee[1] - depart[1]
    longueur = math.hypot(dx, dy)
    if longueur < 1:
        return
    pas_plein = TRAIT_POINTILLE * echelle
    pas_vide = VIDE_POINTILLE * echelle

    parcouru = 0.0
    while parcouru < longueur:
        fin = min(parcouru + pas_plein, longueur)
        dessin.line([(depart[0] + dx * parcouru / longueur,
                      depart[1] + dy * parcouru / longueur),
                     (depart[0] + dx * fin / longueur,
                      depart[1] + dy * fin / longueur)],
                    fill=255, width=largeur)
        parcouru = fin + pas_vide


def _peindre(image, masque_agrandi, couleur, opacite, boite):
    """Reduit le masque a la taille reelle puis peint la couleur a travers lui.

    La reduction BOX fait la moyenne exacte des petits pixels : un pixel du
    bord a moitie couvert devient a moitie opaque, ce qui adoucit le trait.
    """
    gauche, haut, droite, bas = boite
    masque = masque_agrandi.resize((droite - gauche, bas - haut), Image.BOX)
    if opacite < 255:
        masque = masque.point(lambda valeur: valeur * opacite // 255)
    image.paste(couleur, boite, masque)
