"""Настройки сборщика акций.

EDEKA показывает акции конкретного магазина. Для каждого EDEKA откройте
edeka.de, выберите нужный магазин в Берлине, перейдите на его страницу
«Angebote» и вставьте адрес этой страницы в поле url.
Пока url пустой, магазин пропускается, а на сайте написано, что ссылки нет.
"""
import os

# Ваш репозиторий на GitHub в виде "логин/название", например "anna/berlin-angebote".
# Сюда сборщик загружает свежий offers.json, после чего GitHub обновляет сайт.
GITHUB_REPO = "ВАШ-ЛОГИН/berlin-angebote"

# Окно браузера во время сбора. REWE и EDEKA чаще пускают обычное окно,
# чем невидимый браузер, поэтому по умолчанию окно показывается.
# Чтобы скрыть его, поставьте True (или задайте переменную HEADLESS=1).
HEADLESS = os.environ.get("HEADLESS") == "1" or False


STORES = [
    {
        "id": "rewe",
        "name": "REWE",
        "url": "https://www.rewe.de/angebote/nationale-angebote/",
        "color": "#CC071E",
    },
    {
        "id": "edeka-riebe",
        "name": "EDEKA Riebe",
        "url": "https://www.edeka.de/maerkte/408937/angebote/",
        "color": "#1B4C9C",
    },
    {
        "id": "aldi",
        "name": "ALDI Nord",
        "url": "https://www.aldi-nord.de/angebote.html",
        "color": "#00428F",
        "parser": "aldi",
    },
]

# Если в магазине найдено меньше товаров, считаем, что сбор не удался,
# и оставляем на сайте прошлые данные этого магазина.
MIN_OFFERS = 5
