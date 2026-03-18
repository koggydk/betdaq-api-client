# Betdaq API Client

Python client for the Betdaq betting exchange API. Connects via the same vendor endpoint and headers used by Geeks Toy, providing free API access to Betdaq's exchange.

## Setup

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# Test connection
python betdaq_client.py

# Interactive mode
python betdaq_client.py --interactive

# Run examples
python examples.py
```

## Usage as a Library

```python
from betdaq_client import BetdaqClient

client = BetdaqClient("your_betdaq_username", "your_betdaq_password")
```

### Navigating the Event Tree

Betdaq organises data in a tree structure:

```
Sport (top-level)
  └── Competition / League
        └── Match / Event
              └── Market (Match Odds, Over/Under, etc.)
                    └── Selection (Team A, Draw, Team B)
                          └── Prices (Back / Lay)
```

To get to prices, you drill down through the levels:

```python
# 1. List all sports
sports = client.list_top_level_events()
# [{'id': 100003, 'name': 'Soccer'}, {'id': 100032, 'name': 'Ice Hockey'}, ...]

# 2. Drill into a sport to see competitions
tree = client.get_event_tree(100032)  # Ice Hockey
# tree['events'] = [{'id': 10791795, 'name': 'NHL'}, ...]

# 3. Drill into a competition to see matches
tree = client.get_event_tree(10791795)  # NHL
# tree['events'] = [{'id': 14518140, 'name': 'Colorado Avalanche v Dallas Stars'}, ...]

# 4. Drill into a match to see markets
tree = client.get_event_tree(14518140)
# tree['markets'] = [{'id': 50275494, 'name': 'Winner (incl. overtime and penalties)'}, ...]

# 5. Get prices for a market
prices = client.get_prices_raw(50275494)
# prices['selections'][0] = {
#     'name': 'Colorado Avalanche',
#     'last_price': '1.77',
#     'back': [{'price': 1.74, 'stake': 213.33}, ...],
#     'lay':  [{'price': 1.76, 'stake': 11.08}, ...],
# }
```

### Searching for Events

Skip the drill-down and search directly:

```python
# Search within a sport
matches = client.search_events(100003, "Liverpool")  # Soccer
matches = client.search_events(100032, "Colorado")    # Ice Hockey
matches = client.search_events(100005, "Djokovic")    # Tennis
```

### Display Helpers

```python
# Pretty-print a price ladder
client.print_prices(50275494)

# Pretty-print an event tree
client.print_event_tree(100032)
```

## Common Sport IDs

| ID | Sport |
|----|-------|
| 100003 | Soccer |
| 100004 | Horse Racing |
| 100005 | Tennis |
| 100006 | Golf |
| 100007 | Cricket |
| 100008 | Greyhound Racing |
| 100009 | Rugby League |
| 100010 | Rugby Union |
| 100015 | Formula 1 |
| 100016 | Baseball |
| 100017 | Basketball |
| 100019 | Darts |
| 100020 | Boxing |
| 100027 | Snooker |
| 100032 | Ice Hockey |
| 338839 | Australian Rules |
| 481576 | Politics |
| 700700 | MMA |

## Common Football Competition IDs

Use `client.get_event_tree(100003)` to get the latest, but these are typical:

- English Premier League
- UEFA Champions League
- La Liga
- Serie A
- Bundesliga

## NHL

```python
# NHL is under Ice Hockey (100032)
nhl_tree = client.get_event_tree(10791795)  # NHL competition ID

# Each match typically has:
#   - Winner (incl. overtime and penalties) — 2-way
#   - Match Odds — 3-way (includes draw for regulation time)
#   - Handicap (incl. overtime and penalties) (-1.5)
#   - Total (incl. overtime and penalties) (5.5 / 6.5)
```

## API Details

### Endpoints

| Service | URL |
|---------|-----|
| ReadOnly (prices, events) | `https://gbextrader.betdaq.com/v2.0/ReadOnlyService.asmx` |
| Secure (account, orders) | `https://gbextrader.betdaq.com/v2.0/Secure/SecureService.asmx` |
| WSDL | `https://api.betdaq.com/v2.0/API.wsdl` |

### SOAP Header

Every request includes this header:

```xml
<ExternalApiHeader
  version="2"
  languageCode="en"
  username="YOUR_USERNAME"
  password="YOUR_PASSWORD"
  applicationIdentifier="GeeksToy V1.6c"
  xmlns="http://www.GlobalBettingExchange.com/ExternalAPI/" />
```

Password is only included for SecureService calls.

### Available API Operations

**ReadOnlyService:**
- `ListTopLevelEvents` — list sports
- `GetEventSubTreeNoSelections` — browse event tree
- `GetEventSubTreeWithSelections` — browse tree with selection details
- `GetMarketInformation` — market details
- `GetPrices` — live back/lay prices
- `GetOddsLadder` — valid price increments
- `ListSelectionsChangedSince` — poll for price changes
- `GetCurrentSelectionSequenceNumber` — sequence for polling
- `ListSelectionTrades` — recent trades on a selection
- `ListMarketWithdrawalHistory` — withdrawal history
- `GetSPEnabledMarketsInformation` — starting price markets

**SecureService:**
- `GetAccountBalances` — balance, exposure, available funds
- `PlaceOrdersWithReceipt` / `PlaceOrdersNoReceipt` — place bets
- `UpdateOrdersNoReceipt` — update existing orders
- `CancelOrders` / `CancelAllOrders` — cancel bets
- `ListBootstrapOrders` — list current orders
- `ListOrdersChangedSince` — poll for order changes
- `GetOrderDetails` — details of specific orders
- `SuspendFromTrading` / `UnsuspendFromTrading` — pause trading
- `RegisterHeartbeat` / `Pulse` — keep-alive for safety
