import json
from datetime import datetime
import scrapy
import chompjs
class AptekaOtSkladaSpider(scrapy.Spider):
    name = 'apteka_ot_sklada_crawler'
    custom_settings = {
        "LOG_LEVEL": "INFO",
        'ITEM_PIPELINES':
            {
                "apteka_ot_sklada.pipelines.AptekaOtSkladaPipeline": 300
            }
    }

    start_urls = [
        "https://apteka-ot-sklada.ru/catalog/kontaktnye-linzy-i-ochki/linzy-ezhednevnye",
        "https://apteka-ot-sklada.ru/catalog/sredstva-gigieny/uhod-za-polostyu-rta/zubnye-niti_-ershiki",
        "https://apteka-ot-sklada.ru/catalog/perevyazochnye-sredstva/binty/binty-elastichnye-kompressionnye",
        "https://apteka-ot-sklada.ru/catalog/uhod-za-bolnymi_-sredstva-reabilitatsii/kompressionnyy-trikotazh/kompressionnye-mayki_-futbolki_-shorty",
        "https://apteka-ot-sklada.ru/catalog/uhod-za-bolnymi_-sredstva-reabilitatsii/kompressionnyy-trikotazh/golfy"
    ]

    """
    Получаем список id для доступных регионов
    """
    def start_requests(self):
        yield scrapy.Request(
            "https://apteka-ot-sklada.ru/api/region",
            callback=self.parse_region_data
        )

    """
    Находим id Томской области, делаем запрос, чтобы найти id Томска-города
    """
    def parse_region_data(self, response):
        regions_list = chompjs.parse_js_object(response.text)
        for region in regions_list:
            if 'Томск' in region.get("name"):
                id = region.get("id")
                yield scrapy.Request(
                    f"https://apteka-ot-sklada.ru/api/region/{id}",
                    callback=self.parse
                )

    """
    Находим id Томска, делаем запрос, чтобы идентифицировать, что мы заинтересованы только в товарах для Томска
    """
    def parse(self, response):
        subregions_list = chompjs.parse_js_object(response.text)
        for subregion in subregions_list:
            if 'Томск' in subregion.get("name"):
                id = subregion.get("id")
                yield scrapy.Request(
                    "https://apteka-ot-sklada.ru/api/user/city/requestById",
                    callback=self.parse_categories,
                    method='POST',
                    body=json.dumps({'id':id}),
                    headers={
                        'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
                        'Accept': 'application/json, text/plain, */*',
                        'Content-Type': 'application/json;charset=UTF-8',
                        'DNT': '1',
                        'sec-ch-ua-mobile': '?0',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
                        'sec-ch-ua-platform': '"Windows"',
                    }
                )

    """
    Проходимся по выбранным нами категориям
    """
    def parse_categories(self, response, **kwargs):
        for category_url in self.start_urls:
            yield scrapy.Request(
                category_url,
                callback=self.parse_categories_pages
            )

    """
    Собираем/переходим на ссылки по товарам, пагинация
    """
    def parse_categories_pages(self, response):
        product_urls = response.xpath("//div[@class='goods-grid__inner']//a[@itemprop='url']/@href").getall()
        for product_url in product_urls:
            yield response.follow(
                product_url,
                callback=self.parse_product_page
            )
        pagination = response.xpath("//li[@class='ui-pagination__item ui-pagination__item_next']/a/@href").get()
        if pagination:
            yield response.follow(
                pagination,
                callback=self.parse_categories_pages
            )

    """
    Формируем item
    """
    def parse_product_page(self, response):
        title = response.xpath("//h1//text()").get()
        json_data = self.get_json_data(response)
        breadcrumbs = response.xpath("//ul[@class='ui-breadcrumbs__list']//li/a/span/span/text()").getall()[2:]
        price = self.get_price(response)
        availability = self.get_availability(response, json_data)
        assets = self.get_assets(response)
        brand = response.xpath("//div[@itemprop='manufacturer']/span[@itemtype='legalName']/text()").get()
        brand = self.clean_string(brand)
        time = datetime.now()
        yield {
                "timestamp": datetime.timestamp(time),
                "RPC": str(json_data.get("goodsId")),
                "url": response.url,
                "title": title,
                "marketing_tags": self.get_marketing_tags(response),
                "brand": brand if brand else '',
                "section": breadcrumbs,
                "price_data": price,
                "stock": availability,
                "assets": assets,
                "metadata": self.get_metadata(response, json_data),
                "variants": 1,
            }


    def get_availability(self, response, json_data):
        availability_dict = dict()
        availability = response.xpath("//link[@itemprop='availability']/@href").get()
        if availability:
            if 'instock' in availability.lower():
                availability_dict['in_stock'] = True
            else:
                availability_dict['in_stock'] = False
        else:
            availability = json_data.get('inStock')
            if availability == 'h':
                availability_dict['in_stock'] = True
            elif availability == 'b':
                availability_dict['in_stock'] = False
        availability_dict['count'] = 0
        return availability_dict

    def get_price(self, response):
        price_xpath = response.xpath("//div[@class='goods-offer-panel__price']/span")
        if len(price_xpath) == 1:
            price = response.xpath("//div[@class='goods-offer-panel__price']/span//text()").get()
            price = float(self.clean_string(price).replace(" ", ''))
            return {
                    "current": price,
                    "original": price,
                    "sale_tag": ""
                }
        elif len(price_xpath) == 2:
            current_price = response.xpath("//div[@class='goods-offer-panel__price']/span[1]//text()").get()
            original_price = response.xpath("//div[@class='goods-offer-panel__price']/span[2]//text()").get()
            current_price = float(self.clean_string(current_price).replace(" ", ''))
            original_price = float(self.clean_string(original_price).replace(" ", ''))
            discount = (original_price - current_price) / original_price
            return {
                "current": current_price,
                "original": original_price,
                "sale_tag": f"Скидка {discount * 100}%"
            }
        else:
            return {
                "current": 0,
                "original": 0,
                "sale_tag": ""
            }

    def get_json_data(self, response):
        string_json = response.xpath("//script[contains(text(), 'window.__NUXT__')]/text()").get()
        string_json = string_json.split("void 0},", 1)[1]
        json_data = chompjs.parse_js_object(string_json)
        return json_data

    def get_assets(self, response):
        images = response.xpath("//ul[@class='goods-gallery__preview-list']/li//img/@src").getall()
        images = [response.urljoin(x) for x in images]
        images = list(set(images))
        main_image = images[0] if len(images) > 0 else ''
        return {
                "main_image": main_image,
                "set_images": images,
                "view360": [],
                "video": []
                }

    def get_marketing_tags(self, response):
        tags = response.xpath("//ul[@class='goods-tags__list goods-tags__list_direction_horizontal']//li/span/text()").getall()
        tags = [self.clean_string(x) for x in tags]
        return tags

    def get_metadata(self, response, json_data):
        metadata_dict = dict()
        description = response.xpath("//section[@id='description']//text()").getall()
        description = [self.clean_string(x) for x in description if self.clean_string(x) != '']
        description = " ".join(description)
        country_of_origin = response.xpath("//div[@itemprop='manufacturer']/span[@itemtype='location']/text()").get()
        country_of_origin = self.clean_string(country_of_origin)
        art = json_data.get('name').split("арт.", 1)
        art = art[1].strip().split(" ", 1)[0] if len(art) > 1 else None
        metadata_dict['__description'] = description
        if art:
            metadata_dict['АРТИКУЛ'] = art

        if country_of_origin:
            metadata_dict['ПРОИЗВОДИТЕЛЬ'] = country_of_origin

        return metadata_dict

    @staticmethod
    def clean_string(item_string):
        strings_to_clean = ["₽", "\n", "\r", "\t"]
        for c in strings_to_clean:
            item_string = item_string.replace(c, "")
        item_string = item_string.strip()
        return item_string