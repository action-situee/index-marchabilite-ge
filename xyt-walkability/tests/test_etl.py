
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from xyt.walkability.prepare_network import prepare_network
from xyt.walkability.prepare_features import prepare_features
from xyt.walkability.filter_features import filter_features
from xyt.walkability.aggregate_index import aggregate_index

def test_imports():
    assert callable(prepare_network)
    assert callable(prepare_features)
    assert callable(filter_features)
    assert callable(aggregate_index)
