"""
Operations elementaires sur les fichiers et les dossiers, qui reessaient un
court instant quand le systeme refuse.

Sous Windows, un fichier ouvert par un autre programme ne peut etre ni
deplace, ni renomme, ni remplace. Or une photo peut etre lue au meme moment
par un autre fil du logiciel (chargement anticipe, detection des visages), par
l'antivirus, par l'explorateur qui fabrique ses vignettes, ou par OneDrive qui
l'envoie en ligne. Ces lectures ne durent en general qu'un instant : plutot
que d'echouer tout de suite, on reessaie pendant deux secondes, puis l'erreur
remonte a l'appelant, qui previent l'utilisateur.

Aucune de ces fonctions n'ecrase un fichier sans que l'appelant l'ait voulu :
`deplacer_fichier` refuse une destination deja prise, sur tous les systemes.
"""

import errno
import json
import os
import time

# 40 essais espaces de 0,05 seconde : deux secondes en tout.
NOMBRE_D_ESSAIS = 40
PAUSE_ENTRE_ESSAIS = 0.05


def _reessayer(operation, *arguments):
    """Execute operation(*arguments), en reessayant tant que le systeme refuse l'acces."""
    for _ in range(NOMBRE_D_ESSAIS - 1):
        try:
            return operation(*arguments)
        except PermissionError:
            time.sleep(PAUSE_ENTRE_ESSAIS)
    return operation(*arguments)    # dernier essai : cette fois, l'erreur remonte


def deplacer_fichier(source, destination):
    """Deplace un fichier par un simple renommage, tout ou rien.

    `shutil.move` ne convient pas ici. Quand le renommage echoue, parce que le
    chargement anticipe ou la detection des visages lit justement la photo,
    il se rabat sur une copie suivie d'un effacement de l'original ; or
    l'effacement echoue pour la meme raison. La photo se retrouvait alors en
    double : rangee dans le dossier de tri, mais toujours presente dans le
    dossier source. Un renommage, lui, est tout ou rien : soit la photo a
    change de dossier, soit elle n'a pas bouge. Les dossiers de tri etant
    places dans le dossier de l'evenement, sur le meme disque, il suffit
    toujours.

    La destination ne doit pas exister : `os.rename` la remplacerait sans
    rien dire sous macOS et sous Linux (et refuserait sous Windows). On
    refuse donc partout de la meme facon, par FileExistsError, pour qu'aucune
    photo ne soit jamais ecrasee.
    """
    if os.path.exists(destination):
        raise FileExistsError(errno.EEXIST, "Un fichier porte deja ce nom", destination)
    _reessayer(os.rename, source, destination)


def remplacer_fichier(source, destination):
    """Comme os.replace (la destination est remplacee), en reessayant si Windows refuse."""
    _reessayer(os.replace, source, destination)


def supprimer_fichier(chemin):
    """Comme os.remove, en reessayant si Windows refuse."""
    _reessayer(os.remove, chemin)


def renommer_dossier(chemin, nouveau_nom):
    """Renomme un dossier sans le changer de place. Renvoie son nouveau chemin.

    Leve FileExistsError si un autre dossier porte deja ce nom, et OSError si
    le systeme refuse, par exemple parce qu'un fichier du dossier est ouvert
    par un autre programme.

    Un simple changement de majuscules (« vacances » -> « Vacances ») est
    accepte : sous Windows et macOS, les deux noms designent le meme dossier,
    et os.path.exists le dirait deja pris, a tort ; `samefile` le reconnait.
    """
    nouveau_chemin = os.path.join(os.path.dirname(chemin), nouveau_nom)
    if os.path.exists(nouveau_chemin) and not os.path.samefile(chemin, nouveau_chemin):
        raise FileExistsError(errno.EEXIST, "Un dossier porte deja ce nom", nouveau_chemin)
    _reessayer(os.rename, chemin, nouveau_chemin)
    return nouveau_chemin


def lire_json(chemin):
    """Relit un fichier JSON ecrit par ecrire_json.

    « utf-8-sig » accepte aussi un fichier retouche avec le Bloc-notes de
    Windows, qui ajoute en tete une marque invisible : il etait refuse.
    """
    with open(chemin, "r", encoding="utf-8-sig") as fichier:
        return json.load(fichier)


def ecrire_json(chemin, donnees):
    """Ecrit un fichier JSON sans jamais laisser un fichier a moitie ecrit.

    L'ecriture passe par un fichier temporaire, qui remplace ensuite l'ancien
    d'un seul coup : une coupure de courant en pleine ecriture laisse donc
    soit l'ancienne version, soit la nouvelle, jamais un melange illisible.
    Le texte est prepare d'un bloc puis ecrit en une fois : c'est cinq fois
    plus rapide que json.dump, qui ecrit morceau par morceau. Le fichier de
    suivi etant reecrit a chaque touche, la difference se sent.
    """
    texte = json.dumps(donnees, ensure_ascii=False, indent=2)
    chemin_temporaire = chemin + ".tmp"
    try:
        _reessayer(_ecrire_texte, chemin_temporaire, texte)
        remplacer_fichier(chemin_temporaire, chemin)
    except OSError:
        # L'ancien fichier est intact ; le temporaire ne doit pas rester.
        try:
            os.remove(chemin_temporaire)
        except OSError:
            pass
        raise


def _ecrire_texte(chemin, texte):
    with open(chemin, "w", encoding="utf-8") as fichier:
        fichier.write(texte)
