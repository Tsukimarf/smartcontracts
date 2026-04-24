# Pi Network Smart Contracts

A collection of smart contract implementations for the Pi Network blockchain, enabling decentralized applications with subscription support, recurring payments, and other blockchain-native features.

**This is a fork of [PiNetwork/SmartContracts](https://github.com/PiNetwork/SmartContracts)**

## Overview

Pi Network Smart Contracts provides reference implementations and tools for building decentralized applications on the Pi blockchain. The repository currently focuses on subscription support—Pi Network's first smart contract capability—which enables developers to build recurring service models while preserving subscriber control over funds.

### Key Features

- **Subscription Support**: Native smart contract implementation for recurring payments
- **Wallet-Level Control**: Funds remain in the subscriber's wallet until charges are processed
- **Budget Approval Model**: Subscribers approve a defined budget without needing to re-sign every billing event
- **No Pre-Funding Required**: Support for recurring payments without locking up full budgets in advance
- **Flexible Billing Horizons**: Optional expiration ledgers for time-limited authorizations
- **Soroban Integration**: Leverages Soroban's token allowance mechanism for secure fund transfers

## Use Cases

By bringing subscriptions to the Pi ecosystem, developers can implement:

- **SaaS & Productivity**: AI products, productivity tools, and software-as-a-service platforms
- **Digital Content**: Memberships, streaming services, and premium content platforms
- **E-Commerce**: Subscription boxes, recurring orders, and service memberships
- **Local Commerce**: Community-based membership programs and local service subscriptions

## Technical Architecture

### How Subscriptions Work

The subscription contract implements a clean, blockchain-native approach to recurring payments:

1. **Approval Phase**: Subscribers approve the contract as a spender for a defined amount
   - Optional expiration ledger limits authorization duration
   - Approved funds remain in the subscriber's wallet

2. **Billing Phase**: When a charge is due
   - The contract validates the subscription remains active
   - Funds are transferred directly from subscriber to merchant
   - Only the billing amount is withdrawn (not the full approved budget)

3. **Withdrawal**: Merchants receive funds immediately upon charge processing

### Design Innovation

Traditional blockchain systems require explicit authorization (typically a new signature) for every transaction. This creates friction for subscriptions, which need to run automatically. Pi's approach solves this through:

- **Token Allowance Mechanism**: Borrowed from Soroban, allowing contracts to draw down approved amounts over time
- **Stateful Validation**: Contract maintains subscription state without requiring new signatures
- **Wallet Protection**: Funds never leave the subscriber's control until actual withdrawal

## Project Structure

```
smartcontracts/
├── contracts/
│   ├── subscription/          # Core subscription contract implementation
│   │   ├── src/
│   │   ├── Cargo.toml
│   │   └── lib.rs
│   └── [other contracts]/
├── tests/                     # Test suites for smart contracts
├── docs/                      # Documentation and specifications
├── Cargo.toml                # Rust workspace configuration
└── README.md                 # This file
```

## Getting Started

### Prerequisites

- **Rust 1.70+**: Install from [rustup.rs](https://rustup.rs)
- **Soroban CLI**: Pi Network's smart contract development tool
- **Node.js 16+** (optional, for testing and deployment scripts)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Tsukimarf/smartcontracts.git
cd smartcontracts
```

2. Install dependencies:
```bash
cargo build
```

3. Run tests:
```bash
cargo test
```

## Development

### Building Smart Contracts

To build the subscription contract:

```bash
cd contracts/subscription
cargo build --release --target wasm32-unknown-unknown
```

### Running Tests

```bash
cargo test --all
```

### Code Quality

We follow Rust best practices and use standard linting:

```bash
cargo clippy
cargo fmt --check
```

## Smart Contract Specifications

### Subscription Contract Interface

The subscription smart contract provides the following key operations:

#### Initialize Subscription
```
fn create_subscription(
    client: &Client,
    subscriber: &Address,
    merchant: &Address,
    amount: i128,
    interval: u32,  // in ledgers
) -> Result<SubscriptionId, Error>
```

#### Process Billing Cycle
```
fn process_billing(
    client: &Client,
    subscription_id: SubscriptionId,
) -> Result<TransactionId, Error>
```

#### Manage Subscription
```
fn cancel_subscription(subscription_id: SubscriptionId) -> Result<(), Error>
fn get_subscription_status(subscription_id: SubscriptionId) -> SubscriptionStatus
```

For complete API documentation, see the contract source code in `contracts/subscription/src/`.

## Contributing

We welcome contributions from the community! Please follow these guidelines:

1. **Code Standards**: Follow Rust conventions and best practices
2. **Testing**: All new features must include comprehensive tests
3. **Documentation**: Update docs when adding features
4. **Security**: Report security issues privately to the PiNetwork team
5. **Audit**: Smart contracts may be subject to external audits

### Reporting Issues

Found a bug or vulnerability? Please report it responsibly:

- **Security Issues**: Contact the Pi Network team directly
- **Feature Requests**: Open an issue with detailed use case
- **Bug Reports**: Include reproduction steps and environment details

## Security & Auditing

Smart contracts in this repository are subject to:

- Community code review
- External professional audits
- Continuous security testing

**Note**: While these contracts have undergone review, smart contracts carry inherent risks. Use at your own risk and conduct your own security assessments before deploying to production.

## Documentation References

For more information on Pi Network smart contracts:

- **PiRC2 Specification**: [Pi Network Requests for Comment - Subscriptions](https://github.com/PiNetwork/PiRC/tree/main/PiRC2)
- **PiRC Standards**: [Pi Network Standards & Proposals](https://github.com/PiNetwork/PiRC)
- **Pi Network**: [minepi.com](https://minepi.com)

## Technology Stack

- **Language**: Rust
- **Smart Contract Platform**: Soroban
- **Blockchain**: Pi Network
- **Build Tool**: Cargo
- **Testing Framework**: Rust test framework

## Roadmap

Current focus areas for smart contract development:

- [ ] Extended subscription features (pause, resume, tier changes)
- [ ] Multi-merchant payment routing
- [ ] Advanced billing cycle patterns (annual, quarterly, etc.)
- [ ] Cross-chain subscription support
- [ ] Enhanced monitoring and analytics

## License

This project is part of the Pi Network ecosystem. Please refer to the LICENSE file in the repository for full licensing details.

## Community & Support

- **Pi Network Community**: [Community Forum](https://minepi.com/community)
- **GitHub Issues**: [Report issues and request features](https://github.com/Tsukimarf/smartcontracts/issues)
- **Documentation**: [Full documentation](https://docs.pi.network)

## Acknowledgments

- **Original Repository**: [PiNetwork/SmartContracts](https://github.com/PiNetwork/SmartContracts)
- **Soroban Platform**: Stellar's smart contract platform
- **Community**: All contributors and code reviewers

---

**Last Updated**: April 2026  
**Status**: Active Development  
**Version**: Reference Implementation v1.0
