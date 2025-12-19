import os

def get_default_config():
    """
    Retourne la configuration par défaut du projet.
    """
    return {
        'input_dir': os.path.join('Data', 'input'),
        'output_dir': os.path.join('Data', 'output'),
        'attribut_info_file': os.path.join('Data', 'input', 'attributs', 'attribut_info.xlsx'),
    }
