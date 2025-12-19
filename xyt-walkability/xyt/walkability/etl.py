from .check_project import check_project_structure
from .config import get_default_config
from .prepare_network import prepare_network
from .prepare_features import prepare_features
from .filter_features import filter_features
from .aggregate_index import aggregate_index
def check_project(config=None):
    """
    Vérifie la structure du projet et la présence des fichiers/dossiers nécessaires.
    Args:
        config (dict, optional): Configuration du projet.
    Returns:
        missing (list): Liste des éléments manquants.
    """
    if config is None:
        config = get_default_config()
    missing = check_project_structure(config)
    if missing:
        for m in missing:
            print(m)
        raise RuntimeError("Structure du projet incomplète. Voir messages ci-dessus.")
    print("Structure du projet OK.")
"""
ETL pipeline for walkability index calculation.
Each function corresponds to a processing step.
"""


# Les fonctions sont désormais importées de modules dédiés pour chaque étape du pipeline ETL.
