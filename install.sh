#!/bin/bash

set -e

echo "[+] Clonage de SubEvilx..."
git clone https://github.com/tucommenceapousser/SubEvilx.git

echo "[+] Copie des fichiers SubEvilx dans le dossier courant..."
cp -r SubEvilx/* ./

echo "[+] Suppression du dossier SubEvilx..."
rm -rf SubEvilx

echo "[+] Installation des dépendances Python..."
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "[-] Fichier requirements.txt introuvable."
fi

echo "[✓] Installation terminée ! Tu peux maintenant lancer le script principal."
