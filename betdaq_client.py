"""
Betdaq API Client - Direct SOAP API access via Geeks Toy vendor credentials.

Two services:
  - ReadOnlyService: market data, prices, events (no password in header)
  - SecureService:   account, orders, trading (password required)

Usage:
    # Quick test
    python betdaq_client.py

    # Interactive mode
    python betdaq_client.py --interactive

    # As a library
    from betdaq_client import BetdaqClient
    client = BetdaqClient("your_username", "your_password")
    events = client.list_top_level_events()
    prices = client.get_prices_raw(50275494)
"""

import sys
import requests
from lxml import etree
from zeep import Client, Settings
from zeep.transports import Transport


# ── Betdaq SOAP Client ─────────────────────────────────────────────────────

class BetdaqClient:
    """
    Betdaq exchange API client.

    Uses the same endpoint and vendor headers as Geeks Toy,
    which provides free API access to Betdaq's exchange.
    """

    WSDL_URL = "https://api.betdaq.com/v2.0/API.wsdl"
    READONLY_URL = "https://gbextrader.betdaq.com/v2.0/ReadOnlyService.asmx"
    SECURE_URL = "https://gbextrader.betdaq.com/v2.0/Secure/SecureService.asmx"
    NS = "http://www.GlobalBettingExchange.com/ExternalAPI/"
    APP_ID = "GeeksToy V1.6c"
    API_VERSION = "2"
    LANGUAGE = "en"

    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session = requests.Session()

        # Zeep client for structured calls
        transport = Transport(session=self.session, timeout=30)
        settings = Settings(strict=False, xml_huge_tree=True)
        self.zeep_client = Client(self.WSDL_URL, transport=transport, settings=settings)

        # SOAP headers
        header_el = self.zeep_client.get_element(f"{{{self.NS}}}ExternalApiHeader")
        self.readonly_header = header_el(
            version=self.API_VERSION,
            languageCode=self.LANGUAGE,
            username=self.username,
            applicationIdentifier=self.APP_ID,
        )
        self.secure_header = header_el(
            version=self.API_VERSION,
            languageCode=self.LANGUAGE,
            username=self.username,
            password=self.password,
            applicationIdentifier=self.APP_ID,
        )

        # Service bindings with vendor endpoint URLs
        self.readonly = self.zeep_client.create_service(
            f"{{{self.NS}}}ReadOnlyService", self.READONLY_URL)
        self.secure = self.zeep_client.create_service(
            f"{{{self.NS}}}SecureService", self.SECURE_URL)

    # ── Raw XML helpers (most reliable for complex requests) ────────────

    def _soap_request(self, url, action, body_xml, include_password=False):
        """Send a raw SOAP request and return parsed XML response."""
        pwd = f' password="{self.password}"' if include_password else ''
        envelope = f'''<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<soap:Header>
  <ExternalApiHeader version="{self.API_VERSION}" languageCode="{self.LANGUAGE}"
    username="{self.username}"{pwd}
    applicationIdentifier="{self.APP_ID}"
    xmlns="{self.NS}" />
</soap:Header>
<soap:Body>{body_xml}</soap:Body>
</soap:Envelope>'''

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': f'{self.NS}{action}',
        }
        r = self.session.post(url, data=envelope.encode('utf-8'), headers=headers, timeout=30)
        r.raise_for_status()
        return etree.fromstring(r.content)

    def _ns(self, tag):
        """Wrap tag with namespace."""
        return f'{{{self.NS}}}{tag}'

    # ── Account ─────────────────────────────────────────────────────────

    def get_account_balances(self):
        """Get account balance, exposure, available funds."""
        root = self._soap_request(
            self.SECURE_URL, 'GetAccountBalances',
            f'<GetAccountBalances xmlns="{self.NS}"><getAccountBalancesRequest /></GetAccountBalances>',
            include_password=True,
        )
        result = root.find(f'.//{self._ns("GetAccountBalancesResult")}')
        status = result.find(self._ns('ReturnStatus'))
        if status.get('Code') != '0':
            return {'error': status.get('Description')}
        return {
            'balance': result.get('Balance'),
            'exposure': result.get('Exposure'),
            'available': result.get('AvailableFunds'),
            'currency': result.get('Currency'),
        }

    # ── Events ──────────────────────────────────────────────────────────

    def list_top_level_events(self):
        """
        List all top-level sports/event categories.

        Returns list of dicts with 'id' and 'name'.

        Common sport IDs:
            100003  Soccer
            100004  Horse Racing
            100005  Tennis
            100006  Golf
            100007  Cricket
            100008  Greyhound Racing
            100009  Rugby League
            100010  Rugby Union
            100015  Formula 1
            100016  Baseball
            100017  Basketball
            100019  Darts
            100020  Boxing
            100027  Snooker
            100032  Ice Hockey
            338839  Australian Rules
            481576  Politics
            700700  Mixed Martial Arts
        """
        root = self._soap_request(
            self.READONLY_URL, 'ListTopLevelEvents',
            f'<ListTopLevelEvents xmlns="{self.NS}">'
            f'<listTopLevelEventsRequest WantPlayMarkets="false" />'
            f'</ListTopLevelEvents>',
        )
        events = []
        for el in root.iter(self._ns('EventClassifiers')):
            eid = el.get('Id')
            name = el.get('Name')
            if eid and name:
                events.append({'id': int(eid), 'name': name})
        return events

    def get_event_tree(self, event_id, direct_only=True):
        """
        Browse into an event to see sub-events and markets.

        Args:
            event_id: The event classifier ID to drill into.
            direct_only: If True, only get immediate children.
                         If False, get full tree (can be large).

        Returns dict with 'events' (sub-events) and 'markets' lists.
        """
        direct = 'true' if direct_only else 'false'
        root = self._soap_request(
            self.READONLY_URL, 'GetEventSubTreeNoSelections',
            f'<GetEventSubTreeNoSelections xmlns="{self.NS}">'
            f'<getEventSubTreeNoSelectionsRequest WantDirectDescendentsOnly="{direct}" WantPlayMarkets="false">'
            f'<EventClassifierIds>{event_id}</EventClassifierIds>'
            f'</getEventSubTreeNoSelectionsRequest>'
            f'</GetEventSubTreeNoSelections>',
        )
        sub_events = []
        markets = []
        # Find all EventClassifiers that are children (skip the root one)
        all_classifiers = list(root.iter(self._ns('EventClassifiers')))
        for el in all_classifiers:
            eid = el.get('Id')
            name = el.get('Name')
            if eid and name and int(eid) != event_id:
                sub_events.append({'id': int(eid), 'name': name})
        for el in root.iter(self._ns('Markets')):
            mid = el.get('Id')
            name = el.get('Name')
            if mid and name:
                markets.append({'id': int(mid), 'name': name})
        return {'events': sub_events, 'markets': markets}

    def search_events(self, sport_id, search_term):
        """
        Search for events within a sport by name.

        Args:
            sport_id: Top-level sport ID (e.g. 100032 for Ice Hockey).
            search_term: Text to search for (case-insensitive).

        Returns list of matching event dicts.
        """
        tree = self.get_event_tree(sport_id, direct_only=False)
        term = search_term.lower()
        return [e for e in tree['events'] if term in e['name'].lower()]

    # ── Prices ──────────────────────────────────────────────────────────

    def get_prices_raw(self, market_id, num_prices=-1):
        """
        Get full price ladder for a market (raw XML parsing).

        Args:
            market_id: The market ID.
            num_prices: Number of price levels (-1 for all).

        Returns dict with market info and selections with back/lay prices.
        """
        root = self._soap_request(
            self.READONLY_URL, 'GetPrices',
            f'<GetPrices xmlns="{self.NS}">'
            f'<getPricesRequest ThresholdAmount="0" '
            f'NumberForPricesRequired="{num_prices}" '
            f'NumberAgainstPricesRequired="{num_prices}" '
            f'WantSelectionsMatchedAmounts="true" '
            f'WantSelectionMatchedDetails="true">'
            f'<MarketIds>{market_id}</MarketIds>'
            f'</getPricesRequest></GetPrices>',
        )
        market_el = root.find(f'.//{self._ns("MarketPrices")}')
        if market_el is None:
            return None

        market = {
            'id': int(market_el.get('Id')),
            'name': market_el.get('Name'),
            'status': int(market_el.get('Status', 0)),
            'start_time': market_el.get('StartTime'),
            'in_running': market_el.get('IsCurrentlyInRunning') == 'true',
            'total_matched': market_el.get('TotalMatchedAmount', '0'),
            'selections': [],
        }

        for sel_el in market_el.findall(self._ns('Selections')):
            sel = {
                'id': int(sel_el.get('Id')),
                'name': sel_el.get('Name'),
                'status': int(sel_el.get('Status', 0)),
                'last_price': sel_el.get('LastMatchedPrice'),
                'last_matched_at': sel_el.get('LastMatchedOccurredAt'),
                'matched_for': sel_el.get('MatchedSelectionForStake', '0'),
                'matched_against': sel_el.get('MatchedSelectionAgainstStake', '0'),
                'back': [],   # ForSidePrices (available to back)
                'lay': [],    # AgainstSidePrices (available to lay)
            }
            for p in sel_el.findall(self._ns('ForSidePrices')):
                sel['back'].append({
                    'price': float(p.get('Price')),
                    'stake': float(p.get('Stake')),
                })
            for p in sel_el.findall(self._ns('AgainstSidePrices')):
                sel['lay'].append({
                    'price': float(p.get('Price')),
                    'stake': float(p.get('Stake')),
                })
            market['selections'].append(sel)

        return market

    # ── Market Info ─────────────────────────────────────────────────────

    def get_market_info(self, market_id):
        """Get detailed info about a market including selections."""
        root = self._soap_request(
            self.READONLY_URL, 'GetMarketInformation',
            f'<GetMarketInformation xmlns="{self.NS}">'
            f'<getMarketInformationRequest>'
            f'<MarketIds>{market_id}</MarketIds>'
            f'</getMarketInformationRequest></GetMarketInformation>',
        )
        market_el = root.find(f'.//{self._ns("Markets")}')
        if market_el is None:
            return None
        selections = []
        for sel in market_el.findall(self._ns('Selections')):
            selections.append({
                'id': int(sel.get('Id')),
                'name': sel.get('Name'),
                'status': int(sel.get('Status', 0)),
            })
        return {
            'id': int(market_el.get('Id')),
            'name': market_el.get('Name'),
            'type': market_el.get('Type'),
            'status': int(market_el.get('Status', 0)),
            'start_time': market_el.get('StartTime'),
            'selections': selections,
        }

    # ── Display helpers ─────────────────────────────────────────────────

    def print_prices(self, market_id, num_prices=-1):
        """Fetch and pretty-print the price ladder for a market."""
        data = self.get_prices_raw(market_id, num_prices)
        if not data:
            print(f"  No data for market {market_id}")
            return

        print(f"\n  {data['name']} (ID: {data['id']})")
        print(f"  Start: {data['start_time']}  In-Running: {data['in_running']}")
        print(f"  Total Matched: £{data['total_matched']}")

        for sel in data['selections']:
            last = sel['last_price'] or '-'
            print(f"\n  {sel['name']} (Last: {last})")
            print(f"    {'To Back':>20}  |  {'To Lay':<20}")
            print(f"    {'Price':>8} {'Stake':>10}  |  {'Price':>8} {'Stake':>10}")
            print(f"    {'-'*8} {'-'*10}  |  {'-'*8} {'-'*10}")
            max_rows = max(len(sel['back']), len(sel['lay']))
            for i in range(max_rows):
                b = f"{sel['back'][i]['price']:>8.2f} £{sel['back'][i]['stake']:>9.2f}" if i < len(sel['back']) else ' ' * 20
                l = f"{sel['lay'][i]['price']:>8.2f} £{sel['lay'][i]['stake']:>9.2f}" if i < len(sel['lay']) else ''
                print(f"    {b}  |  {l}")

    def print_event_tree(self, event_id, direct_only=True):
        """Fetch and pretty-print the event tree."""
        tree = self.get_event_tree(event_id, direct_only)
        for e in tree['events']:
            print(f"  Event:  {e['id']:<12} {e['name']}")
        for m in tree['markets']:
            print(f"  Market: {m['id']:<12} {m['name']}")


