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
SLA_MARGIN          = 0.20     # p99 + 20%
SLA_SAMPLE_SIZE     = 50       # first 50 calls to derive SLA
SLA_DECOHERENCE_NS  = 2_592_000_000_000_000  # 30 days in nanoseconds
HEARTBEAT_SEC       = 30

# Faucet — drip free CU to new agents so they can make their first buy
FAUCET_FIRST_CU      = 500.0                  # first-ever call
FAUCET_DRIP_CU       =  50.0                  # subsequent once-per-24h calls
FAUCET_MAX_CU        = 1000.0                 # lifetime cap per agent
FAUCET_WINDOW_NS     = 86_400_000_000_000     # 24h in nanoseconds
