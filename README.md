# Digital Wallet Transaction System

## What you'll build

A simple digital wallet system that shows how PostgreSQL and Kafka work together. Users can create wallets, add money, and transfer funds. The transaction history is created through Kafka events.

**What you'll learn**: PostgreSQL transactions, Kafka producer/consumer patterns, eventual consistency
**Setup**: Two Spring Boot apps sharing one PostgreSQL database

## Architecture

Here's what you're building:

```plaintext
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Wallet Service │───▶│    Kafka     │───▶│ History Service │
│ (Spring Boot)   │    │              │    │ (Spring Boot)   │
└─────────────────┘    │wallet_events │    └─────────────────┘
         │             └──────────────┘             │
         └──────────────────────────────────────────┘
                   Shared PostgreSQL Database
```

**The flow:**

1. Client hits Wallet Service API
2. Wallet Service updates database immediately
3. Wallet Service publishes event to Kafka
4. History Service consumes event and updates history
5. Client can query history from History Service

## Process Flow

### How Money Moves Through the System

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

### Example: Transfer Transaction

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

## What each service does

### Wallet Service

Handles the money stuff:

- Create wallets for users
- Add funds to wallets
- Transfer money between wallets
- Publish events when things happen

### History Service

Builds the audit trail:

- Listen for wallet events from Kafka
- Store transaction history
- Provide history APIs
- Handle duplicate events gracefully

## Database design

One PostgreSQL database, three tables:

```sql
-- Wallet Service owns these
wallets (
    id VARCHAR(36) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    balance DECIMAL(19,4) NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

wallet_transactions (
    id VARCHAR(36) PRIMARY KEY,
    wallet_id VARCHAR(36) NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    type VARCHAR(20) NOT NULL, -- 'FUND', 'TRANSFER_OUT', 'TRANSFER_IN'
    status VARCHAR(20) NOT NULL, -- 'COMPLETED', 'FAILED'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id)
);

-- History Service owns this
transaction_events (
    id VARCHAR(36) PRIMARY KEY,
    wallet_id VARCHAR(36) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    amount DECIMAL(19,4) NOT NULL,
    event_type VARCHAR(30) NOT NULL,
    transaction_id VARCHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    event_data JSONB
);
```

## API endpoints

### Wallet Service

- `POST /wallets` - Create wallet for userId
- `POST /wallets/{walletId}/fund` - Add money
- `POST /wallets/{walletId}/transfer` - Send money to another wallet
- `GET /wallets/{walletId}` - Check balance
- `GET /users/{userId}/wallets` - List user's wallets

### History Service

- `GET /wallets/{walletId}/history` - Transaction history
- `GET /users/{userId}/activity` - All user activity

## What you'll actually implement

### Core operations

1. **Create wallet** - Insert into PostgreSQL + publish event
2. **Fund wallet** - Update balance with optimistic locking + publish event
3. **Transfer money** - Update two wallets + publish event
4. **Consume events** - Process Kafka events into history table
5. **Query history** - Read from event-sourced history

### Key learning scenarios

**PostgreSQL stuff:**

- Handle concurrent balance updates without race conditions
- Use `DECIMAL` for money (never floats!)
- Manage transactions that span database + Kafka operations
- Implement optimistic locking with version fields

**Kafka stuff:**

- Configure producers to handle failures
- Set up consumer groups properly
- Handle duplicate messages
- Design event schemas that won't break

**Integration patterns:**

- Deal with eventual consistency
- Handle cases where Kafka is down but PostgreSQL works
- Retry failed operations
- Correlate events across services

## Business rules

Keep it simple:

- Users are just string IDs (no need for authentication)
- Balances can't go negative
- Use 4 decimal places for money amounts
- Balance updates happen immediately
- History updates happen eventually
- Everything must be auditable

## Event design

Events look like this:

```json
{
  "eventType": "WALLET_FUNDED",
  "walletId": "wallet-123",
  "userId": "user-456",
  "amount": "100.00",
  "transactionId": "txn-789",
  "timestamp": "2025-08-19T10:30:00Z"
}
```

**Event types:**

- `WALLET_CREATED`
- `WALLET_FUNDED`
- `TRANSFER_COMPLETED`
- `TRANSFER_FAILED`

## Tech stack

- **Backend**: Java + Spring Boot
- **Database**: PostgreSQL + Spring Data JPA
- **Messaging**: Apache Kafka
- **Infrastructure**: Docker Compose
- **Testing**: Integration tests that span both services

## Success criteria

- You can fund wallets concurrently without losing money
- Events flow reliably from Wallet Service to History Service
- History eventually catches up even when services restart
- You understand why optimistic locking matters for financial data
- You can explain the trade-offs of eventual consistency

The goal isn't production-ready code. It's understanding how PostgreSQL transactions and Kafka events work together in real distributed systems.
