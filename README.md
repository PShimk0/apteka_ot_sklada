# apteka_ot_sklada
Repo containing scrapy spider to parse https://apteka-ot-sklada.ru/
To run spider use 
scrapy crawl apteka_ot_sklada_crawler
Data is stored in list of dicts in json file
If we want to get different region we need to modify methods **parse_region_data** **and parse**
If we want to get different/more categories, add them to start_urls