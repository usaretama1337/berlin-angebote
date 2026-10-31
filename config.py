"""Магазины, которые отслеживает сборщик.

EDEKA показывает акции конкретного магазина. Для каждого EDEKA откройте
edeka.de, выберите нужный магазин в Берлине, перейдите на его страницу
«Angebote» и вставьте адрес этой страницы в поле url.
Пока url пустой, магазин пропускается, а на сайте написано, что ссылки нет.
"""

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
    },
]

# Если в магазине найдено меньше товаров, считаем, что сбор не удался,
# и оставляем на сайте прошлые данные этого магазина.
MIN_OFFERS = 5
