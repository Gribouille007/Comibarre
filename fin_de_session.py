"""
Fin de la session de tri (decision de l'utilisateur, 16 novembre 2026).

Tant que la session n'est pas terminee, tout reste annulable : on peut quitter
le logiciel, le rouvrir, revenir sur n'importe quelle photo et defaire ce
qu'on lui a fait. Pour cela, le dossier de l'evenement garde une copie intacte
de chaque photo modifiee, et le suivi garde la liste des actions.

Le bouton « Terminer la session » du menu rend le tri definitif :

1. les copies intactes sont effacees, et la liste des actions est videe : plus
   rien ne peut etre annule ;
2. les dossiers de tri restes vides sont supprimes du disque. Ils restent dans
   la liste de l'evenement : si l'on y range une photo plus tard, le dossier
   est recree tout seul.

Les versions sans barre (dossiers « Sans-barre ») ne sont pas concernees :
elles font partie du resultat du tri.
"""

import os
import shutil

from fichiers import supprimer_fichier

# Fichiers que les systemes deposent d'eux-memes dans les dossiers qu'on a
# ouverts. Ils ne comptent pas : un dossier qui ne contient qu'eux est vide.
FICHIERS_DU_SYSTEME = {".ds_store", "thumbs.db", "desktop.ini"}

# Dossiers du logiciel supprimes eux aussi s'ils sont vides.
NOMS_DOSSIERS_A_PART = ("RAW", "Videos")


def _est_du_systeme(nom_fichier):
    return nom_fichier.lower() in FICHIERS_DU_SYSTEME or nom_fichier.startswith("._")


def est_vide(chemin_dossier):
    """Le dossier ne contient-il aucun fichier de l'utilisateur, sous-dossiers compris ?"""
    for _, _, fichiers in os.walk(chemin_dossier):
        if any(not _est_du_systeme(nom) for nom in fichiers):
            return False
    return True


def dossiers_vides(suivi):
    """Noms des dossiers de l'evenement (tri, RAW, Videos) presents sur le disque et vides."""
    noms = list(suivi.noms_dossiers_tri) + [nom for nom in NOMS_DOSSIERS_A_PART
                                            if nom not in suivi.noms_dossiers_tri]
    return [nom for nom in noms
            if os.path.isdir(suivi.chemin_dossier(nom)) and est_vide(suivi.chemin_dossier(nom))]


def dossier_des_sauvegardes(suivi):
    """Dossier des copies intactes, ou None s'il ne doit pas etre touche.

    Un evenement cree par une tres ancienne version a pu donner ce nom a l'un
    de ses dossiers de tri, ou a une copie : le vider effacerait des photos
    de l'utilisateur. Le nom est refuse partout depuis ; par prudence, un tel
    dossier n'est de toute facon jamais vide.
    """
    dossier = suivi.chemin_dossier_temporaire()
    noms_de_l_utilisateur = {nom.lower() for nom in
                             suivi.noms_dossiers_tri + suivi.dossiers_dupliques}
    if os.path.basename(dossier).lower() in noms_de_l_utilisateur:
        return None
    return dossier


def bilan(suivi):
    """Ce que terminer la session changerait : de quoi l'annoncer avant de le faire.

    Renvoie {"annulables": nombre d'actions encore annulables,
             "octets": place prise par les copies intactes,
             "dossiers_vides": noms des dossiers qui seraient supprimes}.
    """
    octets = 0
    dossier = dossier_des_sauvegardes(suivi)
    if dossier is not None and os.path.isdir(dossier):
        with os.scandir(dossier) as entrees:
            for entree in entrees:
                try:
                    if entree.is_file():
                        octets += entree.stat().st_size
                except OSError:
                    pass
    return {"annulables": len(suivi.historique), "octets": octets,
            "dossiers_vides": dossiers_vides(suivi)}


def terminer(suivi):
    """Rend le tri definitif. Renvoie (dossiers supprimes, dossiers impossibles a supprimer).

    Le suivi est enregistre d'abord, sans son historique : si la suite
    s'interrompait, il ne designerait pas des copies intactes deja effacees.
    Peut lever OSError si le suivi ne s'enregistre pas ; rien n'est alors fait.
    """
    historique = suivi.donnees.get("historique", [])
    suivi.donnees["historique"] = []
    try:
        suivi.enregistrer()
    except OSError:
        suivi.donnees["historique"] = historique
        raise

    dossier = dossier_des_sauvegardes(suivi)
    if dossier is not None:
        shutil.rmtree(dossier, ignore_errors=True)

    supprimes = []
    refuses = []
    for nom in dossiers_vides(suivi):
        try:
            _supprimer_dossier_vide(suivi.chemin_dossier(nom))
            supprimes.append(nom)
        except OSError:
            refuses.append(nom)
    return supprimes, refuses


def _supprimer_dossier_vide(chemin_dossier):
    """Supprime un dossier qui ne contient que des fichiers du systeme.

    Seuls ces fichiers-la sont effaces, un par un ; `os.rmdir` refuse ensuite
    de supprimer un dossier ou il resterait autre chose. Meme appelee par
    erreur sur un dossier contenant une photo, cette fonction ne peut donc
    pas l'effacer.
    """
    for dossier, _, fichiers in os.walk(chemin_dossier, topdown=False):
        for nom in fichiers:
            if _est_du_systeme(nom):
                supprimer_fichier(os.path.join(dossier, nom))
        os.rmdir(dossier)


def taille_en_clair(octets):
    """« 350 Ko », « 12 Mo », « 1,4 Go »."""
    if octets < 1024 * 1024:
        return "%d Ko" % max(round(octets / 1024), 1 if octets else 0)
    if octets < 1024 ** 3:
        return "%d Mo" % round(octets / 1024 ** 2)
    return ("%.1f Go" % (octets / 1024 ** 3)).replace(".", ",")
