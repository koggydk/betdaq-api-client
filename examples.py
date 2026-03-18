"""
Examples: How to use the Betdaq API client for different sports.

Run: python examples.py
"""

from betdaq_client import BetdaqClient

client = BetdaqClient("godivaspires", "Beaumaris1!")


# ═══════════════════════════════════════════════════════════════════════════
# NAVIGATING THE API
# ═══════════════════════════════════════════════════════════════════════════
#
# Betdaq organises events in a tree:
#
#   Sport (top-level)
#     └── Competition / League
#           └── Match / Event
#                 └── Market (Match Odds, Over/Under, etc.)
#                       └── Selection (Team A, Draw, Team B, etc.)
#                             └── Prices (Back / Lay)
#
# To get prices, you need to drill down:
#   1. list_top_level_events()  → get sport ID
#   2. get_event_tree(sport_id) → get competition IDs
#   3. get_event_tree(comp_id)  → get match IDs + market IDs
#   4. get_prices_raw(market_id) → get selections + back/lay prices
#
# Or use search_events() to skip straight to a match.
# ═══════════════════════════════════════════════════════════════════════════


def example_nhl():
    """
    NHL Ice Hockey example.

    Sport ID: 100032 (Ice Hockey)
    └── 10791795 (NHL)
        └── Individual matches
            └── Markets: Winner (incl. OT), Match Odds, Handicap, Totals
    """
    print("\n" + "=" * 60)
    print("  NHL ICE HOCKEY")
    print("=" * 60)

    # Step 1: Get NHL sub-events (matches)
    nhl = client.get_event_tree(10791795)  # NHL competition ID
    print("\nUpcoming NHL matches:")
    for e in nhl['events']:
        print(f"  {e['id']:<12} {e['name']}")

    # Step 2: Search for a specific match
    matches = client.search_events(100032, "Colorado")
    if matches:
        match = matches[0]
        print(f"\nFound: {match['name']} (ID: {match['id']})")

        # Step 3: Get markets for this match
        tree = client.get_event_tree(match['id'])
        print("\nMarkets:")
        for m in tree['markets']:
            print(f"  {m['id']:<12} {m['name']}")

        # Step 4: Get prices for the first market (usually Winner)
        if tree['markets']:
            client.print_prices(tree['markets'][0]['id'])


def example_football():
    """
    Football (Soccer) example.

    Sport ID: 100003 (Soccer)
    └── Competitions (Premier League, Champions League, etc.)
        └── Individual matches
            └── Markets: Match Odds, BTTS, Over/Under, Correct Score, etc.

    Soccer has the most liquidity on Betdaq. Typical markets:
      - Match Odds (1X2)
      - Draw No Bet
      - Both Teams to Score
      - Total Goals (Over/Under 0.5 through 6.5)
      - Handicap markets
      - Correct Score
      - Half-Time/Full-Time
      - First-Half markets
    """
    print("\n" + "=" * 60)
    print("  FOOTBALL (SOCCER)")
    print("=" * 60)

    # Step 1: List soccer competitions
    soccer = client.get_event_tree(100003)
    print("\nSoccer competitions:")
    for e in soccer['events'][:15]:
        print(f"  {e['id']:<12} {e['name']}")
    if len(soccer['events']) > 15:
        print(f"  ... and {len(soccer['events']) - 15} more")

    # Step 2: Search for a team
    matches = client.search_events(100003, "Liverpool")
    print(f"\nLiverpool matches found: {len(matches)}")
    for m in matches:
        print(f"  {m['id']:<12} {m['name']}")

    # Step 3: Get markets for first match
    if matches:
        match = matches[0]
        tree = client.get_event_tree(match['id'])
        print(f"\nMarkets for {match['name']}:")
        for m in tree['markets']:
            print(f"  {m['id']:<12} {m['name']}")

        # Step 4: Get Match Odds prices
        match_odds = [m for m in tree['markets'] if m['name'] == 'Match Odds']
        if match_odds:
            client.print_prices(match_odds[0]['id'])


def example_horse_racing():
    """
    Horse Racing example.

    Sport ID: 100004 (Horse Racing)
    └── Date/Venue (e.g. "Cheltenham 18th Mar")
        └── Individual races
            └── Markets: Win, Place, etc.
                └── Selections: Individual horses

    Horse racing has the MOST liquidity on Betdaq.
    """
    print("\n" + "=" * 60)
    print("  HORSE RACING")
    print("=" * 60)

    # Step 1: Get today's meetings
    racing = client.get_event_tree(100004)
    print("\nMeetings:")
    for e in racing['events']:
        print(f"  {e['id']:<12} {e['name']}")

    # Step 2: Get races at first venue
    if racing['events']:
        venue = racing['events'][0]
        races = client.get_event_tree(venue['id'])
        print(f"\nRaces at {venue['name']}:")
        for e in races['events']:
            print(f"  {e['id']:<12} {e['name']}")
        for m in races['markets']:
            print(f"  Market: {m['id']:<12} {m['name']}")

        # Step 3: Get prices for first market with markets
        if races['markets']:
            client.print_prices(races['markets'][0]['id'])
        elif races['events']:
            # Drill one more level
            race = client.get_event_tree(races['events'][0]['id'])
            if race['markets']:
                client.print_prices(race['markets'][0]['id'])


def example_tennis():
    """
    Tennis example.

    Sport ID: 100005 (Tennis)
    └── Tournament (e.g. ATP Miami Open)
        └── Individual matches
            └── Markets: Match Odds, Set Winner, etc.
    """
    print("\n" + "=" * 60)
    print("  TENNIS")
    print("=" * 60)

    tennis = client.get_event_tree(100005)
    print("\nTennis competitions:")
    for e in tennis['events']:
        print(f"  {e['id']:<12} {e['name']}")

    # Search for a player
    matches = client.search_events(100005, "Djokovic")
    if matches:
        print(f"\nDjokovic matches:")
        for m in matches:
            print(f"  {m['id']:<12} {m['name']}")


def example_programmatic():
    """
    Example: Programmatically find and display prices.

    This shows how to go from sport → match → prices in code.
    """
    print("\n" + "=" * 60)
    print("  PROGRAMMATIC USAGE")
    print("=" * 60)

    # Find all NHL matches with liquidity
    nhl = client.get_event_tree(10791795)
    print("\nChecking NHL markets for liquidity...")

    for event in nhl['events'][:5]:  # Check first 5 matches
        markets = client.get_event_tree(event['id'])
        for mkt in markets['markets']:
            if 'Winner' in mkt['name']:
                prices = client.get_prices_raw(mkt['id'])
                if prices and float(prices['total_matched']) > 0:
                    print(f"\n  {event['name']}")
                    print(f"    Market: {mkt['name']} - Matched: £{prices['total_matched']}")
                    for sel in prices['selections']:
                        best_back = sel['back'][0]['price'] if sel['back'] else '-'
                        best_lay = sel['lay'][0]['price'] if sel['lay'] else '-'
                        print(f"    {sel['name']:<30} Back: {best_back:<8} Lay: {best_lay}")
                break  # Only check Winner market per match


# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Betdaq API Examples")
    print("=" * 60)

    # Run whichever examples you want:
    example_nhl()
    example_football()
    # example_horse_racing()
    # example_tennis()
    # example_programmatic()
