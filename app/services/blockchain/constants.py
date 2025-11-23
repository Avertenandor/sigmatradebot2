"""Blockchain constants and ABIs."""

# USDT BEP-20 Contract ABI (╤В╨╛╨╗╤М╨║╨╛ ╨╜╨╡╨╛╨▒╤Е╨╛╨┤╨╕╨╝╤Л╨╡ ╤Д╤Г╨╜╨║╤Ж╨╕╨╕)
USDT_ABI = [
    # Transfer event
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    # balanceOf function
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    # transfer function
    {
        "constant": False,
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # decimals function
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
    # allowance function
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

# USDT ╨╕╨╝╨╡╨╡╤В 18 decimals ╨╜╨░ BSC
USDT_DECIMALS = 18

# Gas limits
DEFAULT_GAS_LIMIT = 100000  # For USDT transfers
MAX_GAS_PRICE_GWEI = 10  # Maximum gas price in Gwei

# Confirmation blocks
DEFAULT_CONFIRMATION_BLOCKS = 12

# Retry settings
MAX_RETRIES = 5
RETRY_DELAY_BASE = 2  # seconds, exponential backoff

# WebSocket reconnect settings
WS_RECONNECT_DELAY = 5  # seconds
WS_MAX_RECONNECT_ATTEMPTS = 10
