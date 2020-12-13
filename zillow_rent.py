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


def create_url(zipcode, pageNumber):
    # Creating Zillow URL based on the filter.
    # url = "https://www.zillow.com/homes/for_rent/{0}_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode)
    url = "https://www.zillow.com/homes/for_rent/{0}_rb/{1}_p/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode, pageNumber)

    print(url)
    return url

def update_days(collection, entry):
    query = {"zid": entry.get("zid")}
    updated_value = {"$set": {"daysOnZillow": entry.get("daysOnZillow"), "lastUpdated": todays_date}}

    if (collection.find_one(query)): # if found update daysOnZillow and lastUpdated
        collection.update_one(query, updated_value)
    else: # if not found, insert it 
        collection.insert_one(entry)

    return None

def update_db(data, zipcode):
    collection = db[zipcode] 

    if collection.count_documents({}) == 0: 
        collection.drop()
        collection.insert_many(data)
    
    else:
        for entry in data:
            update_days(collection, entry)
    
    # look at all houses in current zipcode that do not get updated to latest date and change it to off market
    query_off_market = {"lastUpdated": {"$ne": todays_date}}
    updated_value_off_market = {"$set": {"onMarket": False}}
    collection.update_many(query_off_market, updated_value_off_market)

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
        # print(len(search_results))
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
    isRepeat = False # bool to indicate same webpage has been accessed
    firstHouseOnPage = [] # keep track of 1st house zid in page to tell if page is a repeat
    pageNumber = 1 # start from 1 and increment in while (isRepeat == false) until 1st house is a repeat
    data = [] # store house output here and extend list from each page

    while (isRepeat == False):
        url = create_url(zipcode, pageNumber)
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
            raw_json_data = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
            recent_data = get_data_from_json(raw_json_data)

            if (recent_data[0].get("zid") in firstHouseOnPage): # if first house is the same stop the data: this means page has repeated 
                isRepeat = True
            else:  # extend data otherwise 
                firstHouseOnPage.append(recent_data[0].get("zid")) 
                data.extend(recent_data)
    
        pageNumber += 1

    return data

