"""
Demarrage du logiciel, avec installation automatique des bibliotheques.

    python demarrer.py

C'est la maniere la plus simple de lancer le programme : ce fichier se charge
de tout. Au premier lancement, il cree l'environnement isole (le dossier
`venv/`), y installe les bibliotheques listees dans `requirements.txt`, puis
ouvre la fenetre du logiciel. Aux lancements suivants, il ne reinstalle rien et
ouvre directement la fenetre.

Il n'utilise que ce qui est fourni d'origine avec Python : il peut donc
s'executer avant toute installation.

Options :
    --verifier      installe si besoin, puis lance les verifications au lieu du logiciel
    --reinstaller   efface l'environnement et le refabrique entierement
"""

import hashlib
import os
import shutil
import subprocess
import sys

VERSION_MINIMALE = (3, 11)

DOSSIER = os.path.dirname(os.path.abspath(__file__))
DOSSIER_VENV = os.path.join(DOSSIER, "venv")
REQUIREMENTS = os.path.join(DOSSIER, "requirements.txt")

# Empreinte de la liste des bibliotheques telle qu'elle etait lors de la
# derniere installation reussie. Tant qu'elle n'a pas change, il n'y a rien a
# refaire : le lancement est alors immediat.
TEMOIN = os.path.join(DOSSIER_VENV, "bibliotheques_installees.txt")


def python_du_venv():
    """Chemin de l'interpreteur Python a l'interieur de l'environnement isole."""
    if os.name == "nt":
        return os.path.join(DOSSIER_VENV, "Scripts", "python.exe")
    return os.path.join(DOSSIER_VENV, "bin", "python")


def empreinte_des_bibliotheques():
    with open(REQUIREMENTS, "rb") as fichier:
        return hashlib.sha256(fichier.read()).hexdigest()


def deja_installe():
    if not os.path.isfile(python_du_venv()) or not os.path.isfile(TEMOIN):
        return False
    with open(TEMOIN, encoding="utf-8") as fichier:
        return fichier.read().strip() == empreinte_des_bibliotheques()


def verifier_la_version_de_python():
    if sys.version_info < VERSION_MINIMALE:
        arreter("Ce logiciel demande Python %d.%d ou plus recent.\n"
                "Vous utilisez Python %d.%d (%s).\n"
                "Installez une version plus recente depuis https://www.python.org/downloads/"
                % (VERSION_MINIMALE[0], VERSION_MINIMALE[1],
                   sys.version_info[0], sys.version_info[1], sys.executable))


def verifier_tkinter():
    """Tkinter est fourni avec Python, sauf sur certaines installations Linux."""
    try:
        import tkinter        # noqa: F401
        return
    except ImportError:
        pass

    if sys.platform == "darwin":
        conseil = "  brew install python-tk"
    elif os.name == "nt":
        conseil = ("  Relancez l'installateur de Python et cochez\n"
                   "  « tcl/tk and IDLE » dans les options.")
    else:
        conseil = ("  sudo apt install python3-tk        (Debian, Ubuntu)\n"
                   "  sudo dnf install python3-tkinter   (Fedora)\n"
                   "  sudo pacman -S tk                  (Arch)")
    arreter("L'interface graphique de Python (Tkinter) n'est pas installee.\n"
            "Pour l'ajouter :\n" + conseil)


def fabriquer_l_environnement():
    """Cree le dossier venv/, un Python a part, propre a ce logiciel.

    Les bibliotheques y sont installees sans toucher au Python du systeme : on
    peut effacer ce dossier a tout moment sans rien casser ailleurs.
    """
    print("Preparation de l'environnement (une seule fois)...")
    try:
        import venv
        venv.EnvBuilder(with_pip=True, clear=True).create(DOSSIER_VENV)
    except Exception as erreur:
        conseil = ""
        if sys.platform.startswith("linux"):
            conseil = ("\nSur Debian ou Ubuntu, le module manque souvent :\n"
                       "  sudo apt install python3-venv")
        arreter("Impossible de creer l'environnement : %s%s" % (erreur, conseil))


def installer_les_bibliotheques():
    """Installe pillow, pillow-heif et opencv dans l'environnement isole."""
    python = python_du_venv()
    print("Installation des bibliotheques (cela peut prendre une minute)...")
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip", "--quiet"],
                   check=False)

    resultat = subprocess.run([python, "-m", "pip", "install", "-r", REQUIREMENTS])
    if resultat.returncode != 0:
        # Les versions exactes de requirements.txt n'existent pas forcement pour
        # ce systeme ou cette version de Python. On retente alors sans imposer
        # de version : le logiciel fonctionne avec les versions recentes.
        print("\nLes versions exactes ne sont pas disponibles ici.")
        print("Nouvel essai avec les versions les plus recentes...")
        resultat = subprocess.run([python, "-m", "pip", "install"]
                                  + noms_sans_version())
        if resultat.returncode != 0:
            arreter("L'installation des bibliotheques a echoue.\n"
                    "Verifiez votre connexion a Internet, puis relancez.")

    with open(TEMOIN, "w", encoding="utf-8") as fichier:
        fichier.write(empreinte_des_bibliotheques())


def noms_sans_version():
    """Les noms des bibliotheques de requirements.txt, sans le numero de version."""
    noms = []
    with open(REQUIREMENTS, encoding="utf-8") as fichier:
        for ligne in fichier:
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#"):
                noms.append(ligne.split("==")[0].split(">=")[0].strip())
    return noms


def lancer(script):
    """Lance un script du projet avec le Python de l'environnement isole."""
    resultat = subprocess.run([python_du_venv(), os.path.join(DOSSIER, script)],
                              cwd=DOSSIER)
    return resultat.returncode


def arreter(message):
    print("\n" + "-" * 70)
    print(message)
    print("-" * 70)
    attendre_avant_de_fermer()
    sys.exit(1)


def attendre_avant_de_fermer():
    """Garde la fenetre ouverte, quand le programme a ete lance par un double-clic."""
    if sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nAppuyez sur Entree pour fermer cette fenetre.")
        except (EOFError, KeyboardInterrupt):
            pass


def main():
    verifier_la_version_de_python()
    verifier_tkinter()

    if "--reinstaller" in sys.argv:
        shutil.rmtree(DOSSIER_VENV, ignore_errors=True)

    if not deja_installe():
        if not os.path.isfile(python_du_venv()):
            fabriquer_l_environnement()
        installer_les_bibliotheques()
        print("Installation terminee.\n")

    if "--verifier" in sys.argv:
        return lancer("verifier_installation.py")

    code = lancer("main.py")
    if code != 0:
        # Le logiciel s'est arrete sur une erreur : son message est au-dessus,
        # il faut laisser le temps de le lire.
        attendre_avant_de_fermer()
    return code


if __name__ == "__main__":
    sys.exit(main())
