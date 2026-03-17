# constants.py — PROTOCOL CONSTANTS, NOT CONFIGURATION
# These are hardcoded. No admin can change them. No agent can negotiate them.
# If these need to change, it's a protocol version bump — not a config update.

FEE_TOTAL       = 0.015    # 1.5% of every trade, always
FEE_PLATFORM    = 0.010    # goes to BOTmarket operations
FEE_MAKERS      = 0.003    # goes to market-making agents
FEE_VERIFY      = 0.002    # goes to quality verification fund
BOND_SLASH      = 0.05     # 5% of staked CU on any violation
SLASH_TO_BUYER  = 0.50     # 50% of slashed CU → affected buyer
SLASH_TO_FUND   = 0.50     # 50% of slashed CU → verification fund
SLA_MARGIN      = 0.20     # p99 + 20%
SLA_SAMPLE_SIZE = 50       # first 50 calls to derive SLA
HEARTBEAT_SEC   = 30
