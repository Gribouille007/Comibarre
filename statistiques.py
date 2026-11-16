"""
Statistiques de la fenetre de tri (demande de l'utilisateur, 16 novembre 2026).

Le bas de la fenetre dit en permanence combien de photos restent a trier,
combien sont rangees, combien chaque dossier en contient, et a quel rythme on
avance.

Les compteurs sont lus sur le disque de temps en temps (ouverture de la
fenetre, nouveau dossier, ecran de fin) ; entre-temps, ils suivent chaque
rangement. Relire tous les dossiers a chaque touche ralentirait le tri sur un
disque lent.
"""

import time

from dossiers import photos_du_dossier

# Le rythme n'est annonce qu'apres quelques photos, faute de quoi il ne veut
# rien dire.
RANGEMENTS_AVANT_RYTHME = 5

# Une pause (telephone, cafe) n'est comptee que pour une minute, pour ne pas
# fausser le temps restant annonce.
PAUSE_MAXIMALE_COMPTEE = 60.0


class Statistiques:
    """Compte les photos de l'evenement, et mesure le rythme du tri."""

    def __init__(self, suivi, avec_rythme):
        """`avec_rythme` : vrai a l'etape de tri ; en revue, un rythme n'a pas de sens."""
        self.suivi = suivi
        self.avec_rythme = avec_rythme
        self.compteurs = {}            # nombre de photos de chaque dossier de tri
        self.a_trier = 0               # photos encore dans le dossier source
        self.rangees_cette_session = 0
        self.temps_de_tri = 0.0        # secondes passees a trier, pauses ecartees
        self.dernier_rangement = None
        self.compter()

    def compter(self):
        """Compte sur le disque les photos a trier et celles de chaque dossier de tri."""
        self.compteurs = {
            nom: len(photos_du_dossier(self.suivi.chemin_dossier(nom)))
            for nom in self.suivi.noms_dossiers_tri}
        self.a_trier = len(photos_du_dossier(self.suivi.dossier_source))

    def nombre(self, nom_dossier):
        return self.compteurs.get(nom_dossier, 0)

    def deplacement(self, depuis, vers):
        """Une photo est passee du dossier `depuis` au dossier `vers` (None : dossier source)."""
        for nom_dossier, ecart in ((depuis, -1), (vers, 1)):
            if nom_dossier is None:
                self.a_trier = max(self.a_trier + ecart, 0)
            elif nom_dossier in self.compteurs:
                self.compteurs[nom_dossier] = max(self.compteurs[nom_dossier] + ecart, 0)

    def rangement_fait(self):
        """Une photo vient d'etre rangee : le temps passe depuis la precedente est compte."""
        maintenant = time.monotonic()
        if self.dernier_rangement is not None:
            self.temps_de_tri += min(maintenant - self.dernier_rangement,
                                     PAUSE_MAXIMALE_COMPTEE)
        self.dernier_rangement = maintenant
        self.rangees_cette_session += 1

    def rangement_annule(self):
        self.rangees_cette_session = max(self.rangees_cette_session - 1, 0)

    def texte(self):
        """La ligne affichee : reste a trier, deja range, rythme, actions annulables."""
        rangees = sum(self.compteurs.values())
        total = rangees + self.a_trier
        morceaux = ["A trier : %d" % self.a_trier]
        if total:
            morceaux.append("Rangees : %d sur %d (%d %%)"
                            % (rangees, total, round(100 * rangees / total)))
        if self.rangees_cette_session:
            morceaux.append("Cette session : %d" % self.rangees_cette_session)
        if (self.avec_rythme and self.temps_de_tri > 0
                and self.rangees_cette_session >= RANGEMENTS_AVANT_RYTHME):
            # Le premier rangement n'a pas de duree : d'ou le « - 1 ».
            par_minute = (self.rangees_cette_session - 1) * 60 / self.temps_de_tri
            morceaux.append("Rythme : %d photos/min" % round(par_minute))
            if self.a_trier and par_minute > 0:
                morceaux.append("Temps restant : environ %s"
                                % duree_en_clair(self.a_trier / par_minute))
        annulables = len(self.suivi.historique)
        if annulables:
            morceaux.append("%d action(s) annulable(s)" % annulables)
        return "   |   ".join(morceaux)


def duree_en_clair(minutes):
    """« 12 min » ou « 1 h 05 » : une duree lisible d'un coup d'oeil."""
    if minutes < 1:
        return "moins d'une minute"
    if minutes < 60:
        return "%d min" % round(minutes)
    return "%d h %02d" % (minutes // 60, minutes % 60)
