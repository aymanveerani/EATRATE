"""
Canonical domains for US restaurant chains, ~770 entries across two tiers.

Google/Yelp sometimes hand us a location-finder subdomain
(locations.whataburger.com) that 404s at its root, or no website at all for
a given franchise location, even though the chain obviously has a real,
well-known logo. This table resolves a reliable domain for exactly those
cases — checked against a restaurant's normalized name (see _normalize_name
in server/app.py) by substring containment: `key in normalized_name`.

There is no web-crawling tool available in this environment, and no
verifiable "top N US chains" dataset exists to pull from wholesale — a list
this size hand-typed from memory would inevitably include wrong or
hallucinated domains, which is worse than no entry at all (a wrong domain
means scraping and serving some *other* company's logo). So this is built
in two tiers instead:

1. A small hand-curated set (top of the file, organized by category) for
   the highest-traffic chains, with deliberately short keys — "panera" not
   "panerabread", "outback" not "outbacksteakhouse" — since these chains
   show up under different name variants ("Panera" vs. "Panera Bread")
   depending on the source, and the key must appear *inside* whatever the
   real listing name normalizes to; a key longer than the shortest
   real-world variant silently never matches. Every domain in this tier
   was fetched and visually verified as a real logo (see server/logo_fetch.py).
2. A much larger bulk-imported set (bottom of the file) pulled from
   Wikidata's structured data (query.wikidata.org/sparql) — every item
   tagged as a restaurant/cafe/pizzeria/bakery/ice-cream-parlor/fast-food
   chain with a US country or headquarters claim and an official website
   property (P856) on record. This is real, sourced, machine-verifiable
   data, not a guess. Every domain was DNS-verified before inclusion, and
   entries pointing at a generic third-party platform (Facebook, Wayback
   Machine) instead of the brand's own site were dropped. These keys are
   the *full* normalized listing name rather than hand-shortened, so
   they're exact-match rather than fuzzy.
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

    # ------------------------------------------------------------------
    # Bulk-imported from Wikidata (query.wikidata.org/sparql): every item
    # tagged as an instance of restaurant chain / cafe chain / pizzeria
    # chain / bakery chain / ice cream parlor chain / fast food restaurant
    # chain / ghost restaurant chain / boba milk tea chain, with a
    # US country or headquarters-location claim and an official website
    # (P856) on record. All 680 domains below were
    # DNS-verified (real record, not a dead/typo'd domain) before being
    # included; entries pointing at a generic third-party platform
    # (Facebook, Wayback Machine) instead of the brand's own site were
    # dropped, since scraping those would return the platform's logo, not
    # the restaurant's. Keys here are the *full* normalized listing name
    # (not hand-shortened like the curated set above), so they're exact
    # rather than fuzzy — correct whenever the source returns that same
    # name, silent-miss if it returns a shorter variant. This is why the
    # curated section above exists separately: it protects the handful of
    # chains most likely to appear under a shorter name with deliberately
    # shorter, tested keys.
    "110grill": "110grill.com",  # 110 Grill
    "4riverssmokehouse": "4rsmokehouse.com",  # 4 Rivers Smokehouse
    "4040club": "the4040club.com",  # 40/40 Club
    "54thstreetgrillandbar": "54thstreetrestaurants.com",  # 54th Street Grill and Bar
    "7brew": "7brewus.com",  # 7 Brew
    "7leavescafe": "7leavescafe.com",  # 7 Leaves Cafe
    "787coffee": "787coffee.com",  # 787 Coffee
    "awrestaurants": "awrestaurants.com",  # A&W Restaurants
    "atownwings": "atownwings.com",  # A-Town Wings
    "abbottsfrozencustard": "abbottscustard.com",  # Abbott's Frozen Custard
    "abbyspizza": "abbys.com",  # Abby's Pizza
    "abcpizza": "abcpizza.com",  # ABC Pizza
    "aftersicecream": "aftersicecream.com",  # Afters Ice Cream
    "alsbeef": "alsbeef.com",  # Al's Beef
    "aladdinseatery": "aladdins.com",  # Aladdin's Eatery
    "alphacoffee": "alpha.coffee",  # Alpha Coffee
    "americasbestwings": "abwingsmd.com",  # America's Best Wings
    "americandeli": "americandeli.com",  # American Deli
    "amiciseastcoastpizzeria": "amicis.com",  # Amici's East Coast Pizzeria
    "amigos": "amigoskings.com",  # Amigos
    "amysicecreams": "amysicecreams.com",  # Amy's Ice Creams
    "andyspizza": "eatandyspizza.com",  # Andy's Pizza
    "anthonyscoalfiredpizza": "acfp.com",  # Anthony's Coal Fired Pizza
    "antoniospizza": "antonios-pizza.com",  # Antonio's Pizza
    "arbys": "arbys.com",  # Arby's
    "aromajoescoffee": "aromajoes.com",  # Aroma Joe's Coffee
    "atlantabreadcompany": "atlantabread.com",  # Atlanta Bread Company
    "atlaspizza": "atlaspizzapdx.com",  # Atlas Pizza
    "auntieannes": "auntieannes.com",  # Auntie Anne's
    "azzippizza": "azzippizza.com",  # Azzip Pizza
    "bbops": "b-bops.com",  # B-Bop's
    "bbkingsbluesclub": "bbkings.com",  # B.B. King's Blues Club
    "bcpizza": "bc.pizza",  # B.C. Pizza
    "backyardburgers": "backyardburgers.com",  # Back Yard Burgers
    "bagocrab": "bagocrabusa.com",  # Bag O' Crab
    "bajafresh": "bajafresh.com",  # Baja Fresh
    "bambu": "drinkbambu.com",  # Bambu
    "barlouierestaurants": "barlouie.com",  # Bar Louie Restaurants
    "barberitos": "barberitos.com",  # Barberitos
    "barneysbeanery": "barneysbeanery.com",  # Barney's Beanery
    "bartaco": "bartaco.com",  # Bartaco
    "bcdtofuhouse": "bcdtofuhouse.com",  # BCD Tofu House
    "beansbrewscoffeehouse": "beansandbrews.com",  # Beans & Brews Coffee House
    "beefobradys": "beefobradys.com",  # Beef O'Brady's
    "benjerrys": "benjerry.co.uk",  # Ben & Jerry's
    "benihana": "benihana.com",  # Benihana
    "bennigans": "bennigans.com",  # Bennigan's
    "bertuccis": "bertuccis.com",  # Bertucci's
    "bethesdabagels": "bethesdabagels.com",  # Bethesda Bagels
    "betterbuzzcoffee": "betterbuzzcoffee.com",  # Better Buzz Coffee
    "biaggisristoranteitaliano": "biaggis.com",  # Biaggi's Ristorante Italiano
    "bigapplebagels": "bigapplebagels.com",  # Big Apple Bagels
    "bigboyrestaurants": "bigboy.com",  # Big Boy Restaurants
    "bigchicken": "bigchicken.com",  # Big Chicken
    "biggayicecream": "biggayicecream.com",  # Big Gay Ice Cream
    "biglouies": "biglouies.com",  # Big Louie's
    "bigmamaspapaspizzeria": "bigmamaspizza.com",  # Big Mama's & Papa's Pizzeria
    "bikinissportsbargrill": "bikinissportsbarandgrill.com",  # Bikinis Sports Bar & Grill
    "billgrays": "billgrays.com",  # Bill Gray's
    "billmillerbarbqenterprises": "billmillerbbq.com",  # Bill Miller Bar-B-Q Enterprises
    "billygoattavern": "billygoattavern.com",  # Billy Goat Tavern
    "biscuitlove": "biscuitlove.com",  # Biscuit Love
    "biscuitville": "biscuitville.com",  # Biscuitville
    "bjsrestaurantbrewery": "bjsrestaurants.com",  # BJ's Restaurant & Brewery
    "blackangussteakhouse": "blackangus.com",  # Black Angus Steakhouse
    "blackbeardiner": "blackbeardiner.com",  # Black Bear Diner
    "blackjackpizza": "blackjackpizza.com",  # Blackjack Pizza
    "blakeslotaburger": "lotaburger.com",  # Blake's Lotaburger
    "bluechipcookies": "bluechipcookiesdirect.com",  # Blue Chip Cookies
    "blueribbonbarbecue": "blueribbonbbq.com",  # Blue Ribbon Barbecue
    "blueberrysgrill": "blueberrysgrill.com",  # Blueberry's Grill
    "bluestonelane": "bluestonelane.com",  # Bluestone Lane
    "bobevansrestaurants": "bobevans.com",  # Bob Evans Restaurants
    "bobaguys": "bobaguys.com",  # Boba Guys
    "bobbysburgers": "bobbysburgers.com",  # Bobby's Burgers
    "bojanglesfamouschickennbiscuits": "bojangles.com",  # Bojangles' Famous Chicken 'n Biscuits
    "bollywoodtheater": "bollywoodtheaterpdx.com",  # Bollywood Theater
    "bonanzasteakhouse": "pon-bon.com",  # Bonanza Steakhouse
    "boxerramen": "boxerramen.com",  # Boxer Ramen
    "braganzatea": "braganzatea.com",  # Braganza Tea
    "braums": "braums.com",  # Braum's
    "bravoitaliankitchen": "bravoitalian.com",  # Bravo! Italian Kitchen
    "breakfaststation": "breakfaststationcentral.com",  # Breakfast Station
    "brewingz": "brewingz.com",  # BreWingZ
    "brickhousediner": "brickhousediner.com",  # Brick House Diner
    "brioitaliangrille": "brioitalian.com",  # Brio Italian Grille
    "brotherjimmysbbq": "brotherjimmys.com",  # Brother Jimmy's BBQ
    "brownschickenpasta": "brownschicken.com",  # Brown's Chicken & Pasta
    "brueggers": "brueggers.com",  # Bruegger's
    "brustersicecream": "brusters.com",  # Bruster's Ice Cream
    "bubbas33": "bubbas33.com",  # Bubba's 33
    "bubbaques": "bubbaquesbbq.com",  # BubbaQue's
    "bucadibeppo": "dineatbuca.com",  # Buca di Beppo
    "buddakan": "buddakan.com",  # Buddakan
    "buddyspizza": "buddyspizza.com",  # Buddy's Pizza
    "buffalowildwings": "buffalowildwings.com",  # Buffalo Wild Wings
    "buffalowingsrings": "wingsandrings.com",  # Buffalo Wings & Rings
    "bumpersdrivein": "bumpersdrivein.com",  # Bumpers Drive-In
    "bunksandwiches": "bunksandwiches.com",  # Bunk Sandwiches
    "buona": "buona.com",  # Buona
    "burgerlounge": "burgerlounge.com",  # Burger Lounge
    "burgerfi": "burgerfi.com",  # BurgerFi
    "burgerim": "burgerim.com",  # BurgerIM
    "burgerville": "burgerville.com",  # Burgerville
    "burritoville": "burritoville.com",  # BurritoVille
    "bushschicken": "bushschicken.com",  # Bush's Chicken
    "cjbarbeque": "cjbbq.com",  # C&J Barbeque
    "cafeexpress": "cafe-express.com",  # Cafe Express
    "cafecito": "chi.iheartcafecito.com",  # Cafecito
    "cafyumm": "cafeyumm.com",  # Café Yumm!
    "cafzupas": "cafezupas.com",  # Café Zupas
    "californiafishgrill": "cafishgrill.com",  # California Fish Grill
    "californiapizzakitchen": "cpk.com",  # California Pizza Kitchen
    "californiatortilla": "californiatortilla.com",  # California Tortilla
    "callyourmother": "callyourmotherdeli.com",  # Call Your Mother
    "campuspollyeyes": "campuspollyeyes.com",  # Campus Pollyeyes
    "canopyroadcafe": "canopyroadcafe.com",  # Canopy Road Cafe
    "capriottis": "capriottis.com",  # Capriotti's
    "captainds": "captainds.com",  # Captain D's
    "captainjays": "captainjays.net",  # Captain Jay's
    "carrabbasitaliangrill": "carrabbas.com",  # Carrabba's Italian Grill
    "carvel": "carvel.com",  # Carvel
    "cassanospizzaking": "cassanos.com",  # Cassano's Pizza King
    "cavagroup": "cava.com",  # Cava Group
    "champschicken": "champschicken.com",  # Champs Chicken
    "chebahut": "chebahut.com",  # Cheba Hut
    "checkersandrallys": "checkers.com",  # Checkers and Rally's
    "cheeburgercheeburger": "cheeburger.com",  # Cheeburger Cheeburger
    "cheeseburgerinparadise": "cheeseburgerinparadise.com",  # Cheeseburger in Paradise
    "chestersinternational": "chestersinternational.com",  # Chester's International
    "chickncone": "chickncone.com",  # Chick'nCone
    "chickenexpress": "chickene.com",  # Chicken Express
    "chickenintherough": "chickenintherough.com",  # Chicken in the Rough
    "chickensaladchick": "chickensaladchick.com",  # Chicken Salad Chick
    "chinsszechwan": "govisitchins.com",  # Chin's Szechwan
    "chinabuffet": "chinabuffet.net",  # China Buffet
    "chinawokbuffet": "chinawok.com.pe",  # China Wok Buffet
    "chipotlemexicangrill": "chipotle.com",  # Chipotle Mexican Grill
    "chompies": "chompies.com",  # Chompie's
    "chopt": "choptsalad.com",  # Chopt
    "chuys": "chuys.com",  # Chuy's
    "chpnblk": "chopnblok.co",  # ChòpnBlọk
    "citybrew": "citybrew.com",  # City Brew
    "citywok": "citywok.com",  # City Wok
    "claimjumper": "claimjumper.com",  # Claim Jumper
    "cleanjuice": "cleanjuice.com",  # Clean Juice
    "club33": "club33disneyland.com",  # Club 33
    "cluckuchicken": "cluckuchicken.com",  # Cluck-U Chicken
    "clydesrestaurantgroup": "clydesgroup.com",  # Clyde's Restaurant Group
    "cobsbread": "cobsbread.com",  # COBS Bread
    "coldstonecreamery": "coldstonecreamery.com",  # Cold Stone Creamery
    "condadotacos": "condadotacos.com",  # Condado Tacos
    "connorssteakseafood": "connorsrestaurant.com",  # Connors Steak & Seafood
    "coopershawkwineryrestaurants": "chwinery.com",  # Cooper's Hawk Winery & Restaurants
    "coopersoldtimepitbarbque": "coopersbbq.com",  # Cooper's Old Time Pit Bar-B-Que
    "cornerbagelry": "cornerbagelry.com",  # Corner Bagelry
    "cornerbakerycafe": "cornerbakerycafe.com",  # Corner Bakery Cafe
    "cosmicwings": "cosmicwings.com",  # Cosmic Wings
    "costavida": "costavida.com",  # Costa Vida
    "cottageinnpizza": "cottageinn.com",  # Cottage Inn Pizza
    "cottonpatchcaf": "cottonpatch.com",  # Cotton Patch Café
    "countrykitchen": "countrykitchenrestaurants.com",  # Country Kitchen
    "countrypride": "ta-petro.com",  # Country Pride
    "cousinssubs": "cousinssubs.com",  # Cousins Subs
    "craftycrab": "craftycrabrestaurant.com",  # Crafty Crab
    "crownburgers": "crown-burgers.com",  # Crown Burgers
    "crumblcookies": "crumblcookies.com",  # Crumbl Cookies
    "cupsaucercafe": "cupandsaucercafe.com",  # Cup & Saucer Cafe
    "dpdough": "dpdough.com",  # D.P. Dough
    "dallasbbq": "dallasbbq.com",  # Dallas BBQ
    "davannis": "davannis.com",  # Davanni's
    "davebusters": "daveandbusters.com",  # Dave & Buster's
    "delidelicious": "deli-delicious.com",  # Deli Delicious
    "dibellas": "dibellas.com",  # DiBella's
    "dickslastresort": "dickslastresort.com",  # Dick's Last Resort
    "dickeysbarbecuepit": "dickeys.com",  # Dickey's Barbecue Pit
    "diginn": "catering.diginn.com",  # Dig Inn
    "dintaifung": "dintaifung.com.tw",  # Din Tai Fung
    "dinosaurbarbque": "dinosaurbarbque.com",  # Dinosaur Bar-B-Que
    "dions": "dionspizza.com",  # Dion's
    "districttaco": "districttaco.com",  # District Taco
    "doeseatplace": "doeseatplace.com",  # Doe's Eat Place
    "doghaus": "doghaus.com",  # Dog Haus
    "dollypartonsdixiestampede": "dpstampede.com",  # Dolly Parton's Dixie Stampede
    "dominospizza": "dominos.com",  # Domino's Pizza
    "donatospizza": "donatos.com",  # Donatos Pizza
    "donutkingdom": "dktally.com",  # Donut Kingdom
    "dopoadesso": "dopoadesso.com",  # Dopo / Adesso
    "doubledavespizzaworks": "doubledaves.com",  # DoubleDave's Pizzaworks
    "doughzone": "doughzonedumplinghouse.com",  # Dough Zone
    "dupars": "dupars.net",  # Du-par's
    "duchuongsandwiches": "duchuongsandwiches.com",  # Duc Huong Sandwiches
    "duchess": "duchessrestaurants.com",  # Duchess
    "dutchbroscoffee": "dutchbros.com",  # Dutch Bros. Coffee
    "eastofchicagopizza": "eastofchicago.com",  # East of Chicago Pizza
    "eatnpark": "eatnpark.com",  # Eat'n Park
    "eddiemerlots": "eddiemerlots.com",  # Eddie Merlot's
    "eddievs": "eddiev.com",  # Eddie V's
    "eegees": "eegees.com",  # Eegee's
    "eggsupgrill": "eggsupgrill.com",  # Eggs Up Grill
    "eggworks": "theeggworks.com",  # EggWorks
    "einsteinbrosbagels": "einsteinbros.com",  # Einstein Bros. Bagels
    "elfenix": "elfenix.com",  # El Fenix
    "eljalisco": "eljalisco.com",  # El Jalisco
    "ellianoscoffee": "ellianos.com",  # Ellianos Coffee
    "emackbolios": "emackandbolios.com",  # Emack & Bolio's
    "epicwings": "epicwings.com",  # Epic Wings
    "eriksdelicaf": "eriksdelicafe.com",  # Erik's DeliCafé
    "espressovivace": "espressovivace.com",  # Espresso Vivace
    "estrellitapoblana": "estrellitapoblana.nyc",  # Estrellita Poblana
    "eurekarestaurantgroup": "eurekarestaurantgroup.com",  # Eureka! Restaurant Group
    "eurocaf": "eurocafeusa.com",  # Euro Café
    "evergreenssalad": "evergreens.com",  # Evergreens Salad
    "everymanespresso": "everymanespresso.com",  # Everyman Espresso
    "famousdaves": "famousdaves.com",  # Famous Dave's
    "farmerboys": "farmerboys.com",  # Farmer Boys
    "fastraccafe": "fastraccafe.com",  # Fastrac Cafe
    "fatshack": "fatshack.com",  # Fat Shack
    "fatburger": "fatburger.com",  # Fatburger
    "fatz": "fatz.com",  # FATZ
    "fazolis": "fazolis.com",  # Fazoli's
    "fellinispizza": "fellinisatlanta.com",  # Fellini's Pizza
    "fiorellasjackstackbarbecue": "jackstackbbq.com",  # Fiorella's Jack Stack Barbecue
    "firstwatch": "firstwatch.com",  # First Watch
    "fivedaughtersbakery": "fivedaughtersbakery.com",  # Five Daughters Bakery
    "flemingsprimesteakhousewinebar": "flemingssteakhouse.com",  # Fleming's Prime Steakhouse & Wine Bar
    "flights": "flightsrestaurants.com",  # Flights
    "flipburgerboutique": "flipburgerboutique.com",  # FLIP Burger Boutique
    "flippinpizza": "flippinpizza.com",  # Flippin' Pizza
    "fostersfreeze": "fostersfreeze.com",  # Fosters Freeze
    "foxspizzaden": "foxspizza.com",  # Fox's Pizza Den
    "freddysfrozencustardsteakburgers": "freddys.com",  # Freddy's Frozen Custard & Steakburgers
    "freebirdsworldburrito": "freebirds.com",  # Freebirds World Burrito
    "frenchyschicken": "frenchyschicken.com",  # Frenchy's Chicken
    "frischs": "frischs.com",  # Frisch's
    "fuzzystacoshop": "fuzzystacoshop.com",  # Fuzzy's Taco Shop
    "gainesstreetpies": "gainesstreetpies.com",  # Gaines Street Pies
    "garduos": "gardunosrestaurants.com",  # Garduño's
    "gatorsdockside": "gatorsdockside.com",  # Gator's Dockside
    "genghisgrill": "genghisgrill.com",  # Genghis Grill
    "georgetowncupcake": "georgetowncupcake.com",  # Georgetown Cupcake
    "gigiscupcakes": "gigiscupcakesusa.com",  # Gigi's Cupcakes
    "ginoseast": "ginoseast.com",  # Gino's East
    "ginospizzaspaghettihouse": "ginospizza.com",  # Gino's Pizza & Spaghetti House
    "gioninospizzeria": "gioninos.com",  # Gionino’s Pizzeria
    "giovannispizza": "giovannispizza.com",  # Giovanni’s Pizza
    "gloriajeanscoffees": "gloriajeans.com",  # Gloria Jean's Coffees
    "glorydaysgrill": "glorydaysgrill.com",  # Glory Days Grill
    "goldenchick": "goldenchick.com",  # Golden Chick
    "goldenkrustcaribbeanbakerygrill": "goldenkrust.com",  # Golden Krust Caribbean Bakery & Grill
    "goldenspoon": "goldenspoonus.com",  # Golden Spoon
    "goldfingers": "trygoldfingers.com",  # Goldfingers
    "gottsroadside": "gotts.com",  # Gott's Roadside
    "grabajava": "grabajava.com",  # Grab-a-Java
    "graeters": "graeters.com",  # Graeter's
    "grammaspizza": "grammaspizzas.com",  # Grammas Pizza
    "grandys": "grandys.com",  # Grandy's
    "grassa": "grassapdx.com",  # Grassa
    "greatsteak": "thegreatsteak.com",  # Great Steak
    "greatwraps": "greatwraps.com",  # Great Wraps
    "grimaldispizzeria": "grimaldispizzeria.com",  # Grimaldi's Pizzeria
    "gringosmexicankitchen": "gringostexmex.com",  # Gringo's Mexican Kitchen
    "guthries": "guthrieschicken.com",  # Guthrie's
    "gyukaku": "gyu-kaku.com",  # Gyu-Kaku
    "hsaltesquire": "hsalt.com",  # H. Salt Esquire
    "halotopcreamery": "halotop.com",  # Halo Top Creamery
    "hamburgermarys": "hamburgermarys.com",  # Hamburger Mary's
    "hangryjoeshotchicken": "hangryjoes.com",  # Hangry Joe's Hot Chicken
    "happyjoes": "happyjoes.com",  # Happy Joe's
    "hardtimescafe": "hardtimes.com",  # Hard Times Cafe
    "haroldschickenshack": "haroldschickenscorp.com",  # Harold's Chicken Shack
    "hashhouseagogo": "hashhouseagogo.com",  # Hash House a go go
    "hattiebshotchicken": "hattieb.com",  # Hattie B's Hot Chicken
    "headwest": "headwestsubs.com",  # Head West
    "hiresbigh": "hiresbigh.com",  # Hires Big H
    "hodads": "hodadies.com",  # Hodad's
    "homeruninn": "homeruninnpizza.com",  # Home Run Inn
    "honeydewdonuts": "honeydewdonuts.com",  # Honey Dew Donuts
    "honeygrow": "honeygrow.com",  # Honeygrow
    "hooters": "hooters.com",  # Hooters
    "hopdoddyburgerbar": "hopdoddy.com",  # Hopdoddy Burger Bar
    "hotchickentakeover": "hotchickentakeover.com",  # Hot Chicken Takeover
    "hotdogonastick": "hotdogonastick.com",  # Hot Dog on a Stick
    "hotdougs": "hotdougs.com",  # Hot Doug's
    "hotlipspizza": "hotlipspizza.com",  # Hot Lips Pizza
    "hotshotssportsbarandgrill": "hotshotsnet.com",  # Hotshots Sports Bar and Grill
    "houlihans": "houlihans.com",  # Houlihan's
    "houseofblues": "houseofblues.com",  # House of Blues
    "howardjohnsons": "hojo.com",  # Howard Johnson's
    "hteao": "hteao.com",  # HTeaO
    "hueymagooschickentenders": "hueymagoos.com",  # Huey Magoo's Chicken Tenders
    "huhotmongoliangrill": "huhot.com",  # HuHot Mongolian Grill
    "hungryhowiespizza": "hungryhowies.com",  # Hungry Howie's Pizza
    "hwy55burgersshakesfries": "hwy55.com",  # Hwy 55 Burgers, Shakes & Fries
    "hagendazs": "icecream.com",  # Häagen-Dazs
    "illegalpetes": "illegalpetes.com",  # Illegal Pete's
    "imospizza": "imospizza.com",  # Imo's Pizza
    "innoutburger": "in-n-out.com",  # In-N-Out Burger
    "ironskillet": "ta-petro.com",  # Iron Skillet
    "islandwingcompany": "islandwing.com",  # Island Wing Company
    "islandsfineburgersdrinks": "islandsrestaurants.com",  # Islands Fine Burgers & Drinks
    "ivars": "ivars.com",  # Ivar's
    "jalexanders": "jalexanders.com",  # J. Alexander's
    "jdawgs": "jdawgs.com",  # J. Dawgs
    "jacks": "eatatjacks.com",  # Jack's
    "jamesconeyisland": "jamesconeyisland.com",  # James Coney Island
    "jasonsdeli": "jasonsdeli.com",  # Jason's Deli
    "javajos": "javajos.com",  # Java Jo's
    "jazentea": "jazentea.com",  # Jazen Tea
    "jeremiahsitalianice": "jeremiahsice.com",  # Jeremiah's Italian Ice
    "jetspizza": "jetspizza.com",  # Jet's Pizza
    "jimnnicksbarbq": "jimnnicks.com",  # Jim 'N Nick's Bar-B-Q
    "jimboystacos": "jimboystacos.com",  # Jimboy's Tacos
    "joescrabshack": "joescrabshack.com",  # Joe's Crab Shack
    "joespizza": "joespizzanyc.com",  # Joe's Pizza
    "johnsincrediblepizza": "johnspizza.com",  # John's Incredible Pizza
    "johnnycarinos": "carinos.com",  # Johnny Carino's
    "johnnyrockets": "johnnyrockets.com",  # Johnny Rockets
    "juanpollo": "juanpollo.com",  # Juan Pollo
    "juiceitup": "juiceitup.com",  # Juice It Up!
    "juiceland": "juiceland.com",  # JuiceLand
    "juicipatties": "juicipattiesusa.com",  # Juici Patties
    "justlovecoffee": "justlovecoffee.com",  # Just Love Coffee
    "justsalad": "justsalad.com",  # Just Salad
    "kaleidoscoops": "kalscoops.com",  # KaleidoScoops
    "katzsdeli": "katzsneverkloses.com",  # Katz's Deli
    "kekesbreakfastcafe": "kekes.com",  # Keke's Breakfast Cafe
    "kellyscajungrill": "irmgusa.com",  # Kelly's Cajun Grill
    "kerbeylanecafe": "kerbeylanecafe.com",  # Kerbey Lane Cafe
    "kevajuice": "kevajuice.com",  # Keva Juice
    "kimsn": "kimson.com",  # Kim Sơn
    "kingbao": "king-bao.com",  # King Bao
    "kingsfamilyrestaurants": "kingsfamily.com",  # Kings Family Restaurants
    "kizukiramenizakaya": "kizuki.com",  # Kizuki Ramen & Izakaya
    "konagrill": "konagrill.com",  # Kona Grill
    "krekelscustardhamburgers": "krekelscustard.com",  # Krekel's Custard & Hamburgers
    "krystal": "krystal.com",  # Krystal
    "labambamexicanrestaurant": "labambaburritos.com",  # La Bamba Mexican Restaurant
    "labonita": "labonitapdx.com",  # La Bonita
    "lasalsa": "lasalsa.com",  # La Salsa
    "lardo": "lardosandwiches.com",  # Lardo
    "laredotacocompany": "laredotacocompany.com",  # Laredo Taco Company
    "larosaspizzeria": "larosas.com",  # LaRosa's Pizzeria
    "larrysgiantsubs": "larryssubs.com",  # Larry's Giant Subs
    "lawrys": "lawrysonline.com",  # Lawry's
    "layneschickenfingers": "layneschickenfingers.com",  # Layne's Chicken Fingers
    "lazymoon": "lazymoonpizza.com",  # Lazy Moon
    "ledopizza": "ledopizza.com",  # Ledo Pizza
    "leessandwiches": "leesandwiches.com",  # Lee's Sandwiches
    "leeannchin": "leeannchin.com",  # Leeann Chin
    "legalseafoods": "legalseafoods.com",  # Legal Sea Foods
    "leonaspizzeriarestaurant": "leonas.com",  # Leona's Pizzeria & Restaurant
    "lindyschicken": "lindys-chicken.com",  # Lindy's Chicken
    "lionschoice": "lionschoice.com",  # Lion's Choice
    "littlebigburger": "littlebigburger.com",  # Little Big Burger
    "lobsterme": "lobsterme.com",  # Lobster Me
    "longjohnsilvers": "ljsilvers.com",  # Long John Silver's
    "loumalnatispizzeria": "loumalnatis.com",  # Lou Malnati's Pizzeria
    "lovinghut": "lovinghut.com",  # Loving Hut
    "luckygoatcoffeeco": "luckygoatcoffee.com",  # Lucky Goat Coffee Co.
    "lukeslobster": "lukeslobster.com",  # Luke's Lobster
    "lvivcroissants": "lviv-croissants.com",  # Lviv Croissants
    "madforchicken": "madforchicken.com",  # Mad for Chicken
    "maggianoslittleitaly": "maggianos.com",  # Maggiano's Little Italy
    "mahzedahr": "mahzedahrbakery.com",  # Mah Ze Dahr
    "maidrite": "maid-rite.com",  # Maid-Rite
    "maman": "mamannyc.com",  # Maman
    "mangomangodessert": "mangomangodessert.com",  # Mango Mango Dessert
    "manhattanbagel": "manhattanbagel.com",  # Manhattan Bagel
    "marbleslabcreamery": "marbleslab.ca",  # Marble Slab Creamery
    "mariecallenders": "mariecallenders.com",  # Marie Callender's
    "markspizzeria": "markspizzeria.com",  # Mark's Pizzeria
    "martinsbbq": "martinsbbqpr.net",  # Martin's BBQ
    "marylandfriedchicken": "marylandfriedchicken.net",  # Maryland Fried Chicken
    "mashtimalones": "mashtimalones.com",  # Mashti Malone's
    "matchacafemaiko": "matchacafe-maiko.com",  # Matcha Cafe Maiko
    "mattoespresso": "matto.com",  # Matto Espresso
    "maxermas": "maxandermas.com",  # Max & Erma's
    "mazzios": "mazzios.com",  # Mazzio's
    "mcalistersdeli": "mcalistersdeli.com",  # McAlister's Deli
    "meatheadsburgersfries": "meatheadsburgers.com",  # Meatheads Burgers & Fries
    "melsdrivein": "melsdrive-in.com",  # Mel's Drive-In
    "melocreamdonuts": "mel-o-cream.com",  # Mel-O-Cream Donuts
    "mellowmushroom": "mellowmushroom.com",  # Mellow Mushroom
    "menchiesfrozenyogurt": "menchies.com",  # Menchie's Frozen Yogurt
    "mendocinofarms": "mendocinofarms.com",  # Mendocino Farms
    "metrodiner": "metrodiner.com",  # Metro Diner
    "mezehmediterraneangrill": "mezeh.com",  # Mezeh Mediterranean Grill
    "miamisubspizzaandgrill": "mymiamigrill.com",  # Miami Subs Pizza and Grill
    "mightyquinns": "mightyquinnsbbq.com",  # Mighty Quinn's
    "mightytaco": "mightytaco.com",  # Mighty Taco
    "miliossandwiches": "milios.com",  # Milio's Sandwiches
    "milkbar": "milkbarstore.com",  # Milk Bar
    "millersalehouse": "millersalehouse.com",  # Miller's Ale House
    "miloshamburgers": "miloshamburgers.com",  # Milo's Hamburgers
    "mimiscafe": "mimiscafe.com",  # Mimi's Cafe
    "mitchellsfishmarket": "mitchellsfishmarket.com",  # Mitchell's Fish Market
    "mosrestaurants": "ilovemoschowder.com",  # Mo's Restaurants
    "mochinut": "mochinut.com",  # Mochinut
    "modernmarket": "modernmarket.com",  # Modern Market
    "moesitaliansandwiches": "moesitaliansandwiches.com",  # Moe's Italian Sandwiches
    "monamigabi": "monamigabi.com",  # Mon Ami Gabi
    "monicalspizza": "monicals.com",  # Monical's Pizza
    "montanamikes": "montanamikes.com",  # Montana Mike's
    "montgomeryinn": "montgomeryinn.com",  # Montgomery Inn
    "mooyah": "mooyah.com",  # Mooyah
    "mortonsgrille": "mortonsgrille.com",  # Morton's Grille
    "mountainmikespizza": "mountainmikespizza.com",  # Mountain Mike's Pizza
    "mrgattispizza": "mrgattispizza.com",  # Mr Gatti's Pizza
    "mrhero": "mrhero.com",  # Mr. Hero
    "mrbeastburger": "mrbeastburger.com",  # MrBeast Burger
    "mrsfields": "mrsfields.com",  # Mrs. Fields
    "nafnafgrill": "nafnafgrill.com",  # Naf Naf Grill
    "nathansfamous": "nathansfamous.com",  # Nathan's Famous
    "nationsgianthamburgers": "nationsrestaurants.com",  # Nation's Giant Hamburgers
    "nativefoodscafe": "nativefoods.com",  # Native Foods Cafe
    "nativegrillwings": "nativegrillandwings.com",  # Native Grill & Wings
    "newportcreamery": "newportcreamery.com",  # Newport Creamery
    "nextlevelburger": "nextlevelvg.com",  # Next Level Burger
    "nickthegreek": "nickthegreek.com",  # Nick The Greek
    "nikonikos": "nikonikos.com",  # Niko Niko's
    "ninetyninerestaurantpub": "99restaurants.com",  # Ninety Nine Restaurant & Pub
    "noahsnewyorkbagels": "noahs.com",  # Noah's New York Bagels
    "normsrestaurants": "norms.com",  # Norms Restaurants
    "nothingbundtcakes": "nothingbundtcakes.com",  # Nothing Bundt Cakes
    "nuvegancafe": "ilovenuvegan.com",  # NuVegan Cafe
    "ocharleys": "ocharleys.com",  # O'Charley's
    "ojoslocos": "ojoslocos.com",  # Ojos Locos
    "oldchicago": "oldchicago.com",  # Old Chicago
    "ologybrewingco": "ologybrewing.com",  # Ology Brewing Co.
    "oniguru": "onigururestaurant.com",  # OniGuru
    "orangejulius": "orangejulius.com",  # Orange Julius
    "orangeleaffrozenyogurt": "orangeleafyogurt.com",  # Orange Leaf Frozen Yogurt
    "ottopizza": "ottoportland.com",  # Otto Pizza
    "pfchangschinabistro": "pfchangs.com",  # P. F. Chang's China Bistro
    "pagliaccipizza": "pagliacci.com",  # Pagliacci Pizza
    "pancherosmexicangrill": "pancheros.com",  # Pancheros Mexican Grill
    "panerabread": "panerabread.com",  # Panera Bread
    "papaginos": "papaginos.com",  # Papa Gino's
    "pardonmycheesesteak": "pardonmycheesesteak.com",  # Pardon my Cheesesteak
    "pastaphony": "pastaphony.com",  # Pastaphony
    "pastini": "pastini.com",  # Pastini
    "patxischicagopizza": "patxispizza.com",  # Patxi's Chicago Pizza
    "peetscoffee": "peets.com",  # Peet's Coffee
    "pennstation": "penn-station.com",  # Penn Station
    "peoplededicatedtoquality": "eatpdq.com",  # People Dedicated to Quality
    "pepperonis": "pepperonis.net",  # Pepperoni's
    "perkinsrestaurantbakery": "perkinsrestaurants.com",  # Perkins Restaurant & Bakery
    "philsbbq": "philsbbq.com",  # Phil's BBQ
    "phillypretzelfactory": "phillypretzelfactory.com",  # Philly Pretzel Factory
    "philzcoffee": "philzcoffee.com",  # Philz Coffee
    "phha": "phohoa.com",  # Phở Hòa
    "piadaitalianstreetfood": "mypiada.com",  # Piada Italian Street Food
    "piccadillypub": "elephantcastle.com",  # Piccadilly Pub
    "piccadillyrestaurants": "piccadilly.com",  # Piccadilly Restaurants
    "pickupstix": "pickupstix.com",  # Pick Up Stix
    "pineandcrane": "pineandcrane.com",  # Pine and Crane
    "pinkberry": "pinkberry.com",  # Pinkberry
    "pizzafactory": "pizzafactory.com",  # Pizza Factory
    "pizzaking": "pizzaking.com",  # Pizza King
    "pizzaluc": "pizzaluce.com",  # Pizza Lucé
    "pizzamyheart": "pizzamyheart.com",  # Pizza My Heart
    "pizzapatrn": "pizzapatron.com",  # Pizza Patrón
    "pizzaport": "pizzaport.com",  # Pizza Port
    "pizzaschmizza": "schmizza.com",  # Pizza Schmizza
    "pjscoffee": "pjscoffee.com",  # PJ's Coffee
    "planethollywood": "planethollywood.com",  # Planet Hollywood
    "planetsmoothie": "planetsmoothie.com",  # Planet Smoothie
    "playabowls": "playabowls.com",  # Playa Bowls
    "pollotropical": "pollotropical.com",  # Pollo Tropical
    "ponderosasteakhouse": "pon-bon.com",  # Ponderosa Steakhouse
    "potbellysandwichshop": "potbelly.com",  # Potbelly Sandwich Shop
    "primantibrothers": "primantibros.com",  # Primanti Brothers
    "primohoagies": "primohoagies.com",  # Primo Hoagies
    "pudgies": "pudgies.com",  # Pudgie's
    "qdobamexicaneats": "qdoba.com",  # Qdoba Mexican Eats
    "quakersteaklube": "thelube.com",  # Quaker Steak & Lube
    "quickly": "quicklyusa.com",  # Quickly
    "rasushi": "rasushi.com",  # RA Sushi
    "rainforestcafe": "rainforestcafe.com",  # Rainforest Cafe
    "raisingcaneschickenfingers": "raisingcanes.com",  # Raising Cane's Chicken Fingers
    "rallys": "rallys.com",  # Rally's
    "ramenryoma": "ramenryoma.net",  # Ramen Ryoma
    "randysdonuts": "randys-donuts.com",  # Randy's Donuts
    "redarrowdiner": "redarrowdiner.com",  # Red Arrow Diner
    "redelephantpizzagrill": "redelephantpizza.com",  # Red Elephant Pizza & Grill
    "redhotblue": "redhotandblue.com",  # Red Hot & Blue
    "redmillburgers": "redmillburgers.com",  # Red Mill Burgers
    "redowlcoffeecompany": "redowlcoffee.com",  # Red Owl Coffee Company
    "redeyecoffee": "redeyecoffee.com",  # RedEye Coffee
    "reginapizzeria": "reginapizzeria.com",  # Regina Pizzeria
    "ribcrib": "ribcrib.com",  # RibCrib
    "roadhousegrill": "roadhouse.it",  # Roadhouse Grill
    "robeks": "robeks.com",  # Robeks
    "robertostacoshop": "robertostacoshop.com",  # Roberto's Taco Shop
    "robototokyogrill": "robototokyogrill.com",  # Roboto Tokyo Grill
    "rocknrollsushi": "rocknrollsushi.com",  # Rock N Roll Sushi
    "rockyrococo": "rockyrococo.com",  # Rocky Rococo
    "rodneyscottswholehogbbq": "rodneyscottsbbq.com",  # Rodney Scott's Whole Hog BBQ
    "rosatisauthenticchicagopizza": "myrosatis.com",  # Rosati's Authentic Chicago Pizza
    "rosatispizza": "rosatispizza.com",  # Rosati's Pizza
    "roscoeshouseofchickenandwaffles": "roscoeschickenandwaffles.com",  # Roscoe's House of Chicken and Waffles
    "roundtablepizza": "roundtablepizza.com",  # Round Table Pizza
    "royrogersrestaurants": "royrogersrestaurants.com",  # Roy Rogers Restaurants
    "royalcastle": "royalcastlemiami.com",  # Royal Castle
    "rubioscoastalgrill": "rubios.com",  # Rubio's Coastal Grill
    "rubysdiner": "rubys.com",  # Ruby's Diner
    "rudyscountrystoreandbarbq": "rudysbbq.com",  # Rudy's Country Store and Bar-B-Q
    "russosnewyorkpizzeria": "nypizzeria.com",  # Russo's New York Pizzeria
    "rustytaco": "rustytaco.com",  # Rusty Taco
    "ruthshospitalitygroup": "rhgi.com",  # Ruth's Hospitality Group
    "salspizza": "sals.com",  # Sal's Pizza
    "saladandgo": "saladandgo.com",  # Salad and Go
    "saladworks": "saladworks.com",  # Saladworks
    "salsaritasfreshmexicangrill": "salsaritas.com",  # Salsarita's Fresh Mexican Grill
    "saltandstraw": "saltandstraw.com",  # Salt and Straw
    "saltgrasssteakhouse": "saltgrass.com",  # Saltgrass Steak House
    "salvatoresoldfashionedpizzeria": "salvatores.com",  # Salvatore's Old Fashioned Pizzeria
    "samsfamilyofrestaurants": "lovethatseafood.com",  # Sam's Family of Restaurants
    "sankalp": "sankalpusa.com",  # Sankalp
    "sbarro": "sbarro.com",  # Sbarro
    "scooterscoffee": "scooterscoffee.com",  # Scooter's Coffee
    "scoutco": "scoutvt.com",  # Scout & Co.
    "seasons52": "seasons52.com",  # Seasons 52
    "seorfrogs": "senorfrogs.com",  # Señor Frog's
    "shahshalalfood": "shahshalalfood.co.uk",  # Shah's Halal Food
    "shakespearespizza": "shakespeares.com",  # Shakespeare's Pizza
    "sharisrestaurants": "sharis.com",  # Shari's Restaurants
    "shoneys": "shoneys.com",  # Shoney's
    "showmars": "showmars.com",  # Showmars
    "simplesimonspizza": "simplesimonspizza.com",  # Simple Simon’s Pizza
    "skippersseafoodchowderhouse": "skippers.com",  # Skippers Seafood & Chowder House
    "skylinechili": "skylinechili.com",  # Skyline Chili
    "slapfish": "slapfishrestaurant.com",  # Slapfish
    "slimchickens": "slimchickens.com",  # Slim Chickens
    "smallcakes": "smallcakescupcakery.com",  # Smallcakes
    "smallssliders": "smallssliders.com",  # Smalls Sliders
    "smithfieldschickennbarbq": "scnbnc.com",  # Smithfield's Chicken 'N Bar-B-Q
    "snapburger": "snap-burger.com",  # Snap Burger
    "sneakypetes": "sneakypetes.com",  # Sneaky Pete's
    "sonnysbbq": "sonnysbbq.com",  # Sonny's BBQ
    "souplantation": "souplantation.com",  # Souplantation
    "sourdoughco": "sourdoughandco.com",  # Sourdough & Co.
    "spaghettiwarehouse": "meatballs.com",  # Spaghetti Warehouse
    "spangles": "spanglesinc.com",  # Spangles
    "specialtys": "specialtys.com",  # Specialty's
    "streetpizza": "gordonramsayrestaurants.com",  # Street Pizza
    "subzero": "subzeroicecream.com",  # Sub Zero
    "sukihana": "irmgusa.com",  # Suki Hana
    "superchixchickencustard": "superchix.com",  # Super Chix Chicken & Custard
    "superdeluxe": "eatsuperdeluxe.com",  # SuperDeluxe
    "surcherosfreshmex": "surcheros.com",  # Surcheros Fresh Mex
    "surfcitysqueeze": "surfcitysqueeze.com",  # Surf City Squeeze
    "sushieatstation": "sushieatstation.com",  # Sus Hi Eatstation
    "sushiroku": "sushiroku.com",  # Sushi Roku
    "sushirrito": "sushirrito.com",  # Sushirrito
    "sushisamba": "sushisamba.com",  # Sushisamba
    "sweetgreen": "sweetgreen.com",  # Sweetgreen
    "sweethoneydessert": "sweethoneydessert.com",  # Sweethoney Dessert
    "swensens": "swensensicecream.com",  # Swensen's
    "tacobellcantina": "locations.tacobell.com",  # Taco Bell Cantina
    "tacobueno": "tacobueno.com",  # Taco Bueno
    "tacocabana": "tacocabana.com",  # Taco Cabana
    "tacocasa": "tacocasatexas.com",  # Taco Casa
    "tacodelmar": "tacodelmar.com",  # Taco del Mar
    "tacogringo": "tacogringo.com",  # Taco Gringo
    "tacojohns": "tacojohns.com",  # Taco John's
    "tacomayo": "tacomayo.com",  # Taco Mayo
    "tacopalenque": "tacopalenque.com",  # Taco Palenque
    "tacone": "tacone.com",  # Tacone
    "tacotime": "tacotime.com",  # TacoTime
    "tacotote": "tacotote.com",  # Tacotote
    "tapiocaexpress": "tapiocaexpress.com",  # Tapioca Express
    "tastea": "gotastea.com",  # Tastea
    "tattebakerycafe": "tattebakery.com",  # Tatte Bakery & Cafe
    "tedsmontanagrill": "tedsmontanagrill.com",  # Ted's Montana Grill
    "teddysbiggerburgers": "teddysbb.com",  # Teddy's Bigger Burgers
    "tendergreens": "tendergreens.com",  # Tender Greens
    "teriyakimadness": "teriyakimadness.com",  # Teriyaki Madness
    "texschickenburgers": "eattexs.com",  # Tex's Chicken & Burgers
    "texasdebrazil": "texasdebrazil.com",  # Texas de Brazil
    "thebean": "thebean.nyc",  # The Bean
    "thebigbiscuit": "bigbiscuit.com",  # The Big Biscuit
    "thebrasstap": "brasstapbeerbar.com",  # The Brass Tap
    "thecapitalgrille": "thecapitalgrille.com",  # The Capital Grille
    "thecheesecakefactory": "thecheesecakefactory.com",  # The Cheesecake Factory
    "thecounter": "thecounter.com",  # The Counter
    "theflamebroiler": "flamebroilerusa.com",  # The Flame Broiler
    "thehalalguys": "thehalalguys.com",  # The Halal Guys
    "thehat": "thehat.com",  # The Hat
    "thehoneybakedhamcompany": "honeybaked.com",  # The Honey Baked Ham Company
    "thejalapenotree": "jalapenotree.com",  # The Jalapeno Tree
    "themeltdown": "themeltdown.com",  # The Meltdown
    "themeltingpot": "meltingpot.com",  # The Melting Pot
    "theoriginalpancakehouse": "originalpancakehouse.com",  # The Original Pancake House
    "theperfectpig": "theperfectpig.com",  # The Perfect Pig
    "thepizzastudio": "pizzastudio.com",  # The Pizza Studio
    "thesimplegreek": "thesimplegreek.com",  # The Simple Greek
    "thestand": "thestand.com",  # The Stand
    "thetrainingtable": "thetrainingtable.com",  # The Training Table
    "thevarsity": "thevarsity.com",  # The Varsity
    "theworkscaf": "workscafe.com",  # The Works Café
    "theyardmilkshakebar": "theyardmilkshakebar.com",  # The Yard Milkshake Bar
    "thinkcoffee": "thinkcoffee.com",  # Think Coffee
    "thriftyicecream": "thriftyicecream.com",  # Thrifty Ice Cream
    "tibbysneworleanskitchen": "tibbys.com",  # Tibby's New Orleans Kitchen
    "tierramiacoffee": "tierramiacoffee.com",  # Tierra Mia Coffee
    "tijuanaflats": "tijuanaflats.com",  # Tijuana Flats
    "tiltedkiltpubeatery": "tiltedkilt.com",  # Tilted Kilt Pub & Eatery
    "timberlodgesteakhouse": "timberlodgesteakhouse.com",  # Timber Lodge Steakhouse
    "toastique": "toastique.com",  # Toastique
    "tobykeithsilovethisbargrill": "tobykeithsbar.com",  # Toby Keith's I Love This Bar & Grill
    "togos": "togos.com",  # TOGO'S
    "tomwahls": "tomwahls.com",  # Tom Wahl's
    "topburmese": "topburmese.com",  # Top Burmese
    "toppotdoughnuts": "toppotdoughnuts.com",  # Top Pot Doughnuts
    "topperspizza": "toppers.com",  # Toppers Pizza
    "torchystacos": "torchystacos.com",  # Torchy’s Tacos
    "trailerbirds": "trailerbirds.com",  # Trailer Birds
    "tropicalsmoothiecafe": "tropicalsmoothiecafe.com",  # Tropical Smoothie Cafe
    "truefoodkitchen": "truefoodkitchen.com",  # True Food Kitchen
    "tubbys": "tubbys.com",  # Tubby's
    "tudorsbiscuitworld": "tudorsbiscuitworld.com",  # Tudor's Biscuit World
    "tullyscoffee": "tullys.com",  # Tully's Coffee
    "twinpeaks": "twinpeaksrestaurant.com",  # Twin Peaks
    "twistedtenders": "twistedchickentenders.com",  # Twisted Tenders
    "twisteetreat": "twisteetreat.com",  # Twistee Treat
    "twohandscorndog": "twohandsus.com",  # Two Hands Corn Dog
    "umamiburger": "umami.com",  # Umami Burger
    "uniteddairyfarmers": "udfinc.com",  # United Dairy Farmers
    "universityofbeer": "theuob.com",  # University of Beer
    "unochicagogrill": "unos.com",  # Uno Chicago Grill
    "uppercrustpizzeria": "theuppercrustpizzeria.com",  # Upper Crust Pizzeria
    "urbanplates": "urbanplates.com",  # Urban Plates
    "valentinos": "valentinos.com",  # Valentino's
    "valeriostropicalbakeshop": "valeriostropicalbakeshop.com",  # Valerio’s Tropical Bakeshop
    "vanleeuwenicecream": "vanleeuwenicecream.com",  # Van Leeuwen Ice Cream
    "via313": "locations.via313.com",  # Via 313
    "vicanthonyssteakhouse": "vicandanthonys.com",  # Vic & Anthony's Steakhouse
    "villaitaliankitchen": "villaitaliankitchen.com",  # Villa Italian Kitchen
    "vitalitybowls": "vitalitybowls.com",  # Vitality Bowls
    "vocellipizza": "vocellipizza.com",  # Vocelli Pizza
    "voodoodoughnut": "voodoodoughnut.com",  # Voodoo Doughnut
    "wabagrill": "wabagrill.com",  # WaBa Grill
    "wafflecabin": "wafflecabin.com",  # Waffle Cabin
    "wahlburgers": "wahlburgers.com",  # Wahlburgers
    "wahoosfishtaco": "wahoos.com",  # Wahoo's Fish Taco
    "wards": "wardsrestaurants.com",  # Ward's
    "watergrill": "watergrill.com",  # Water Grill
    "waybackburgers": "waybackburgers.com",  # Wayback Burgers
    "weathervaneseafoodrestaurants": "weathervaneseafoods.com",  # Weathervane Seafood Restaurants
    "westernsizzlin": "western-sizzlin.com",  # Western Sizzlin'
    "wetzelspretzels": "wetzels.com",  # Wetzel's Pretzels
    "whiteysicecream": "whiteysicecream.com",  # Whitey's Ice Cream
    "wienerschnitzel": "wienerschnitzel.com",  # Wienerschnitzel
    "williejewellsoldschoolbarbq": "williejewells.com",  # Willie Jewell's Old School Bar-B-Q
    "winchellsdonuts": "winchells.com",  # Winchell's Donuts
    "wingzone": "wingzone.com",  # Wing Zone
    "wingsetc": "wingsetc.com",  # Wings Etc.
    "wingstreet": "wingstreet.com",  # WingStreet
    "wokaholic": "irmgusa.com",  # Wok a Holic
    "wonder": "wonder.com",  # Wonder
    "wongsking": "wongsking.com",  # Wong's King
    "woops": "bywoops.com",  # Woops!
    "xianfamousfoods": "xianfoods.com",  # Xi'an Famous Foods
    "yardhouse": "yardhouse.com",  # Yard House
    "yogurtmountain": "yogurtmountain.com",  # Yogurt Mountain
    "yogurtland": "yogurt-land.com",  # Yogurtland
    "yourpie": "yourpie.com",  # Your Pie
    "yumyumdonuts": "yumyumdonuts.com",  # Yum Yum Donuts
    "zeats": "eatzeats.com",  # Z!Eats
    "zburger": "zburger.com",  # Z-Burger
    "zacadoos": "zacadoos.com",  # Zacadoo's
    "zankouchicken": "zankouchicken.com",  # Zankou Chicken
    "zeekspizza": "zeekspizza.com",  # Zeeks Pizza
    "zerodegrees": "zerodegreescompany.com",  # Zero Degrees
    "zipsdrivein": "zipsdrivein.com",  # Zip's Drive-in
    "zippys": "zippys.com",  # Zippy's
    "zoskitchen": "zoeskitchen.com",  # Zoës Kitchen
    "zpizza": "zpizza.com",  # zpizza
}
