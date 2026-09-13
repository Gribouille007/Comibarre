"""
Etape 1 - Le tri (section 8).

Les photos du dossier source defilent une par une en grand. Une touche du
clavier range la photo affichee dans l'un des quatre dossiers de tri, et la
photo suivante apparait aussitot.

La fenetre est partagee avec le mode revue et decrite dans rangement.py ; a
l'etape de tri, les photos viennent du dossier source.
"""

from rangement import FenetreRangement


def lancer_tri(racine, suivi):
    """Ouvre l'etape de tri et attend sa fermeture."""
    if not suivi.tri["photos"]:
        return
    fenetre = FenetreRangement(racine, suivi, suivi.tri, dossier_origine=None,
                               titre="Tri - %s" % suivi.nom_evenement)
    racine.wait_window(fenetre.fenetre)