if __name__ == "__main__":

    zips = ["90210" , "97229", "97124"]

    for zipcode in zips:
        print ("Fetching data for %s" % (zipcode))
        scraped_data = parse(zipcode)
        # scraped_data = [{'zid': '20519272', 'address': '627 N Alta Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,000/mo', 'bed': 2, 'bath': 1.0, 'area': 890, 'daysOnZillow': 0, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/627-N-Alta-Dr-Beverly-Hills-CA-90210/20519272_zpid/', 'title': 'Apartment for rent'}, {'zid': '20533168', 'address': '13431 Java Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$10,000/mo', 'bed': 7, 'bath': 6.0, 'area': 5000, 'daysOnZillow': 0, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/13431-Java-Dr-Beverly-Hills-CA-90210/20533168_zpid/', 'title': 'House for rent'}, {'zid': '20521509', 'address': '720 N Bedford Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$38,000/mo', 'bed': 4, 'bath': 6.0, 'area': 7372, 'daysOnZillow': 0, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/720-N-Bedford-Dr-Beverly-Hills-CA-90210/20521509_zpid/', 'title': 'House for rent'}, {'zid': '20523602', 'address': '1643 San Ysidro Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$10,800/mo', 'bed': 5, 'bath': 3.0, 'area': 2453, 'daysOnZillow': 1, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/1643-San-Ysidro-Dr-Beverly-Hills-CA-90210/20523602_zpid/', 'title': 'House for rent'}, {'zid': '115827637', 'address': '13749 Mulholland Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$45,000/mo', 'bed': 5, 'bath': 5.0, 'area': 4000, 'daysOnZillow': 1, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/13749-Mulholland-Dr-Beverly-Hills-CA-90210/115827637_zpid/', 'title': 'House for rent'}, {'zid': '20521524', 'address': '711 N Bedford Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$13,800/mo', 'bed': 4, 'bath': 4.0, 'area': 4738, 'daysOnZillow': 1, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/711-N-Bedford-Dr-Beverly-Hills-CA-90210/20521524_zpid/', 'title': 'House for rent'}, {'zid': '20534576', 'address': '1101 Loma Vista Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$14,000/mo', 'bed': 4, 'bath': 4.0, 'area': 4000, 'daysOnZillow': 1, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/1101-Loma-Vista-Dr-Beverly-Hills-CA-90210/20534576_zpid/', 'title': 'House for rent'}, {'zid': '20515231', 'address': '410 N Oakhurst Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,800/mo', 'bed': 2, 'bath': 2.5, 'area': 1542, 'daysOnZillow': 2, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/410-N-Oakhurst-Dr-Beverly-Hills-CA-90210/20515231_zpid/', 'title': 'Apartment for rent'}, {'zid': '20523669', 'address': '1199 Tower Grove Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$9,995/mo', 'bed': 3, 'bath': 4.5, 'area': 3905, 'daysOnZillow': 3, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/1199-Tower-Grove-Dr-Beverly-Hills-CA-90210/20523669_zpid/', 'title': 'House for rent'}, {'zid': '20519980', 'address': '714 N Sierra Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$25,000/mo', 'bed': 6, 'bath': 6.5, 'area': 5052, 'daysOnZillow': 3, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/714-N-Sierra-Dr-Beverly-Hills-CA-90210/20519980_zpid/', 'title': 'House for rent'}, {'zid': '20533165', 'address': '13425 Java Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$13,000/mo', 'bed': 3, 'bath': 2.5, 'area': 4000, 'daysOnZillow': 3, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/13425-Java-Dr-Beverly-Hills-CA-90210/20533165_zpid/', 'title': 'House for rent'}, {'zid': '2076944736', 'address': '325 N Palm Dr #C', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$1,600/mo', 'bed': 1, 'bath': 1.0, 'area': None, 'daysOnZillow': 4, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/325-N-Palm-Dr-C-Beverly-Hills-CA-90210/2076944736_zpid/', 'title': 'Condo for rent'}, {'zid': '119676569', 'address': '9853 Portola Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,650/mo', 'bed': 2, 'bath': 2.0, 'area': 1070, 'daysOnZillow': 6, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/9853-Portola-Dr-Beverly-Hills-CA-90210/119676569_zpid/', 'title': 'House for rent'}, {'zid': '2083798704', 'address': '9160 Beverly Blvd APT 104', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$2,695/mo', 'bed': 2, 'bath': 1.5, 'area': 1000, 'daysOnZillow': 6, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/9160-Beverly-Blvd-APT-104-Beverly-Hills-CA-90210/2083798704_zpid/', 'title': 'Apartment for rent'}, {'zid': '2076974662', 'address': '906 Benedict Canyon Dr #VILLA1', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,395/mo', 'bed': 2, 'bath': 1.0, 'area': 1250, 'daysOnZillow': 7, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/906-Benedict-Canyon-Dr-VILLA1-Beverly-Hills-CA-90210/2076974662_zpid/', 'title': 'Condo for rent'}, {'zid': '20521218', 'address': '517 N Canon Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$13,995/mo', 'bed': 5, 'bath': 3.0, 'area': 4007, 'daysOnZillow': 8, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/517-N-Canon-Dr-Beverly-Hills-CA-90210/20521218_zpid/', 'title': 'House for rent'}, {'zid': '20520891', 'address': '262 N Crescent Dr APT 1B', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,295/mo', 'bed': 2, 'bath': 2.0, 'area': 1410, 'daysOnZillow': 8, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/262-N-Crescent-Dr-APT-1B-Beverly-Hills-CA-90210/20520891_zpid/', 'title': 'Apartment for rent'}, {'zid': '20523789', 'address': '10134 Angelo View Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$30,000/mo', 'bed': 4, 'bath': 3.5, 'area': 3332, 'daysOnZillow': 9, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/10134-Angelo-View-Dr-Beverly-Hills-CA-90210/20523789_zpid/', 'title': 'House for rent'}, {'zid': '20534488', 'address': '450 Trousdale Pl', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$19,995/mo', 'bed': 6, 'bath': 7.0, 'area': 6955, 'daysOnZillow': 13, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/450-Trousdale-Pl-Beverly-Hills-CA-90210/20534488_zpid/', 'title': 'House for rent'}, {'zid': '20534116', 'address': '2600 Bowmont Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$35,000/mo', 'bed': 8, 'bath': 11.0, 'area': 10337, 'daysOnZillow': 15, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/2600-Bowmont-Dr-Beverly-Hills-CA-90210/20534116_zpid/', 'title': 'House for rent'}, {'zid': '20523795', 'address': '1280 Angelo Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$40,000/mo', 'bed': 7, 'bath': 8.0, 'area': 7767, 'daysOnZillow': 16, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/1280-Angelo-Dr-Beverly-Hills-CA-90210/20523795_zpid/', 'title': 'House for rent'}, {'zid': '20519765', 'address': '605 Foothill Rd', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$19,500/mo', 'bed': 7, 'bath': 9.5, 'area': 7812, 'daysOnZillow': 16, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/605-Foothill-Rd-Beverly-Hills-CA-90210/20519765_zpid/', 'title': 'House for rent'}, {'zid': '20523643', 'address': '1500 Benedict Canyon Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$5,500/mo', 'bed': 2, 'bath': 2.5, 'area': 1359, 'daysOnZillow': 17, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/1500-Benedict-Canyon-Dr-Beverly-Hills-CA-90210/20523643_zpid/', 'title': 'House for rent'}, {'zid': '20520063', 'address': '412 N Palm Dr APT 203', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$4,150/mo', 'bed': 2, 'bath': 2.0, 'area': 1579, 'daysOnZillow': 19, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/412-N-Palm-Dr-APT-203-Beverly-Hills-CA-90210/20520063_zpid/', 'title': 'Apartment for rent'}, {'zid': '20521030', 'address': '605 N Rexford Dr', 'city': 'Beverly Hills', 'state': 'CA', 'postal_code': '90210', 'price': '$14,995/mo', 'bed': 4, 'bath': 3.5, 'area': 3100, 'daysOnZillow': 19, 'lastUpdated': '2020-12-11', 'onMarket': True, 'url': 'https://www.zillow.com/homedetails/605-N-Rexford-Dr-Beverly-Hills-CA-90210/20521030_zpid/', 'title': 'House for rent'}]
        if scraped_data:
            print ("Writing data to database")
            print(len(scraped_data))
            update_db(scraped_data, zipcode)