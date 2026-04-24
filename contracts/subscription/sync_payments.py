"""
On-chain sync for PaymentReceived(address indexed user, uint256 amount)
- Runs DB migration on startup
- Polls new blocks for events
- Saves to PostgreSQL
"""

import os
import time
import logging
from decimal import Decimal

import psycopg2
import psycopg2.extras
from web3 import Web3
from web3.middleware import geth_poa_middleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIG  (set these in a .env file)
# ─────────────────────────────────────────────
RPC_URL          = os.getenv("RPC_URL", "https://mainnet.infura.io/v3/YOUR_KEY")
CONTRACT_ADDRESS = Web3.to_checksum_address(os.getenv("CONTRACT_ADDRESS", "0x0000000000000000000000000000000000000000"))
DATABASE_URL     = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/subscriptions")
POLL_INTERVAL    = int(os.getenv("POLL_INTERVAL", "12"))   # seconds between polls
START_BLOCK      = int(os.getenv("START_BLOCK", "0"))       # block to start from if no cursor
CONFIRMATIONS    = int(os.getenv("CONFIRMATIONS", "12"))    # blocks to wait before finalising

# Minimal ABI — only the event we care about
CONTRACT_ABI = [
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True,  "internalType": "address", "name": "user",   "type": "address"},
            {"indexed": False, "internalType": "uint256",  "name": "amount", "type": "uint256"},
        ],
        "name": "PaymentReceived",
        "type": "event",
    }
]


# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL)


MIGRATION_SQL = """
-- Migration v1: on-chain payment sync

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cursor: tracks the last block successfully synced per contract
CREATE TABLE IF NOT EXISTS sync_cursors (
    contract_address  TEXT PRIMARY KEY,
    last_block        BIGINT      NOT NULL DEFAULT 0,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Raw payments from PaymentReceived events
CREATE TABLE IF NOT EXISTS payments (
    id               BIGSERIAL   PRIMARY KEY,
    tx_hash          TEXT        NOT NULL,
    block_number     BIGINT      NOT NULL,
    block_timestamp  TIMESTAMPTZ,
    log_index        INT         NOT NULL,
    user_address     TEXT        NOT NULL,
    amount_wei       NUMERIC(78) NOT NULL,       -- full uint256 precision
    amount_eth       NUMERIC(36, 18),             -- human-readable (18 decimals)
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (tx_hash, log_index)
);

-- Aggregated balance per user (maintained by the sync process)
CREATE TABLE IF NOT EXISTS user_balances (
    user_address      TEXT        PRIMARY KEY,
    total_paid_wei    NUMERIC(78) NOT NULL DEFAULT 0,
    total_paid_eth    NUMERIC(36, 18),
    payment_count     BIGINT      NOT NULL DEFAULT 0,
    first_payment_at  TIMESTAMPTZ,
    last_payment_at   TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_payments_user    ON payments (user_address);
CREATE INDEX IF NOT EXISTS idx_payments_block   ON payments (block_number);
CREATE INDEX IF NOT EXISTS idx_payments_tx      ON payments (tx_hash);
"""


def run_migration(conn):
    with conn.cursor() as cur:
        cur.execute(MIGRATION_SQL)
        cur.execute(
            """
            INSERT INTO schema_migrations (version)
            VALUES ('v1_payment_received_sync')
            ON CONFLICT (version) DO NOTHING
            """
        )
    conn.commit()
    log.info("Migration applied (or already up to date).")


# ─────────────────────────────────────────────
# CURSOR
# ─────────────────────────────────────────────

def get_cursor(conn, address: str) -> int:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT last_block FROM sync_cursors WHERE contract_address = %s",
            (address.lower(),),
        )
        row = cur.fetchone()
        return row[0] if row else START_BLOCK


