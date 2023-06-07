# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html
import json

# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class AptekaOtSkladaPipeline:

    items = []
    def process_item(self, item, spider):
        self.items.append(item)
        return item

    def close_spider(self, spider):
        with open('apteka_ot_sklada_data.json', 'a') as aot:
            json.dump(self.items, aot)
