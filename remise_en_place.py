"""
Photos revenues dans le dossier source apres avoir ete rangees.

Probleme constate par l'utilisateur sur un dossier synchronise par OneDrive
(octobre 2026) : apres un tri complet, des photos qu'il avait rangees se
trouvaient de nouveau dans le dossier source, et plus du tout dans leur
dossier de tri, sans qu'aucune erreur ait ete signalee. Le deplacement avait
reussi ; c'est la synchronisation qui l'a defait ensuite, parfois plusieurs
secondes plus tard (voir synchronisation.py).

Le fichier de suivi retient le dossier choisi pour chaque photo
(Suivi.rangements). Une photo presente a la racine du dossier source alors
qu'elle avait ete rangee est donc une photo revenue : le logiciel le dit, et
propose de la remettre dans son dossier.
"""

import filecmp
import os
from tkinter import messagebox

from dossiers import photos_du_dossier
from fichiers import deplacer_fichier, supprimer_fichier
from retouches import deplacer_sans_barre
from synchronisation import service_de_synchronisation

# Nombre maximal de photos citees par leur nom dans un message.
NOMBRE_CITE = 8


def photos_revenues(suivi):
    """Photos rangees, mais retrouvees a la racine du dossier source.

    Renvoie une liste de couples (nom de la photo, dossier ou elle avait ete
    rangee). Un rangement vers un dossier qui n'est plus un dossier de tri ne
    compte pas : il n'y a plus nulle part ou la remettre.
    """
    noms_dossiers = suivi.noms_dossiers_tri
    revenues = []
    for nom in photos_du_dossier(suivi.dossier_source):
        dossier = suivi.rangements.get(nom)
        if dossier in noms_dossiers:
            revenues.append((nom, dossier))
    return revenues


def remettre_en_place(suivi, revenues):
    """Range de nouveau les photos revenues. Renvoie les echecs : [(nom, raison)].

    Si le dossier de tri contient deja un fichier du meme nom, identique octet
    pour octet, la synchronisation a laisse la photo en double : l'exemplaire
    du dossier source est simplement efface, rien n'est perdu. S'il est
    different, rien n'est touche et l'echec est signale : aucune photo n'est
    jamais ecrasee.
    """
    echecs = []
    for nom, nom_dossier in revenues:
        depart = os.path.join(suivi.dossier_source, nom)
        arrivee = os.path.join(suivi.chemin_dossier(nom_dossier), nom)
        try:
            if os.path.exists(arrivee):
                if not filecmp.cmp(depart, arrivee, shallow=False):
                    echecs.append((nom, "un autre fichier du meme nom est deja dans "
                                        "« %s »" % nom_dossier))
                    continue
                supprimer_fichier(depart)
            else:
                os.makedirs(os.path.dirname(arrivee), exist_ok=True)
                deplacer_fichier(depart, arrivee)
                # Une version sans bandeaux restee a la racine suit la photo.
                deplacer_sans_barre(depart, arrivee)
        except OSError as erreur:
            echecs.append((nom, str(erreur)))
    return echecs


def proposer_de_remettre_en_place(parent, suivi):
    """Signale les photos revenues dans le dossier source, et propose de les ranger de nouveau.

    Non : elles restent a trier, et leur ancien rangement est oublie, pour ne
    pas etre propose de nouveau. A appeler avant d'etablir la liste des
    photos a trier.
    """
    revenues = photos_revenues(suivi)
    if not revenues:
        return

    service = service_de_synchronisation(suivi.dossier_source)
    if service:
        cause = ("C'est %s qui a annule leur deplacement : pendant le tri, mieux vaut "
                 "suspendre sa synchronisation." % service)
    else:
        cause = ("Leur deplacement a ete annule apres coup, probablement par un "
                 "service de synchronisation ou un autre programme.")

    if messagebox.askyesno(
            "Photos revenues dans le dossier source",
            "%d photo(s) que vous aviez rangee(s) se trouve(nt) de nouveau dans le "
            "dossier source :\n%s\n\n%s\n\n"
            "Les remettre dans leur dossier de tri ?\n"
            "(Non : elles vous seront proposees de nouveau au tri.)"
            % (len(revenues), _citer(revenues), cause),
            parent=parent):
        echecs = remettre_en_place(suivi, revenues)
        if echecs:
            messagebox.showwarning(
                "Photos laissees dans le dossier source",
                "%d photo(s) n'ont pas pu etre remise(s) en place, et restent a trier :\n%s"
                % (len(echecs), "\n".join("%s : %s" % echec for echec in echecs[:NOMBRE_CITE])),
                parent=parent)
            for nom, _ in echecs:
                suivi.noter_rangement(nom, None)
    else:
        for nom, _ in revenues:
            suivi.noter_rangement(nom, None)
    suivi.enregistrer()


def _citer(revenues):
    """Quelques lignes « 12.jpg -> A garder », suivies du nombre des autres."""
    lignes = ["   %s  ->  %s" % (nom, dossier) for nom, dossier in revenues[:NOMBRE_CITE]]
    if len(revenues) > NOMBRE_CITE:
        lignes.append("   ... et %d autre(s)" % (len(revenues) - NOMBRE_CITE))
    return "\n".join(lignes)
