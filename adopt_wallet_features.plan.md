# Adopt Wallet Features from Reference App

## Goal
Integrate "Smart Gas" logic and advanced HD Wallet derivation from the reference application (`Wallet Sender`) to improve transaction reliability and wallet management flexibility.

## Changes

### 1. [app/services/blockchain_service.py](app/services/blockchain_service.py)
-   Implement `get_optimal_gas_price` method:
    -   Fetch RPC gas price.
    -   Apply dynamic capping: `min(max(rpc_gas, MIN_GAS), MAX_GAS)`.
    -   Constants: `MIN_GAS = 0.1 Gwei`, `MAX_GAS = 5.0 Gwei`.
-   Update `send_payment` and `send_native_token` to use `get_optimal_gas_price` instead of fixed value.
-   Update `get_transaction_count` to use `'pending'` block identifier for better concurrency.

### 2. [bot/handlers/admin/wallet_key_setup.py](bot/handlers/admin/wallet_key_setup.py)
-   Update `WalletSetupStates` to include `setting_derivation_index`.
-   Modify `process_output_key` to detect Seed Phrase and ask for Derivation Index (default 0).
-   Add `process_derivation_index` handler to perform derivation: `m/44'/60'/0'/0/{index}`.
-   Wrap `Account.enable_unaudited_hdwallet_features` in try/except block.

## Result
-   **Reliability:** Transactions won't get stuck during network congestion (Smart Gas + Pending Nonce).
-   **Flexibility:** Admins can import specific addresses from HD Wallets (e.g. Ledger/Trust Wallet secondary accounts).

