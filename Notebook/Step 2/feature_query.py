import ast
import pandas as pd

def make_feature_query(filter_column: str | None, filter_values: str | int | float | bool | None):
    """
    Construit une expression pour pandas.DataFrame.query() à partir de
    filter_column et filter_values (qui peut être scalaire ou une liste encodée).
    Retourne None si pas de filtre.
    """
    if not filter_column or pd.isna(filter_column) or pd.isna(filter_values):
        return None

    col = str(filter_column).strip()

    # Tenter d'interpréter une liste encodée
    if isinstance(filter_values, str):
        s = filter_values.strip()

        # True/False en string
        if s.lower() in ("true", "false"):
            val = True if s.lower() == "true" else False
            return f"`{col}` == {val}"

        # Liste encodée: "['a','b']"
        if s.startswith("[") and s.endswith("]"):
            try:
                lst = ast.literal_eval(s)
                if isinstance(lst, (list, tuple)):
                    # pandas.query supporte "col in @lst"
                    return f"`{col}` in @lst"
            except Exception:
                pass

        # Sinon chaîne simple
        return f"`{col}` == {repr(s)}"

    # Numérique/bool direct
    return f"`{col}` == {filter_values}"
