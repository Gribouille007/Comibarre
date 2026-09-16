#!/bin/sh
# Lancement du logiciel sur macOS, par un double-clic dans le Finder.
# Le Finder n'execute pas les fichiers .sh : ce fichier ne sert qu'a appeler
# lancer.sh, qui fait tout le travail.
exec "$(dirname "$0")/lancer.sh" "$@"
