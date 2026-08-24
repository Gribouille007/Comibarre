"""
Enregistrement de l'avancement et reprise de session (cahier des charges, section 10).

Tout l'etat du travail tient dans un unique fichier JSON place dans le dossier de
l'evenement. Ce fichier est reecrit apres chaque action de l'utilisateur, de sorte
que fermer le logiciel a n'importe quel moment ne fait jamais perdre plus que
l'action en cours.

Aucune base de donnees n'est utilisee : un simple fichier texte suffit largement
pour un seul utilisateur et un seul evenement.
"""

import json
import os

# Nom du fichier de suivi, cree a la racine du dossier de l'evenement.
NOM_FICHIER_SUIVI = "suivi.json"

# Dossier ou sont conservees les copies intactes des photos avant censure,
# pour permettre l'annulation (section 9.6). Vide a la fermeture du logiciel.
NOM_DOSSIER_TEMPORAIRE = "_temporaire_censure"


class Suivi:
    """Represente le fichier de suivi et donne acces a son contenu."""

    def __init__(self, dossier_evenement, donnees):
        self.dossier_evenement = dossier_evenement
        self.donnees = donnees

    # ------------------------------------------------------------------
    # Creation, chargement, enregistrement
    # ------------------------------------------------------------------

    @classmethod
    def creer(cls, dossier_source, nom_evenement, dossiers_tri):
        """Construit un suivi tout neuf pour un evenement qui demarre.

        dossiers_tri est une liste de quatre dictionnaires {"nom", "touche"}.
        """
        dossier_evenement = os.path.join(dossier_source, nom_evenement)
        donnees = {
            "version": 1,
            "nom_evenement": nom_evenement,
            "dossier_source": dossier_source,
            "dossiers_tri": dossiers_tri,
            # Passe a True une fois la preparation automatique effectuee ; elle
            # ne doit jamais etre rejouee ensuite (sections 5 et 10).
            "preparation_faite": False,
            "tri": {
                "photos": [],      # noms de fichiers, dans l'ordre d'affichage
                "position": 0,     # index de la photo courante
                "historique": [],  # rangements effectues, pour l'annulation
                "terminee": False,
            },
            "censure": {
                "dossier": None,   # nom du dossier de tri en cours de traitement
                "position": 0,
                "historique": [],  # validations effectuees, pour l'annulation
            },
        }
        return cls(dossier_evenement, donnees)

    @classmethod
    def charger(cls, dossier_evenement):
        """Relit le fichier de suivi d'un evenement deja commence."""
        chemin = os.path.join(dossier_evenement, NOM_FICHIER_SUIVI)
        with open(chemin, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)

        # Le dossier a pu etre deplace depuis la derniere session : on fait
        # confiance a l'emplacement reel plutot qu'aux chemins enregistres.
        suivi = cls(dossier_evenement, donnees)
        suivi.donnees["dossier_source"] = os.path.dirname(dossier_evenement)
        return suivi

    @staticmethod
    def existe(dossier_evenement):
        """Indique si le dossier choisi contient bien un evenement."""
        return os.path.isfile(os.path.join(dossier_evenement, NOM_FICHIER_SUIVI))

    def enregistrer(self):
        """Ecrit le fichier de suivi sur le disque.

        L'ecriture passe par un fichier temporaire puis un remplacement atomique :
        une coupure de courant en pleine ecriture ne peut donc pas laisser un
        fichier de suivi tronque, qui rendrait la reprise impossible.
        """
        os.makedirs(self.dossier_evenement, exist_ok=True)
        chemin = os.path.join(self.dossier_evenement, NOM_FICHIER_SUIVI)
        chemin_temporaire = chemin + ".tmp"
        with open(chemin_temporaire, "w", encoding="utf-8") as fichier:
            json.dump(self.donnees, fichier, ensure_ascii=False, indent=2)
        os.replace(chemin_temporaire, chemin)

    # ------------------------------------------------------------------
    # Acces simplifie aux informations les plus utilisees
    # ------------------------------------------------------------------

    @property
    def nom_evenement(self):
        return self.donnees["nom_evenement"]

    @property
    def dossier_source(self):
        return self.donnees["dossier_source"]

    @property
    def dossiers_tri(self):
        """Liste des quatre dictionnaires {"nom", "touche"}."""
        return self.donnees["dossiers_tri"]

    @property
    def noms_dossiers_tri(self):
        return [dossier["nom"] for dossier in self.dossiers_tri]

    @property
    def tri(self):
        return self.donnees["tri"]

    @property
    def censure(self):
        return self.donnees["censure"]

    def chemin_dossier_tri(self, nom_dossier):
        """Chemin complet de l'un des quatre dossiers de tri."""
        return os.path.join(self.dossier_evenement, nom_dossier)

    def chemin_dossier_temporaire(self):
        """Chemin du dossier des copies de sauvegarde de la censure."""
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
