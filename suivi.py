"""
Enregistrement de l'avancement et reprise de session (cahier des charges, section 10).

Tout l'etat du travail tient dans un unique fichier JSON place dans le dossier de
l'evenement. Ce fichier est reecrit apres chaque action de l'utilisateur, de sorte
que fermer le logiciel a n'importe quel moment ne fait jamais perdre plus que
l'action en cours.

Aucune base de donnees n'est utilisee : un simple fichier texte suffit largement
pour un seul utilisateur et un seul evenement.

Deux organisations coexistent :

- version 2 (depuis le 26 octobre 2026) : le dossier de l'evenement EST le
  dossier source. Le logiciel le renomme du nom de l'evenement, et y cree les
  dossiers de tri ; les photos a trier attendent a sa racine ;
- version 1 (evenements plus anciens) : le dossier de l'evenement est un
  sous-dossier, a son nom, place dans le dossier source.

Les evenements de la version 1 se reprennent toujours, sans rien changer a
leur organisation.
"""

import os

from fichiers import ecrire_json, lire_json

# Nom du fichier de suivi, cree a la racine du dossier de l'evenement.
NOM_FICHIER_SUIVI = "suivi.json"

# Dossier ou sont conservees les copies intactes des photos avant censure ou
# rognage, pour permettre l'annulation (section 9.6). Vide a la fermeture de
# la fenetre.
NOM_DOSSIER_TEMPORAIRE = "_sauvegardes_temporaires"

# Version des fichiers de suivi ecrits par ce programme (voir l'entete).
VERSION = 2


