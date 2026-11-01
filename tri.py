"""
Etape 1 - Le tri (section 8).

Les photos du dossier source defilent une par une en grand. Une touche du
clavier range la photo affichee dans l'un des dossiers de tri, et la photo
suivante apparait aussitot.

La fenetre est partagee avec le mode revue et decrite dans rangement.py ; a
l'etape de tri, les photos viennent du dossier source.
"""

from dossiers import photos_du_dossier
from rangement import FenetreRangement


def photos_a_trier(suivi):
    """Photos encore a la racine du dossier source, c'est-a-dire pas encore rangees."""
    return photos_du_dossier(suivi.dossier_source)


def preparer_tri(suivi):
    """Met dans la liste du tri les seules photos qui ne sont pas encore rangees.

    La liste etait autrefois fixee une fois pour toutes a la preparation, et
    contenait donc aussi les photos deja rangees. Rouvrir le tri pouvait
    alors montrer des photos venues d'un dossier de tri, et, une fois la
    liste parcourue jusqu'au bout, annoncer que tout etait trie alors que des
    photos attendaient encore dans le dossier source (passees avec Espace, ou
    ramenees par une annulation).

    Elle est donc refaite a chaque ouverture, a partir de ce qui se trouve
    reellement dans le dossier source : on reprend toujours a la premiere
    photo qui reste a ranger. Pendant la session, les photos rangees restent
    dans la liste, pour qu'on puisse y revenir avec la fleche gauche.

    L'historique repart de zero : ses positions renvoyaient a l'ancienne
    liste, et le Retour arriere aurait fait reapparaitre une photo rangee lors
    d'une session precedente. Un rangement d'une session precedente se
    corrige en mode revue.
    """
    tri = suivi.tri
    tri["photos"] = photos_a_trier(suivi)
    tri["position"] = 0
    tri["historique"] = []
    tri["terminee"] = not tri["photos"]
    suivi.enregistrer()


def lancer_tri(racine, suivi):
    """Ouvre l'etape de tri et attend sa fermeture.

    Arrive au bout des photos, l'utilisateur peut demander a repasser celles
    qui restent dans le dossier source (touche Entree sur l'ecran de fin) : la
    fenetre se ferme alors, et une nouvelle s'ouvre sur ces seules photos,
    avec une liste et un historique remis a neuf.
    """
    while True:
        preparer_tri(suivi)
        if not suivi.tri["photos"]:
            return
        fenetre = FenetreRangement(racine, suivi, suivi.tri, dossier_origine=None,
                                   titre="Tri - %s" % suivi.nom_evenement)
        racine.wait_window(fenetre.fenetre)
        if not fenetre.recommencer:
            return
