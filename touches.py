"""
Les touches du clavier dans la fenetre de tri : celles que le logiciel se
reserve, et la reconnaissance d'une touche de tri quelle que soit la
disposition du clavier.
"""

# Lettres deja prises dans la fenetre de tri, avec leur role. Elles ne peuvent
# pas servir a ranger une photo.
TOUCHES_RESERVEES = {
    "r": "pivoter",
    "c": "rogner",
    "n": "nouveau dossier",
}

# Sur un clavier AZERTY (France, Belgique), la rangee des chiffres donne
# & e " ' ( ... sans la touche Majuscule : les chiffres ne s'obtiennent
# qu'avec elle. Qui a choisi « 1 » pour ranger ses photos appuie pourtant sur la
# touche marquee 1, sans Majuscule. Ce tableau fait correspondre chaque
# caractere de cette rangee au chiffre imprime sur la meme touche.
#
# Les lettres accentuees sont ecrites par leur code (\u00e9...), les fichiers
# .py du projet n'en contenant aucune.
CHIFFRE_DE_LA_TOUCHE_AZERTY = {
    "&": "1",
    "\u00e9": "2",      # e accent aigu
    '"': "3",
    "'": "4",
    "(": "5",
    "-": "6",           # clavier francais
    "\u00a7": "6",      # signe paragraphe, clavier belge
    "\u00e8": "7",      # e accent grave
    "_": "8",           # clavier francais
    "!": "8",           # clavier belge
    "\u00e7": "9",      # c cedille
    "\u00e0": "0",      # a accent grave
}


def probleme_de_touche(touche):
    """Explique pourquoi `touche` ne peut pas ranger de photo, ou renvoie None."""
    if len(touche) != 1:
        return "une touche de tri est un seul caractere"
    if touche.isspace() or not touche.isprintable():
        return "une touche de tri doit etre une lettre, un chiffre ou un signe"
    role = TOUCHES_RESERVEES.get(touche.lower())
    if role is not None:
        return "la touche %s est reservee (%s)" % (touche.upper(), role)
    return None


def caracteres_de_la_touche(evenement):
    """Caracteres qu'une touche pressee peut designer, du plus exact au plus large.

    Le caractere produit vient en premier : si l'utilisateur a choisi « & »
    comme touche de tri, c'est bien ce dossier-la que designe la touche &. Le
    chiffre imprime sur la meme touche d'un clavier AZERTY ne vient qu'ensuite.
    Une touche qui ne produit aucun caractere (fleche, touche de fonction) ou
    un caractere de controle (Ctrl+lettre) ne designe rien.
    """
    caractere = evenement.char
    if len(caractere) != 1 or not caractere.isprintable():
        return []
    caracteres = [caractere]
    chiffre = CHIFFRE_DE_LA_TOUCHE_AZERTY.get(caractere)
    if chiffre is not None:
        caracteres.append(chiffre)
    return caracteres
