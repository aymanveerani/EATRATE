"""
Curated canonical domains for major US restaurant chains.

Google/Yelp sometimes hand us a location-finder subdomain
(locations.whataburger.com) that 404s at its root, or no website at all for
a given franchise location, even though the chain obviously has a real,
well-known logo. This table resolves a reliable domain for exactly those
cases — checked against a restaurant's normalized name (see _normalize_name
in server/app.py) by substring containment: `key in normalized_name`.

Keys are deliberately the shortest distinctive root of the brand name, not
the full listing name — "panera" not "panerabread", "outback" not
"outbacksteakhouse" — because a chain shows up under slightly different
name variants ("Panera" vs. "Panera Bread", "Outback" vs. "Outback
Steakhouse") depending on the source and location, and the key must appear
*inside* whatever the real listing name normalizes to. A key longer than
the shortest real-world variant silently never matches.

This is a curated list, not an exhaustive one — there's no web-crawling
tool available in this environment to discover "every" chain automatically,
so it covers the major national and large regional chains a US user is
most likely to actually encounter. Every domain here was verified directly
against the real site (see server/logo_fetch.py), not guessed.
"""

CHAIN_DOMAINS = {
    # Burgers / fast food
    "mcdonalds": "mcdonalds.com",
    "burgerking": "bk.com",
    "wendys": "wendys.com",
    "whataburger": "whataburger.com",
    "innout": "in-n-out.com",
    "fiveguys": "fiveguys.com",
    "shakeshack": "shakeshack.com",
    "culvers": "culvers.com",
    "sonic": "sonicdrivein.com",
    "jackinthebox": "jackinthebox.com",
    "carlsjr": "carlsjr.com",
    "hardees": "hardees.com",
    "whitecastle": "whitecastle.com",
    "checkers": "checkers.com",
    "raisingcanes": "raisingcanes.com",
    "freddys": "freddys.com",
    "steaknshake": "steaknshake.com",
    "smashburger": "smashburger.com",

    # Chicken
    "chickfila": "chick-fil-a.com",
    "kfc": "kfc.com",
    "popeyes": "popeyes.com",
    "zaxbys": "zaxbys.com",
    "bojangles": "bojangles.com",
    "churchs": "churchschicken.com",
    "wingstop": "wingstop.com",
    "buffalowild": "buffalowildwings.com",
    "elpolloloco": "elpolloloco.com",

    # Pizza
    "pizzahut": "pizzahut.com",
    "dominos": "dominos.com",
    "papajohns": "papajohns.com",
    "littlecaesars": "littlecaesars.com",
    "papamurphys": "papamurphys.com",
    "marcospizza": "marcos.com",
    "modpizza": "modpizza.com",
    "blazepizza": "blazepizza.com",
    "cicis": "cicis.com",

    # Mexican
    "chipotle": "chipotle.com",
    "qdoba": "qdoba.com",
    "moes": "moes.com",
    "deltaco": "deltaco.com",
    "tacobell": "tacobell.com",

    # Sandwiches / subs
    "subway": "subway.com",
    "jimmyjohns": "jimmyjohns.com",
    "jerseymikes": "jerseymikes.com",
    "firehousesubs": "firehousesubs.com",
    "potbelly": "potbelly.com",
    "quiznos": "quiznos.com",
    "panera": "panerabread.com",

    # Coffee / bakery / dessert
    "starbucks": "starbucks.com",
    "dunkin": "dunkindonuts.com",
    "timhortons": "timhortons.com",
    "peets": "peets.com",
    "cariboucoffee": "cariboucoffee.com",
    "krispykreme": "krispykreme.com",
    "cinnabon": "cinnabon.com",
    "baskinrobbins": "baskinrobbins.com",
    "coldstone": "coldstonecreamery.com",
    "dairyqueen": "dairyqueen.com",
    "smoothieking": "smoothieking.com",
    "jamba": "jambajuice.com",
    "menchies": "menchies.com",

    # Asian
    "pandaexpress": "pandaexpress.com",
    "pfchangs": "pfchangs.com",
    "noodlescompany": "noodles.com",

    # Casual / family dining
    "applebees": "applebees.com",
    "chilis": "chilis.com",
    "olivegarden": "olivegarden.com",
    "outback": "outback.com",
    "texasroadhouse": "texasroadhouse.com",
    "redlobster": "redlobster.com",
    "tgifridays": "tgifridays.com",
    "ihop": "ihop.com",
    "dennys": "dennys.com",
    "crackerbarrel": "crackerbarrel.com",
    "wafflehouse": "wafflehouse.com",
    "rubytuesday": "rubytuesday.com",
    "cheesecakefactory": "thecheesecakefactory.com",
    "bjsrestaurant": "bjsrestaurants.com",
    "redrobin": "redrobin.com",
    "longhornsteakhouse": "longhornsteakhouse.com",
    "logansroadhouse": "logansroadhouse.com",
    "saltgrass": "saltgrass.com",
    "bostonmarket": "bostonmarket.com",
    "goldencorral": "goldencorral.com",
    "sizzler": "sizzler.com",
    "carrabbas": "carrabbas.com",
    "bonefishgrill": "bonefishgrill.com",

    # Other
    "chuckecheese": "chuckecheese.com",
    "dickeys": "dickeys.com",
}
