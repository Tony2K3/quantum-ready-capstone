"""Switches that change what the server pulls. Source credentials are read
from environment variables in each source module (see sources/)."""

# Crypto-related fields (algorithms, key lengths, certificates...) are
# excluded until the team decides how to handle them. Flip to True to
# include whatever the source has.
INCLUDE_CRYPTO_FIELDS = False

# fetch_nodes + fetch_edges back to back reuse one pull
CACHE_SECONDS = 60
