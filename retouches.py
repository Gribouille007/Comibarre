"""
Enregistrement des retouches d'une photo : bandeaux et rotation (sections 9.5
et 8.1).

Les deux se valident ensemble, par la touche Entree ou par une touche de tri.
Le meme calcul sert deux fois : pour garder tout de suite en memoire la photo
retouchee, et pour l'enregistrer, en arriere-plan, a partir du fichier.

L'ordre compte. Les bandeaux sont memorises dans le repere de la photo
d'origine, remise dans le bon sens (EXIF) mais pas encore pivotee : ils sont
donc incrustes d'abord, et la photo n'est pivotee qu'ensuite. Ils se retrouvent
ainsi exactement la ou l'utilisateur les a vus a l'ecran.
"""

from PIL import Image

from bandeaux import remplir_polygone_lisse
from images import charger_image, enregistrer_au_format_origine, format_origine

# Rotation d'examen (en degres, dans le sens des aiguilles d'une montre) ->
# operation Pillow equivalente. Pillow compte ses quarts de tour dans l'autre
# sens : un quart de tour a droite est donc son ROTATE_270. Ces operations
# deplacent les pixels sans les recalculer : la photo ne perd aucune nettete.
QUARTS_DE_TOUR = {
    90: Image.Transpose.ROTATE_270,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def appliquer_retouches(image, liste_bandeaux, rotation, echelle=1.0):
    """Renvoie une copie de l'image, bandeaux incrustes puis pivotee.

    `echelle` sert a retoucher l'apercu, plus petit que la photo : les
    bandeaux, exprimes en pixels de la photo entiere, sont ramenes a sa taille.
    """
    image = image.copy()
    for bandeau in liste_bandeaux:
        remplir_polygone_lisse(image, [(x * echelle, y * echelle)
                                       for x, y in bandeau.coins()])
    if rotation in QUARTS_DE_TOUR:
        image = image.transpose(QUARTS_DE_TOUR[rotation])
    return image


def enregistrer_retouches(chemin, liste_bandeaux, rotation):
    """Applique les retouches a la photo enregistree et la reenregistre sur place.

    La photo est relue et remise dans le bon sens (EXIF), exactement comme
    elle l'etait a l'ecran, puis retouchee par le meme calcul que l'affichage.

    Cette fonction est executee en arriere-plan (voir ecritures.py). La copie
    de sauvegarde a deja ete faite par l'appelant.
    """
    format_image = format_origine(chemin)
    image = appliquer_retouches(charger_image(chemin), liste_bandeaux, rotation)
    enregistrer_au_format_origine(image, chemin, format_image)
