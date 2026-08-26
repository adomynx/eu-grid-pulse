"""Load raw DataFrames into the warehouse raw tables (Step 3).

Land data AS-IS here. Do not clean at this layer — the raw layer is an honest,
replayable copy of the source.
"""


def load_raw_load(df):
    """Step 3: write load DataFrame to raw_load. TODO: implement (SQLAlchemy / to_gbq)."""
    raise NotImplementedError("Implement in Step 3")


def load_raw_generation(df):
    """Step 3: write generation DataFrame to raw_generation. TODO: implement."""
    raise NotImplementedError("Implement in Step 3")
