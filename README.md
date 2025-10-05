# Digital Wallet System

This project is a simple digital wallet system built with Python, FastAPI, and Kafka. It demonstrates a microservices architecture where a `Wallet Service` handles core financial transactions and a `History Service` provides an audit trail through event-sourcing. The system is designed to showcase patterns for handling data consistency and resilience in a distributed environment.

## Architecture

The system is composed of two main services that communicate asynchronously via a Kafka message broker, while sharing a PostgreSQL database.

```plaintext
┌──────────────────┐      ┌──────────────┐      ┌──────────────────┐
│  Wallet Service  │─────▶│    Kafka     │─────▶│ History Service  │
│ (FastAPI/Python) │      │              │      │ (FastAPI/Python) │
└──────────────────┘      │wallet_events │      └──────────────────┘
         │                └──────────────┘                │
         └────────────────────────────────────────────────┘
                   Shared PostgreSQL Database
```

1.  **Wallet Service**: The primary service that handles synchronous operations like creating wallets, funding, and transfers. It ensures immediate data consistency in the database for critical financial data and publishes events to Kafka upon success.
2.  **History Service**: Consumes events from Kafka to build a complete, event-sourced audit trail of all transactions. This provides a queryable history that is eventually consistent with the main wallet data.

## Core Features

-   Create and manage digital wallets for users.
-   Fund wallets using **optimistic locking** to prevent race conditions during concurrent updates.
-   Transfer funds between wallets using **pessimistic locking** for atomicity.
-   Publish events to Kafka for every transaction (create, fund, transfer).
-   Provide a complete, event-sourced transaction history for any wallet or user.
-   Handle idempotent event processing to prevent duplicate history entries.

## Technology Stack

-   **Backend**: Python 3.11+ with [FastAPI](https://fastapi.tiangolo.com/)
-   **Database**: PostgreSQL with [SQLAlchemy](https://www.sqlalchemy.org/) for ORM
-   **Messaging**: Apache Kafka via [aiokafka](https://github.com/aio-libs/aiokafka)
-   **Infrastructure**: Docker Compose

## Key Concepts Implemented

This project serves as a practical demonstration of several key patterns used in distributed systems:

-   **Eventual Consistency**: The transaction history in the `History Service` becomes consistent with the `Wallet Service` only after the Kafka event has been successfully processed.
-   **Event Sourcing (simplified)**: The `History Service` builds its state entirely from the stream of events produced by the `Wallet Service`, providing a verifiable audit log.
-   **Optimistic Locking**: To handle concurrent funding requests safely, the `wallets` table uses a `version` column. An update will only succeed if the version has not changed, preventing lost updates.
-   **Pessimistic Locking**: For critical, multi-row operations like fund transfers, the system uses `SELECT ... FOR UPDATE` to lock the involved wallet rows in the database. This ensures the transfer is atomic and avoids deadlocks by locking rows in a consistent order.
-   **Idempotent Consumers**: The `History Service` is designed to handle duplicate Kafka events gracefully, ensuring that a single transaction is never recorded more than once, even if the event is delivered multiple times.

## Process Flows

### Synchronous vs. Asynchronous Operations

The system clearly separates immediate, synchronous actions from eventual, asynchronous ones.

```plaintext
                    ┌─────────────────────────────────────────┐
                    │         SYNCHRONOUS (immediate)         │
                    ├─────────────────────────────────────────┤
                    │                                         │
    Client─────────▶│  Wallet Service ──▶ PostgreSQL          │
    Request         │     │                  │                │
                    │     │                  ▼                │
                    │     │              [wallets]            │
                    │     │              balance: $100        │
                    │     │              version: 2           │
                    │     │                  │                │
                    │     │                  ▼                │
                    │     │          [wallet_transactions]    │
                    │     │           type: FUND              │
                    │     │           amount: $50             │
                    │     │                                   │
                    │     ▼                                   │
                    │  Response                               │
    ◀───────────────│  (success)                              │
                    │                                         │
                    └─────────────┬───────────────────────────┘
                                  │
                                  │ Publish Event
                                  ▼
                    ┌─────────────────────────────────────────┐
                    │        ASYNCHRONOUS (eventual)          │
                    ├─────────────────────────────────────────┤
                    │                                         │
                    │   Kafka ──▶ History Service             │
                    │     │            │                      │
                    │     ▼            ▼                      │
                    │  [Event]    [transaction_events]        │
                    │   {            event_type: WALLET_FUNDED│
                    │     type:       wallet_id: abc-123      │
                    │     "FUNDED",   amount: $50             │
                    │     amount: 50,  event_data: {...}      │
                    │     ...         created_at: timestamp   │
                    │   }                                     │
                    │                                         │
                    └─────────────────────────────────────────┘
```

### Transfer Transaction Example

```plaintext
Before Transfer:
┌──────────────┐          ┌──────────────┐
│   Wallet A   │          │   Wallet B   │
│ Balance: $100│          │ Balance: $50 │
└──────────────┘          └──────────────┘

During Transfer ($30 from A to B):
1. Lock both wallets (ORDER BY id to prevent deadlock)
2. Check A has >= $30
3. A.balance -= 30, B.balance += 30
4. Record both transactions
5. Publish event
6. Commit

After Transfer:
┌──────────────┐          ┌──────────────┐          ┌────────────────┐
│   Wallet A   │          │   Wallet B   │          │  Kafka Event   │
│ Balance: $70 │          │ Balance: $80 │          │ TRANSFER_DONE  │
└──────────────┘          └──────────────┘          └────────────────┘
        │                         │                           │
        └─────────────────────────┴───────────────────────────┘
                              Eventually
                                 ▼
                        ┌─────────────────┐
                        │ History Service │
                        │   2 events:     │
                        │   - A sent $30  │
                        │   - B recv $30  │
                        └─────────────────┘
```

## API Endpoints

### Wallet Service

-   `POST /wallets` - Create a new wallet for a user.
-   `POST /wallets/{wallet_id}/fund` - Add funds to a wallet.
-   `POST /wallets/{wallet_id}/transfer` - Transfer funds to another wallet.
-   `GET /wallets/{wallet_id}` - Get wallet details and balance.
-   `GET /users/{user_id}/wallets` - List all wallets for a specific user.

### History Service

-   `GET /history/wallets/{wallet_id}` - Get the full transaction history for a wallet.
-   `GET /history/users/{user_id}` - Get all activity for a user across all their wallets.