def set_cursor(conn, address: str, block: int):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO sync_cursors (contract_address, last_block, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (contract_address)
            DO UPDATE SET last_block = EXCLUDED.last_block, updated_at = NOW()
            """,
            (address.lower(), block),
        )
    conn.commit()


# ─────────────────────────────────────────────
# EVENT PROCESSING
# ─────────────────────────────────────────────

WEI_PER_ETH = Decimal(10 ** 18)


def save_events(conn, w3: Web3, events: list):
    if not events:
        return

    rows = []
    for ev in events:
        block    = ev["blockNumber"]
        tx_hash  = ev["transactionHash"].hex()
        log_idx  = ev["logIndex"]
        user     = ev["args"]["user"].lower()
        amount   = ev["args"]["amount"]           # int (wei)
        amount_d = Decimal(amount)

        # Fetch block timestamp (cached implicitly by web3 — one RPC call per block)
        blk_ts = None
        try:
            blk_data = w3.eth.get_block(block)
            blk_ts   = blk_data["timestamp"]      # Unix epoch seconds
        except Exception as e:
            log.warning("Could not fetch block timestamp for block %s: %s", block, e)

        rows.append((tx_hash, block, blk_ts, log_idx, user, amount_d, amount_d / WEI_PER_ETH))

    with conn.cursor() as cur:
        # Insert payments (skip duplicates)
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO payments
                (tx_hash, block_number, block_timestamp, log_index,
                 user_address, amount_wei, amount_eth)
            VALUES %s
            ON CONFLICT (tx_hash, log_index) DO NOTHING
            """,
            rows,
            template="(%s, %s, to_timestamp(%s), %s, %s, %s, %s)",
        )

        # Upsert user_balances
        users = {}
        for tx_hash, block, blk_ts, log_idx, user, amount_d, amount_eth in rows:
            if user not in users:
                users[user] = {"total": Decimal(0), "count": 0, "ts": blk_ts}
            users[user]["total"] += amount_d
            users[user]["count"] += 1
            if blk_ts and (users[user]["ts"] is None or blk_ts > users[user]["ts"]):
                users[user]["ts"] = blk_ts

        for user, data in users.items():
            cur.execute(
                """
                INSERT INTO user_balances
                    (user_address, total_paid_wei, total_paid_eth,
                     payment_count, first_payment_at, last_payment_at, updated_at)
                VALUES (%s, %s, %s, %s, to_timestamp(%s), to_timestamp(%s), NOW())
                ON CONFLICT (user_address) DO UPDATE SET
                    total_paid_wei   = user_balances.total_paid_wei + EXCLUDED.total_paid_wei,
                    total_paid_eth   = user_balances.total_paid_eth + EXCLUDED.total_paid_eth,
                    payment_count    = user_balances.payment_count  + EXCLUDED.payment_count,
                    first_payment_at = LEAST(user_balances.first_payment_at, EXCLUDED.first_payment_at),
                    last_payment_at  = GREATEST(user_balances.last_payment_at, EXCLUDED.last_payment_at),
                    updated_at       = NOW()
                """,
                (
                    user,
                    data["total"],
                    data["total"] / WEI_PER_ETH,
                    data["count"],
                    data["ts"],
                    data["ts"],
                ),
            )

    conn.commit()
    log.info("Saved %d event(s).", len(rows))


# ─────────────────────────────────────────────
# SYNC LOOP
# ─────────────────────────────────────────────

CHUNK_SIZE = 2000   # max block range per getLogs call


def sync(w3: Web3, contract, conn):
    latest     = w3.eth.block_number - CONFIRMATIONS
    from_block = get_cursor(conn, CONTRACT_ADDRESS) + 1

    if from_block > latest:
        log.info("Already up to date at block %d.", latest)
        return

    log.info("Syncing blocks %d → %d ...", from_block, latest)

    block = from_block
    while block <= latest:
        to_block = min(block + CHUNK_SIZE - 1, latest)
        try:
            events = contract.events.PaymentReceived.get_logs(
                fromBlock=block, toBlock=to_block
            )
            log.info("Blocks %d-%d: %d event(s) found.", block, to_block, len(events))
            save_events(conn, w3, events)
            set_cursor(conn, CONTRACT_ADDRESS, to_block)
        except Exception as e:
            log.error("Error fetching logs %d-%d: %s", block, to_block, e)
            raise
        block = to_block + 1


def main():
    # Connect Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)  # safe for non-PoA too
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {RPC_URL}")
    log.info("Connected to chain (chainId=%d).", w3.eth.chain_id)

    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)

    # Connect DB & migrate
    conn = get_conn()
    run_migration(conn)

    # Poll loop
    log.info("Starting sync loop (poll every %ds).", POLL_INTERVAL)
    while True:
        try:
            sync(w3, contract, conn)
        except psycopg2.OperationalError:
            log.warning("DB connection lost, reconnecting...")
            conn = get_conn()
        except Exception as e:
            log.error("Sync error: %s", e)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()