class Suivi:
    """Represente le fichier de suivi et donne acces a son contenu."""

    def __init__(self, dossier_evenement, donnees):
        self.dossier_evenement = dossier_evenement
        self.donnees = donnees

    # ------------------------------------------------------------------
    # Creation, chargement, enregistrement
    # ------------------------------------------------------------------

    @classmethod
    def creer(cls, dossier_evenement, nom_evenement, dossiers_tri):
        """Construit un suivi tout neuf pour un evenement qui demarre.

        `dossier_evenement` est le dossier des photos lui-meme (version 2).
        `dossiers_tri` est une liste de dictionnaires {"nom", "touche"}.
        """
        donnees = {
            "version": VERSION,
            "nom_evenement": nom_evenement,
            "dossiers_tri": [{"nom": dossier["nom"], "touche": dossier["touche"]}
                             for dossier in dossiers_tri],
            # Copies de dossiers faites depuis le menu principal. Elles ne sont
            # pas des dossiers de tri, mais elles peuvent etre revues et
            # censurees comme les autres.
            "dossiers_dupliques": [],
            # Passe a True une fois la preparation automatique terminee ; elle
            # ne doit jamais etre rejouee ensuite (sections 5 et 10).
            "preparation_faite": False,
            "tri": {
                "photos": [],      # noms de fichiers, dans l'ordre d'affichage
                "position": 0,     # index de la photo courante
                "historique": [],  # rangements effectues, pour l'annulation
                "terminee": False,
            },
            "revue": Suivi._revue_vide(),
            # Mode barrer (pose de bandeaux sur les yeux) : active ou non par
            # la touche Tab, et retenu d'une photo et d'une session a l'autre.
            "mode_barrer": False,
            # Dossier de tri choisi pour chaque photo : voir `rangements`.
            "rangements": {},
        }
        return cls(dossier_evenement, donnees)

    @staticmethod
    def _revue_vide():
        return {
            "dossier": None,       # nom du dossier en cours de revue
            "photos": [],
            "position": 0,
            "historique": [],      # deplacements et rognages, pour l'annulation
            "terminee": False,
        }

    @classmethod
    def charger(cls, dossier_evenement):
        """Relit le fichier de suivi d'un evenement deja commence.

        Leve ValueError si le fichier ne ressemble pas a un fichier de suivi
        (tronque, ou modifie a la main), plutot que de laisser le programme
        s'arreter plus loin sur une cle manquante.
        """
        donnees = lire_json(os.path.join(dossier_evenement, NOM_FICHIER_SUIVI))
        if (not isinstance(donnees, dict)
                or not isinstance(donnees.get("dossiers_tri"), list)
                or not isinstance(donnees.get("tri"), dict)
                or not isinstance(donnees.get("nom_evenement"), str)
                or not all(isinstance(dossier, dict)
                           and isinstance(dossier.get("nom"), str)
                           and isinstance(dossier.get("touche"), str)
                           for dossier in donnees["dossiers_tri"])
                or not isinstance(donnees.get("revue", {}), dict)
                or not isinstance(donnees.get("dossiers_dupliques", []), list)
                or not isinstance(donnees.get("rangements", {}), dict)):
            raise ValueError("Le fichier de suivi est incomplet ou abime.")
        # Les cles d'etape manquantes sont completees plutot que refusees : un
        # fichier ecrit par une version plus ancienne peut ne pas toutes les
        # avoir, et le tri s'arretait sinon plus loin sur une cle absente.
        for etape in (donnees["tri"], donnees.setdefault("revue", cls._revue_vide())):
            for cle, valeur in (("photos", []), ("position", 0), ("historique", []),
                                ("terminee", False)):
                etape.setdefault(cle, valeur)
        return cls(dossier_evenement, donnees)

    @staticmethod
    def existe(dossier_evenement):
        """Indique si le dossier choisi contient bien un evenement."""
        return os.path.isfile(os.path.join(dossier_evenement, NOM_FICHIER_SUIVI))

    def enregistrer(self):
        """Ecrit le fichier de suivi sur le disque (voir fichiers.ecrire_json).

        L'ecriture reessaie un court instant si le fichier est occupe : OneDrive,
        par exemple, le lit pour l'envoyer en ligne a chaque modification.
        """
        os.makedirs(self.dossier_evenement, exist_ok=True)
        ecrire_json(os.path.join(self.dossier_evenement, NOM_FICHIER_SUIVI), self.donnees)

    # ------------------------------------------------------------------
    # Acces simplifie aux informations les plus utilisees
    # ------------------------------------------------------------------

    @property
    def nom_evenement(self):
        return self.donnees["nom_evenement"]

    @property
    def dossier_source(self):
        """Dossier dont la racine contient les photos a trier.

        Le chemin est deduit de l'emplacement reel du dossier de l'evenement,
        et non relu dans le fichier : l'evenement a pu etre deplace ou renomme
        depuis la derniere session.
        """
        if self.donnees.get("version", 1) >= 2:
            return self.dossier_evenement
        return os.path.dirname(self.dossier_evenement)

    @property
    def dossiers_tri(self):
        """Liste des dossiers de tri, dictionnaires {"nom", "touche"}."""
        return self.donnees["dossiers_tri"]

    @property
    def noms_dossiers_tri(self):
        return [dossier["nom"] for dossier in self.dossiers_tri]

    @property
    def dossiers_dupliques(self):
        """Noms des copies de dossiers faites depuis le menu principal.

        `setdefault` permet de relire sans erreur un fichier de suivi ecrit par
        une version precedente du logiciel, qui ne connaissait pas les copies.
        """
        return self.donnees.setdefault("dossiers_dupliques", [])

    def ajouter_dossier_duplique(self, nom_dossier):
        if nom_dossier not in self.dossiers_dupliques:
            self.dossiers_dupliques.append(nom_dossier)

    @property
    def noms_dossiers_censurables(self):
        """Dossiers que l'on peut passer en revue.

        Les dossiers de tri, plus les copies qui existent encore sur le disque.
        Les dossiers RAW et Videos en sont volontairement absents : leur contenu
        ne doit jamais etre modifie.
        """
        noms = list(self.noms_dossiers_tri)
        for nom in self.dossiers_dupliques:
            if nom not in noms and os.path.isdir(self.chemin_dossier(nom)):
                noms.append(nom)
        return noms

    @property
    def tri(self):
        return self.donnees["tri"]

    @property
    def revue(self):
        """Etat du mode revue.

        `setdefault` permet de relire sans erreur un fichier de suivi ecrit par
        une version precedente du logiciel, qui ne connaissait pas la revue.
        """
        return self.donnees.setdefault("revue", Suivi._revue_vide())

    @property
    def mode_barrer(self):
        """Le mode barrer est-il actif ? (False pour un suivi d'une version precedente)"""
        return self.donnees.get("mode_barrer", False)

    @mode_barrer.setter
    def mode_barrer(self, actif):
        self.donnees["mode_barrer"] = actif

    def chemin_dossier(self, nom_dossier):
        """Chemin complet d'un dossier range dans le dossier de l'evenement.

        Sert aussi bien aux dossiers de tri qu'aux copies faites depuis le
        menu principal.
        """
        return os.path.join(self.dossier_evenement, nom_dossier)

    def chemin_dossier_temporaire(self):
        """Chemin du dossier des copies de sauvegarde (censure et rognage)."""
        return os.path.join(self.dossier_evenement, NOM_DOSSIER_TEMPORAIRE)

    def dossier_tri_pour_touche(self, touche):
        """Renvoie le nom du dossier associe a une touche, ou None.

        La comparaison ignore la casse : la touche « a » et la touche « A »
        rangent dans le meme dossier.
        """
        for dossier in self.dossiers_tri:
            if dossier["touche"].lower() == touche.lower():
                return dossier["nom"]
        return None

    # ------------------------------------------------------------------
    # Ou chaque photo a ete rangee
    # ------------------------------------------------------------------

    @property
    def rangements(self):
        """Dossier de tri choisi pour chaque photo rangee : {nom de photo: nom de dossier}.

        Garde la trace des decisions de l'utilisateur, independamment de ce
        que contient le disque. C'est ce qui permet de reperer une photo
        rangee qu'un service de synchronisation a remise ensuite dans le
        dossier source (voir remise_en_place.py). `setdefault` : absent des
        suivis ecrits par une version precedente.
        """
        return self.donnees.setdefault("rangements", {})

    def noter_rangement(self, nom_fichier, nom_dossier):
        """Note le dossier ou la photo vient d'etre rangee ; None si elle revient a trier."""
        if nom_dossier is None:
            self.rangements.pop(nom_fichier, None)
        else:
            self.rangements[nom_fichier] = nom_dossier

    # ------------------------------------------------------------------
    # Modification de la liste des dossiers de tri
    # ------------------------------------------------------------------
    # Ces methodes ne touchent qu'au suivi : les dossiers eux-memes sont crees,
    # renommes ou supprimes sur le disque par l'appelant.

    def ajouter_dossier_tri(self, nom, touche):
        self.dossiers_tri.append({"nom": nom, "touche": touche})

    def renommer_dossier_tri(self, ancien_nom, nouveau_nom):
        """Fait suivre le nouveau nom d'un dossier de tri partout ou le suivi le cite.

        Les historiques d'annulation designent les dossiers par leur nom : sans
        cette mise a jour, annuler un rangement chercherait la photo dans un
        dossier qui n'existe plus sous ce nom.
        """
        for dossier in self.dossiers_tri:
            if dossier["nom"] == ancien_nom:
                dossier["nom"] = nouveau_nom
        for photo, dossier in self.rangements.items():
            if dossier == ancien_nom:
                self.rangements[photo] = nouveau_nom
        if self.revue["dossier"] == ancien_nom:
            self.revue["dossier"] = nouveau_nom
        for etat in (self.tri, self.revue):
            for action in etat["historique"]:
                for cle in ("dossier", "depuis", "emplacement"):
                    if action.get(cle) == ancien_nom:
                        action[cle] = nouveau_nom

    def changer_touche(self, nom_dossier, touche):
        for dossier in self.dossiers_tri:
            if dossier["nom"] == nom_dossier:
                dossier["touche"] = touche

    def retirer_dossier_tri(self, nom):
        """Retire un dossier de tri (vide) de la liste, et tout ce qui le cite."""
        self.donnees["dossiers_tri"] = [dossier for dossier in self.dossiers_tri
                                        if dossier["nom"] != nom]
        for photo in [photo for photo, dossier in self.rangements.items() if dossier == nom]:
            del self.rangements[photo]
        if self.revue["dossier"] == nom:
            self.donnees["revue"] = Suivi._revue_vide()
        for etat in (self.tri, self.revue):
            etat["historique"] = [action for action in etat["historique"]
                                  if nom not in (action.get("dossier"), action.get("depuis"),
                                                 action.get("emplacement"))]

    def ordonner_dossiers_tri(self, dossiers):
        """Remplace la liste par `dossiers` ({"nom", "touche"}), dans cet ordre."""
        self.donnees["dossiers_tri"] = [{"nom": dossier["nom"], "touche": dossier["touche"]}
                                        for dossier in dossiers]
