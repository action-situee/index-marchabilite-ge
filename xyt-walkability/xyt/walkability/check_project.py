import os
import sys
import pathlib

def check_project_structure(config):
    """
    Vérifie la structure du projet et la présence des fichiers/dossiers nécessaires.
    Args:
        config (dict): Dictionnaire de configuration (doit contenir au moins 'input_dir', 'output_dir', 'attribut_info_file').
    Returns:
        missing (list): Liste des éléments manquants.
    """
    missing = []
    input_dir = config.get('input_dir', 'Data/input')
    output_dir = config.get('output_dir', 'Data/output')
    attributs_dir = os.path.join(input_dir, 'attributs')
    attribut_info_file = config.get('attribut_info_file', os.path.join(attributs_dir, 'attribut_info.xlsx'))

    # Vérification des dossiers
    for d in [input_dir, output_dir, attributs_dir]:
        if not os.path.isdir(d):
            missing.append(f"Dossier manquant : {d}")
    # Vérification du fichier attribut_info.xlsx
    if not os.path.isfile(attribut_info_file):
        missing.append(f"Fichier manquant : {attribut_info_file}")
    # Création des dossiers de sortie si besoin
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    return missing

if __name__ == '__main__':
    import json
    config = json.load(open(sys.argv[1])) if len(sys.argv) > 1 else {}
    missing = check_project_structure(config)
    if missing:
        print("\n".join(missing))
        sys.exit(1)
    print("Structure du projet OK.")
