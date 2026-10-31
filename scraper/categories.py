"""Распределение товаров по группам по ключевым словам в немецком названии.

Группы проверяются сверху вниз, товар попадает в первую подходящую.
Порядок важен: например, «Orangensaft» должен попасть в напитки раньше,
чем слово «Orange» отправит его во фрукты.

Чтобы поправить группу, добавьте слово в нужный список. Короткие слова
пишите с \\b по краям, чтобы «Eis» не находилось внутри «Reis».
"""
import re

CATEGORIES = [
    ("pets", "Для животных", "🐾", [
        r"hund", r"katze", r"tiernahrung", r"whiskas", r"felix", r"pedigree",
        r"sheba", r"katzenstreu", r"kauknochen", r"\bvogel",
    ]),
    ("household", "Бытовое и гигиена", "🧴", [
        r"waschmittel", r"spülmittel", r"spülmaschinen", r"weichspüler",
        r"toilettenpapier", r"küchenrolle", r"taschentücher", r"shampoo",
        r"duschgel", r"dusche\b", r"zahnpasta", r"zahncreme", r"zahnbürste",
        r"\bdeo", r"windeln", r"persil", r"ariel", r"lenor", r"\btempo\b",
        r"zewa", r"nivea", r"rasier", r"reiniger", r"müllbeutel", r"seife",
        r"bodylotion", r"handcreme", r"gesichtscreme", r"somat", r"finish", r"frosch",
        r"batterie", r"glühbirne", r"\bkerze", r"duftperlen", r"tandil",
    ]),
    ("nonfood", "Дом, сад и одежда", "🏠", [
        r"gardenline", r"pflanze", r"blume", r"amaryllis", r"sukkulent", r"orchidee",
        r"home creation", r"ambiano", r"easy home", r"workzone", r"crane", r"quigg",
        r"up2fashion", r"novitesse", r"topcraft", r"medion", r"bettwäsche", r"parka",
        r"troyer", r"jacke", r"pullover", r"socken", r"strumpf", r"\bhose", r"shirt",
        r"schuhe", r"stiefel", r"mütze", r"schal\b", r"handschuh", r"\bled\b", r"\bled-",
        r"lampe", r"leuchte", r"\bdecke\b", r"kissen", r"handtuch", r"werkzeug",
        r"kindermode", r"spielzeug", r"deko", r"pfanne\b", r"\btopf\b", r"couch",
        r"\bbbq\b", r"anzünder", r"brikett", r"anfeuerholz", r"kaminholz", r"samsung",
        r"smartphone", r"maginon", r"jeans", r"teppich", r"regal\b",
    ]),
    ("alcohol", "Алкоголь", "🍷", [
        r"\bbier", r"\bpils", r"radler", r"weizen", r"\bwein\b", r"rotwein",
        r"weißwein", r"rosé", r"sekt", r"prosecco", r"champagner", r"wodka",
        r"vodka", r"whisk(e)?y", r"\brum\b", r"\bgin\b", r"likör", r"jägermeister",
        r"spirituose", r"riesling", r"merlot", r"primitivo", r"becks",
        r"krombacher", r"warsteiner", r"bitburger", r"berliner kindl",
        r"berliner pilsner", r"aperol", r"\bcider", r"glühwein", r"rotkäppchen",
        r"gutedel", r"\bqba\b", r"lambrusco", r"chardonnay",
    ]),
    ("coffee_tea", "Кофе и чай", "☕", [
        r"kaffee", r"espresso", r"cappuccino", r"kapseln", r"tchibo",
        r"jacobs", r"dallmayr", r"melitta", r"lavazza", r"nescaf",
        r"\btee\b", r"teekanne", r"meßmer", r"messmer", r"kakao", r"matcha",
    ]),
    ("drinks", "Напитки и сладкая вода", "🥤", [
        r"cola", r"fanta", r"sprite", r"\blimo", r"limonade", r"eistee",
        r"saft", r"nektar", r"schorle", r"mineralwasser", r"tafelwasser",
        r"\bwasser\b", r"sprudel", r"energy", r"red bull", r"monster",
        r"pepsi", r"mezzo", r"capri", r"smoothie", r"volvic", r"gerolsteiner",
        r"\bvio\b", r"fritz", r"club-?mate", r"\bmate\b", r"getränk",
        r"\bdrink", r"bionade", r"sinalco", r"7up", r"schweppes", r"lipton",
    ]),
    ("sweets", "Вкусности", "🍫", [
        r"schoko", r"riegel", r"chips", r"keks", r"gummi", r"haribo",
        r"bonbon", r"praline", r"milka", r"ritter sport", r"\bkinder\b",
        r"lindt", r"snickers", r"twix", r"\bmars\b", r"kit ?kat", r"nutella",
        r"waffel", r"popcorn", r"erdnüsse", r"nüsse", r"salzstangen",
        r"cracker", r"pringles", r"lay.?s\b", r"funny-?frisch", r"\bchio\b",
        r"crunchips", r"\beis\b", r"eiscreme", r"magnum", r"langnese",
        r"ben ?& ?jerry", r"toffifee", r"merci", r"lakritz", r"muffin",
        r"donut", r"süßigkeit", r"leibniz", r"oreo", r"m&m", r"lebkuchen",
        r"spekulatius", r"stollen", r"marzipan", r"duplo", r"mentos", r"wonka",
        r"mozartkugel", r"gebäck", r"weihnachtsmann", r"nuss", r"crêpe", r"crepe",
        r"snack", r"cocktail-mix", r"nicnac", r"pick up", r"manner", r"törtchen",
    ]),
    ("frozen", "Заморозка", "❄️", [
        r"tiefkühl", r"\btk\b", r"tiefgefroren", r"pizza", r"pommes", r"la mia grande",
        r"fischstäbchen", r"\biglo\b", r"frosta", r"wagner", r"ristorante",
    ]),
    ("meat_fish", "Мясо и рыба", "🥩", [
        r"fleisch", r"hähnchen", r"hühn", r"huhn", r"\bpute", r"\brind",
        r"schwein", r"\bhack", r"wurst", r"würstchen", r"salami", r"schinken",
        r"steak", r"schnitzel", r"filet", r"lachs", r"fisch", r"garnele",
        r"thunfisch", r"hering", r"forelle", r"kassler", r"gyros", r"bacon",
        r"\bspeck", r"frikadelle", r"chicken", r"ente\b", r"gans\b", r"pangasius",
        r"jam[oó]n", r"serrano", r"prosciutto", r"wiltmann", r"aufschnitt", r"braten",
        r"lamm", r"geflügel", r"wiener\b",
    ]),
    ("dairy", "Молочное и яйца", "🧀", [
        r"milch", r"joghurt", r"jogurt", r"quark", r"käse", r"butter",
        r"sahne", r"skyr", r"kefir", r"\beier\b", r"mozzarella", r"gouda",
        r"camembert", r"feta", r"margarine", r"pudding", r"schmand",
        r"\bbrie\b", r"emmentaler", r"parmesan", r"ayran", r"actimel", r"streichzart", r"babybel",
        r"g[ée]ramont", r"zottarella", r"activia", r"ehrmann", r"dessert",
    ]),
    ("bakery", "Хлеб и выпечка", "🥐", [
        r"\bbrot", r"brötchen", r"toast", r"baguette", r"croissant",
        r"kuchen", r"brezel", r"laugen", r"semmel", r"ciabatta", r"wraps?\b",
        r"tortilla",
    ]),
    ("pantry", "Бакалея", "🍝", [
        r"nudeln", r"pasta", r"spaghetti", r"penne", r"fusilli", r"\breis\b",
        r"\bmehl", r"zucker", r"öl\b", r"essig", r"ketchup", r"mayo",
        r"\bsenf", r"soße", r"sauce", r"gewürz", r"konserve", r"\bdose",
        r"suppe", r"müsli", r"cornflakes", r"haferflocken", r"honig",
        r"marmelade", r"konfitüre", r"aufstrich", r"bohnen", r"linsen",
        r"\bmais\b", r"barilla", r"maggi", r"knorr", r"brühe", r"pesto", r"sushi",
        r"onigiri", r"bowl", r"gyoza", r"edamame", r"udon", r"kimchi", r"tteokbokki",
        r"reispapier", r"nori", r"krupuk", r"asia",
    ]),
    ("fruit_veg", "Овощи и фрукты", "🥦", [
        r"\bobst", r"gemüse", r"apfel", r"äpfel", r"banane", r"birne",
        r"trauben", r"orange", r"mandarine", r"clementine", r"zitrone",
        r"\bkiwi", r"mango", r"ananas", r"melone", r"beere", r"tomate",
        r"gurke", r"paprika", r"kartoffel", r"zwiebel", r"möhre", r"karotte",
        r"salat", r"brokkoli", r"blumenkohl", r"zucchini", r"champignon",
        r"pilze", r"avocado", r"kohl", r"spinat", r"lauch", r"knoblauch",
        r"kürbis", r"radieschen", r"spargel", r"aubergine", r"granatapfel",
        r"pflaume", r"nektarine", r"pfirsich", r"kirsche", r"lime", r"grapefruit",
        r"pomelo", r"pak-?choi", r"ingwer", r"rüben", r"sellerie", r"fenchel",
        r"koriander", r"petersilie", r"basilikum", r"schnittlauch", r"kräuter",
    ]),
]

OTHER = ("other", "Прочее", "📦")

_COMPILED = [
    (cid, re.compile("|".join(patterns), re.IGNORECASE))
    for cid, _label, _emoji, patterns in CATEGORIES
]


def categorize(text: str) -> str:
    for cid, rx in _COMPILED:
        if rx.search(text):
            return cid
    return OTHER[0]


def categories_for_site():
    """Список групп для сайта, в том порядке, в котором их удобно показывать."""
    order = ["drinks", "sweets", "fruit_veg", "meat_fish", "dairy", "bakery",
             "pantry", "frozen", "coffee_tea", "alcohol", "household", "nonfood", "pets"]
    by_id = {cid: (label, emoji) for cid, label, emoji, _ in CATEGORIES}
    result = [{"id": cid, "label": by_id[cid][0], "emoji": by_id[cid][1]} for cid in order]
    result.append({"id": OTHER[0], "label": OTHER[1], "emoji": OTHER[2]})
    return result
