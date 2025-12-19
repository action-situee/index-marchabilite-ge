import click
from .etl import check_project, prepare_network, prepare_features, filter_features, aggregate_index
@cli.command()
@click.option('--config', default=None, help='Chemin vers un fichier de configuration JSON (optionnel)')
def check(config):
    """Vérifie la structure du projet et la présence des fichiers/dossiers nécessaires."""
    import json
    config_dict = None
    if config:
        with open(config, 'r') as f:
            config_dict = json.load(f)
    check_project(config_dict)

@click.group()
def cli():
    """xyt-walkability: ETL pipeline for walkability index."""
    pass

@cli.command()
@click.option('--input', required=True, help='Input path')
@click.option('--output', required=True, help='Output path')
@click.option('--params', default=None, help='Extra parameters as JSON string')
def prepare_network_cmd(input, output, params):
    """Step 0: Prepare the pedestrian network."""
    prepare_network(input, output, params)

@cli.command()
@click.option('--input', required=True, help='Input path')
@click.option('--output', required=True, help='Output path')
@click.option('--params', default=None, help='Extra parameters as JSON string')
def prepare_features_cmd(input, output, params):
    """Step 1: Prepare features for the network."""
    prepare_features(input, output, params)

@cli.command()
@click.option('--input', required=True, help='Input path')
@click.option('--output', required=True, help='Output path')
@click.option('--params', default=None, help='Extra parameters as JSON string')
def filter_features_cmd(input, output, params):
    """Step 2: Filter/validate features (manual step possible)."""
    filter_features(input, output, params)

@cli.command()
@click.option('--input', required=True, help='Input path')
@click.option('--output', required=True, help='Output path')
@click.option('--params', default=None, help='Extra parameters as JSON string')
def aggregate_index_cmd(input, output, params):
    """Step 3: Aggregate and compute walkability index."""
    aggregate_index(input, output, params)

if __name__ == '__main__':
    cli()
