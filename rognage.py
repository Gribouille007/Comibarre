"""
Rognage d'une photo (etape de tri et mode revue).

Le cadre est trace a l'ecran sur la photo telle qu'elle est affichee : remise
dans le bon sens grace aux donnees d'orientation EXIF, puis eventuellement
pivotee par l'utilisateur pour mieux l'examiner (touche R). Cette rotation
d'examen reste purement visuelle (section 8.1) : seul le rognage est
enregistre, et la photo garde son sens d'origine.

Le meme calcul sert deux fois : pour montrer tout de suite la photo rognee a
l'ecran, et pour l'enregistrer, en arriere-plan, a partir du fichier.
"""

from images import charger_image, enregistrer_au_format_origine, format_origine


def cadre_dans_le_sens_d_origine(cadre, rotation_affichage, largeur, hauteur):
    """Ramene un cadre trace sur la photo pivotee dans le repere de la photo d'origine.

    Faire pivoter toute la photo pour la rogner, puis la remettre dans son
    sens, serait lent sur une grande photo. Il revient exactement au meme, et
    c'est instantane, de faire tourner le cadre dans l'autre sens.

    cadre              : (gauche, haut, droite, bas) sur la photo pivotee.
    rotation_affichage : 0, 90, 180 ou 270 degres, dans le sens des aiguilles
                         d'une montre.
    largeur, hauteur   : dimensions de la photo d'origine, NON pivotee.

    Exemple du quart de tour (90 degres) : le haut de la photo d'origine se
    retrouve a droite de l'ecran, et son bord gauche en haut de l'ecran. La
    distance au bord droit de l'ecran devient donc la distance au haut de la
    photo, et la distance au haut de l'ecran la distance a son bord gauche.
    Les deux autres cas se raisonnent de la meme facon.
    """
    gauche, haut, droite, bas = cadre
    if rotation_affichage == 90:
        return (haut, hauteur - droite, bas, hauteur - gauche)
    if rotation_affichage == 180:
        return (largeur - droite, hauteur - bas, largeur - gauche, hauteur - haut)
    if rotation_affichage == 270:
        return (largeur - bas, gauche, largeur - haut, droite)
    return cadre


def rogner_image(image, cadre, rotation_affichage):
    """Rogne une image (dans son sens d'origine) selon un cadre trace sur la photo pivotee.

    Aucun pixel n'est recalcule : la photo rognee est un simple morceau de
    l'originale.
    """
    return image.crop(cadre_dans_le_sens_d_origine(cadre, rotation_affichage,
                                                   image.width, image.height))


def rogner_fichier(chemin, cadre, rotation_affichage):
    """Rogne la photo enregistree et la reenregistre sur place, dans son format.

    La photo est relue et remise dans le bon sens (EXIF), exactement comme
    elle l'etait a l'ecran, puis rognee par le meme calcul que l'affichage :
    le fichier obtenu correspond donc a ce que l'utilisateur voit.

    Cette fonction est executee en arriere-plan (voir ecritures.py). La copie
    de sauvegarde a deja ete faite par l'appelant.
    """
    format_image = format_origine(chemin)
    image = rogner_image(charger_image(chemin), cadre, rotation_affichage)
    enregistrer_au_format_origine(image, chemin, format_image)