# ── Interactive Mode ────────────────────────────────────────────────────────

def interactive(client):
    print("=" * 60)
    print("  Betdaq API Client - Interactive Mode")
    print("=" * 60)
    print()
    print("Commands:")
    print("  1  - Get account balances")
    print("  2  - List top-level events (sports)")
    print("  3  - Browse event tree (enter event ID)")
    print("  4  - Get live prices (enter market ID)")
    print("  5  - Search events (enter sport ID + search term)")
    print("  q  - Quit")
    print()

    while True:
        try:
            cmd = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        try:
            if cmd == "q":
                break
            elif cmd == "1":
                print(client.get_account_balances())
            elif cmd == "2":
                for e in client.list_top_level_events():
                    print(f"  {e['id']:<12} {e['name']}")
            elif cmd == "3":
                eid = input("  Event ID: ").strip()
                client.print_event_tree(int(eid))
            elif cmd == "4":
                mid = input("  Market ID: ").strip()
                client.print_prices(int(mid))
            elif cmd == "5":
                sid = input("  Sport ID: ").strip()
                term = input("  Search: ").strip()
                results = client.search_events(int(sid), term)
                for e in results:
                    print(f"  {e['id']:<12} {e['name']}")
            else:
                print("Unknown command.")
        except Exception as e:
            print(f"  Error: {e}")


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os

    USERNAME = os.environ.get("BETDAQ_USERNAME", "")
    PASSWORD = os.environ.get("BETDAQ_PASSWORD", "")

    if not USERNAME or not PASSWORD:
        # Try .env file
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
            USERNAME = os.environ.get("BETDAQ_USERNAME", "")
            PASSWORD = os.environ.get("BETDAQ_PASSWORD", "")

    if not USERNAME or not PASSWORD:
        print("Set your credentials via environment variables or .env file:")
        print("  export BETDAQ_USERNAME=your_username")
        print("  export BETDAQ_PASSWORD=your_password")
        print()
        print("Or create a .env file with:")
        print("  BETDAQ_USERNAME=your_username")
        print("  BETDAQ_PASSWORD=your_password")
        sys.exit(1)

    client = BetdaqClient(USERNAME, PASSWORD)

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive(client)
    else:
        print("Connecting to Betdaq API...")
        print(f"  User: {USERNAME}")
        print()

        bal = client.get_account_balances()
        print(f"  Balance: £{bal.get('balance', 'N/A')} ({bal.get('currency', '')})")
        print()

        print("Sports:")
        for e in client.list_top_level_events():
            print(f"  {e['id']:<12} {e['name']}")
