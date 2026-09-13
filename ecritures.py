"""
Enregistrement des photos modifiees, en arriere-plan (section 11.1).

Reencoder une grande photo prend du temps : un quart de seconde pour un JPEG,
plusieurs secondes pour un HEIC. Si la fenetre attendait la fin de chaque
enregistrement, elle se figerait a chaque validation. Les enregistrements sont
donc confies a un fil d'execution separe, qui les traite un par un, dans
l'ordre ou ils ont ete demandes, pendant que l'utilisateur passe deja a la
photo suivante.

Une seule regle a respecter : avant de toucher a un fichier depuis la fenetre
(le deplacer, le copier, le remettre en place), il faut attendre la fin de
son enregistrement s'il est encore en cours. C'est le role de `attendre`.
"""

import os
import queue
import threading
from tkinter import messagebox


class EcrituresEnArrierePlan:
    """File d'attente des enregistrements, traites un par un par un fil separe."""

    def __init__(self):
        self.file = queue.Queue()
        self.en_attente = []        # chemins des fichiers pas encore enregistres
        self.erreurs = []           # (chemin, message) des enregistrements rates
        self.signal = threading.Condition()
        self.fil = threading.Thread(target=self._travailler, daemon=True)
        self.fil.start()

    def ajouter(self, chemin, travail, *arguments):
        """Demande l'execution de travail(*arguments), qui enregistre le fichier `chemin`."""
        with self.signal:
            self.en_attente.append(chemin)
        self.file.put((chemin, travail, arguments))

    def attendre(self, chemin=None):
        """Attend la fin de l'enregistrement d'un fichier, ou de tous si chemin vaut None.

        Revient aussitot s'il n'y a rien en cours, ce qui est le cas le plus
        frequent.
        """
        with self.signal:
            if chemin is None:
                while self.en_attente:
                    self.signal.wait()
            else:
                while chemin in self.en_attente:
                    self.signal.wait()

    def erreurs_a_signaler(self):
        """Renvoie les enregistrements rates depuis le dernier appel."""
        with self.signal:
            erreurs = self.erreurs
            self.erreurs = []
        return erreurs

    def arreter(self):
        """Termine tous les enregistrements demandes, puis arrete le fil.

        L'attente n'est volontairement pas limitee dans le temps : fermer avant
        la fin ferait perdre une modification que l'utilisateur a validee.
        """
        self.file.put(None)
        self.fil.join()

    def _travailler(self):
        while True:
            demande = self.file.get()
            if demande is None:
                return
            chemin, travail, arguments = demande
            try:
                travail(*arguments)
            except Exception as erreur:
                # L'ecriture passe par un fichier temporaire (voir images.py) :
                # en cas d'echec, le fichier d'origine est reste intact.
                with self.signal:
                    self.erreurs.append((chemin, str(erreur) or type(erreur).__name__))
            with self.signal:
                self.en_attente.remove(chemin)
                self.signal.notify_all()


def signaler_les_echecs(ecritures, chargeur, fenetre):
    """Previent l'utilisateur de chaque enregistrement qui a echoue.

    La version modifiee gardee en memoire par le chargeur ne correspond alors
    plus au fichier : elle est oubliee, pour que la photo soit relue telle
    qu'elle est reellement sur le disque.
    """
    for chemin, message in ecritures.erreurs_a_signaler():
        chargeur.oublier_fichier(chemin)
        messagebox.showerror(
            "Enregistrement impossible",
            "La photo « %s » n'a pas pu etre enregistree :\n%s\n\n"
            "Le fichier d'origine est reste intact." % (os.path.basename(chemin), message),
            parent=fenetre)
