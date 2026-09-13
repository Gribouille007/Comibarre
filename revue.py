"""
Mode revue - reclasser les photos d'un dossier deja trie (section 8 bis).

On repasse une a une les photos de l'un des quatre dossiers de tri. Si une
photo n'est pas a sa place, la touche d'un autre dossier l'y deplace aussitot ;
la touche du dossier revu la laisse ou elle est.

La fenetre est la meme qu'a l'etape de tri (voir rangement.py) : seules
changent les photos presentees.
"""

from dossiers import photos_du_dossier
from rangement import FenetreRangement


def preparer_revue(suivi, nom_dossier):
    """Met a jour, dans le fichier de suivi, la liste des photos a revoir.

    Meme principe que pour la censure (section 9.7) : rouvrir le meme dossier
    retombe sur la photo ou l'on s'etait arrete. On repart en revanche du debut
    si l'on change de dossier, ou si le dossier avait deja ete revu en entier.
    """
    revue = suivi.revue
    photos = photos_du_dossier(suivi.chemin_dossier(nom_dossier))

    if (revue["dossier"] != nom_dossier or not revue["photos"]
            or revue["position"] >= len(revue["photos"])):
        revue["dossier"] = nom_dossier
        revue["photos"] = photos
        revue["position"] = 0
        revue["historique"] = []
        revue["terminee"] = False
    else:
        # Des photos ont pu etre rangees dans ce dossier depuis la derniere
        # fois, a l'etape de tri : on les ajoute a la fin de la liste. Les
        # photos deja listees gardent leur place, pour que la position et
        # l'historique d'annulation restent justes.
        deja_listees = set(revue["photos"])
        revue["photos"].extend(nom for nom in photos if nom not in deja_listees)

    suivi.enregistrer()


def lancer_revue(racine, suivi, nom_dossier):
    """Ouvre le mode revue sur un dossier de tri. Renvoie le nombre de photos."""
    preparer_revue(suivi, nom_dossier)
    if not suivi.revue["photos"]:
        return 0

    fenetre = FenetreRangement(racine, suivi, suivi.revue, dossier_origine=nom_dossier,
                               titre="Revue - %s / %s" % (suivi.nom_evenement, nom_dossier))
    racine.wait_window(fenetre.fenetre)
    return len(suivi.revue["photos"])
