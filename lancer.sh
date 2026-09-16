#!/bin/sh
# Lance le logiciel sur macOS et sur Linux.
#
# Ce script cherche un Python assez recent, propose de l'installer s'il n'y en
# a pas, puis passe la main a demarrer.py, qui installe les bibliotheques et
# ouvre la fenetre.
#
# Sur macOS, double-cliquez plutot sur « lancer.command », qui appelle
# celui-ci : le Finder n'ouvre pas les fichiers .sh.

set -u
cd "$(dirname "$0")" || exit 1

VERSION_MINIMALE="3.11"

# --------------------------------------------------------------------------
# Trouver un Python utilisable
# --------------------------------------------------------------------------
# Plusieurs Python coexistent souvent sur une meme machine. On essaie les noms
# les plus precis d'abord, et on garde le premier qui est assez recent : celui
# de macOS, par exemple, est trop ancien et serait retenu a tort sans ce test.
trouver_python() {
    for candidat in python3.14 python3.13 python3.12 python3.11 python3 python
    do
        chemin=$(command -v "$candidat" 2>/dev/null) || continue
        if "$chemin" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
        then
            echo "$chemin"
            return 0
        fi
    done
    return 1
}

demander() {
    printf "%s [o/N] " "$1"
    read -r reponse
    case "$reponse" in
        o|O|oui|Oui|y|Y|yes) return 0 ;;
        *) return 1 ;;
    esac
}

# --------------------------------------------------------------------------
# Installer Python s'il manque
# --------------------------------------------------------------------------
installer_python_macos() {
    if command -v brew >/dev/null 2>&1; then
        echo "Homebrew est present sur cette machine."
        if demander "Installer Python (avec son interface graphique) via Homebrew ?"; then
            # python-tk installe Python et l'interface graphique Tkinter, qui
            # n'est pas fournie par le paquet python seul.
            brew install python-tk || brew install python || return 1
            return 0
        fi
        return 1
    fi
    echo "Homebrew n'est pas installe."
    echo "Vous pouvez soit l'installer (https://brew.sh), soit telecharger"
    echo "Python directement."
    if demander "Ouvrir la page de telechargement de Python ?"; then
        open "https://www.python.org/downloads/"
    fi
    return 1
}

installer_python_linux() {
    if command -v apt-get >/dev/null 2>&1; then
        commande="sudo apt-get install -y python3 python3-venv python3-tk"
    elif command -v dnf >/dev/null 2>&1; then
        commande="sudo dnf install -y python3 python3-tkinter"
    elif command -v pacman >/dev/null 2>&1; then
        commande="sudo pacman -S --needed python tk"
    elif command -v zypper >/dev/null 2>&1; then
        commande="sudo zypper install -y python3 python3-tk"
    else
        echo "Gestionnaire de paquets inconnu."
        echo "Installez Python $VERSION_MINIMALE ou plus recent, ainsi que Tkinter."
        return 1
    fi

    echo "Commande a executer : $commande"
    if demander "L'executer maintenant ? (votre mot de passe vous sera demande)"; then
        $commande || return 1
        return 0
    fi
    return 1
}

# --------------------------------------------------------------------------

PYTHON=$(trouver_python)
if [ -z "${PYTHON:-}" ]; then
    echo "Aucun Python $VERSION_MINIMALE ou plus recent n'a ete trouve."
    echo ""
    case "$(uname -s)" in
        Darwin) installer_python_macos ;;
        *)      installer_python_linux ;;
    esac

    PYTHON=$(trouver_python)
    if [ -z "${PYTHON:-}" ]; then
        echo ""
        echo "Python reste introuvable. Installez-le, puis relancez ce fichier."
        printf "Appuyez sur Entree pour fermer. "
        read -r _
        exit 1
    fi
fi

exec "$PYTHON" demarrer.py "$@"
