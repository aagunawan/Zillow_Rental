from urllib.request import Request, urlopen
from lxml import html
import requests
import unicodecsv as csv
import argparse
import json
import pymongo
from pymongo import MongoClient
from datetime import datetime

cluster = MongoClient("mongodb+srv://aagunawan:dedeku88@cluster0.qfiad.mongodb.net/<dbname>?retryWrites=true&w=majority")
db = cluster["rental"]
todays_date = datetime.today().strftime('%Y-%m-%d')

def clean(text):
    if text:
        return ' '.join(' '.join(text).split())
    return None


def get_headers():
    # Creating headers.
    headers = {'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
               'accept-encoding': 'gzip, deflate, sdch, br',
               'accept-language': 'en-GB,en;q=0.8,en-US;q=0.6,ml;q=0.4',
               'cache-control': 'max-age=0',
               'upgrade-insecure-requests': '1',
               'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/74.0.3729.131 Safari/537.36'}
    return headers


def create_url(zipcode, filter):
    # Creating Zillow URL based on the filter.
    url = "https://www.zillow.com/homes/for_rent/{0}_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode)

    print(url)
    return url

def update_days(collection, entry):
    query = {"zid": entry.get("zid")}
    updated_value = {"$set": {"daysOnZillow": entry.get("daysOnZillow"), "lastUpdated": todays_date}}

    if (collection.find_one(query)): # if found update daysOnZillow and lastUpdated
        collection.update_one(query, updated_value)
    else: # if not found, insert it 
        collection.insert_one(entry)
    
    # look at all houses in current zipcode that do not get updated to latest date and change it to off market
    query_off_market = {"lastUpdated": {"$ne": todays_date}}
    updated_value_off_market = {"$set": {"onMarket": False}}
    collection.update_many(query_off_market, updated_value_off_market)

    return None

def update_db(data, zipcode):
    collection = db[zipcode] 

    if collection.count_documents({}) == 0: 
        collection.drop()
        collection.insert_many(data)
    
    else:
        for entry in data:
            update_days(collection, entry)
    
    return None

def get_response(url):
    
    # Getting response from zillow.com.
    for i in range(5):
        response = requests.get(url, headers=get_headers())
        print("status code received:", response.status_code)
        if response.status_code != 200:
            continue
        else:
            return response
    return None

def get_data_from_json(raw_json_data):
    # getting data from json (type 2 of their A/B testing page)

    cleaned_data = clean(raw_json_data).replace('<!--', "").replace("-->", "")
    properties_list = []

    try:
        json_data = json.loads(cleaned_data)
        search_results = json_data.get('cat1').get('searchResults').get('listResults', [])
        for properties in search_results:
            address = properties.get('addressStreet')
            zid = properties.get('zpid')
            property_info = properties.get('hdpData', {}).get('homeInfo')
            if (property_info):
                city = property_info.get('city')
                state = property_info.get('state')
                postal_code = property_info.get('zipcode')
                price = properties.get('price')
                bedrooms = properties.get('beds')
                bathrooms = properties.get('baths')
                area = properties.get('area')
                info = f'{bedrooms} bds, {bathrooms} ba ,{area} sqft'
                daysOnZillow = property_info.get('daysOnZillow')
                lastUpdated = todays_date
                property_url = properties.get('detailUrl')
                title = properties.get('statusText')

                data = {'zid': zid,
                        'address': address,
                        'city': city,
                        'state': state,
                        'postal_code': postal_code,
                        'price': price,
                        'bed': bedrooms,
                        'bath': bathrooms,
                        'area': area,
                        'daysOnZillow': daysOnZillow,
                        'lastUpdated': lastUpdated,
                        'onMarket': True,
                        'url': property_url,
                        'title': title}
                properties_list.append(data)
        del json_data # test this to not allow old values 
        return properties_list

    except ValueError:
        print("Invalid json")
        return None

def parse(zipcode, filter=None):
    url = create_url(zipcode, filter)
    response = get_response(url)
   
    if not response:
        print("Failed to fetch the page, please check `response.html` to see the response received from zillow.com.")
        return None

    # These two new lines are added
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    webpage = urlopen(req).read()

    #replace the parser to take input added above
    parser = html.fromstring(webpage)
    search_results = parser.xpath("//div[@id='search-results']//article")
    
    if not search_results:
        print("parsing from json data")
        # identified as type 2 page
        raw_json_data = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
        return get_data_from_json(raw_json_data)

if __name__ == "__main__":
    # Reading arguments

    argparser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    argparser.add_argument('zipcode', help='')
    sortorder_help = """
    available sort orders are :
    newest : Latest property details,
    cheapest : Properties with cheapest price
    """

    argparser.add_argument('sort', nargs='?', help=sortorder_help, default='Homes For You')
    args = argparser.parse_args()
    zipcode = args.zipcode
    sort = args.sort
    print ("Fetching data for %s" % (zipcode))
    scraped_data = parse(zipcode, sort)
    if scraped_data:
        print ("Writing data to database")
        update_db(scraped_data, zipcode)