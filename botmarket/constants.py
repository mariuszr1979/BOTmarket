# constants.py — PROTOCOL CONSTANTS, NOT CONFIGURATION
# These are hardcoded. No admin can change them. No agent can negotiate them.
# If these need to change, it's a protocol version bump — not a config update.

FEE_TOTAL       = 0.015    # 1.5% of every trade, always — retained by exchange
BOND_SLASH      = 0.05     # 5% of staked CU on any violation
SLASH_TO_BUYER  = 0.50     # 50% of slashed CU → affected buyer (compensation)
SLASH_BURN      = 0.50     # 50% of slashed CU → destroyed (deflationary, no fund address)
SLA_MARGIN          = 0.20     # p99 + 20%
SLA_SAMPLE_SIZE     = 50       # first 50 calls to derive SLA
SLA_DECOHERENCE_NS  = 2_592_000_000_000_000  # 30 days in nanoseconds
HEARTBEAT_SEC       = 30
CIRCUIT_BREAKER_STRIKES = 3        # consecutive callback failures before auto-suspend
ESCROW_TIMEOUT_NS = 3_600_000_000_000  # 1 hour — auto-refund "executed" trades older than this

# Faucet — drip free CU to new agents so they can make their first buy
FAUCET_FIRST_CU      = 500.0                  # first-ever call
FAUCET_DRIP_CU       =  50.0                  # subsequent once-per-24h calls
FAUCET_MAX_CU        = 1000.0                 # lifetime cap per agent
FAUCET_WINDOW_NS     = 86_400_000_000_000     # 24h in nanoseconds
