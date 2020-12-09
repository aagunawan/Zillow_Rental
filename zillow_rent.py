from urllib.request import Request, urlopen
from lxml import html
import requests
import unicodecsv as csv
import argparse
import json
import pymongo
from pymongo import MongoClient


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
    # url = "https://www.zillow.com/homes/53726_rb/"
   
    # if filter == "newest":
    #     url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/days_sort".format(zipcode)
    # elif filter == "cheapest":
    #     url = "https://www.zillow.com/homes/for_sale/{0}/0_singlestory/pricea_sort/".format(zipcode)
    # else:
    # url = "https://www.zillow.com/homes/hillsboro-or-{0}/rent-houses/".format(zipcode)
    url = "https://www.zillow.com/homes/for_rent/{0}_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy".format(zipcode)
    # url = "https://www.zillow.com/homes/for_rent/55454_rb/?fromHomePage=true&shouldFireSellPageImplicitClaimGA=false&fromHomePageTab=buy"
    print(url)
    return url


def save_to_file(response):
    # saving response to `response.html`

    with open("response.html", 'w') as fp:
        fp.write(response.text)


def write_data_to_csv(data):
    # saving scraped data to csv.

    with open("properties-%s.csv" % (zipcode), 'wb') as csvfile:
        fieldnames = ['title', 'address', 'city', 'state', 'postal_code', 'price', 'bed', 'bath', 'area', 'daysOnZillow', 'url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data:
            writer.writerow(row)

def write_to_db(data, zipcode):
    cluster = MongoClient("mongodb+srv://aagunawan:dedeku88@cluster0.qfiad.mongodb.net/<dbname>?retryWrites=true&w=majority")
    db = cluster["rental"]
    collection = db["listings"] 
    collection.drop()
    collection.insert_many(data)

def get_response(url):
    # Getting response from zillow.com.

    for i in range(5):
        response = requests.get(url, headers=get_headers())
        print("status code received:", response.status_code)
        if response.status_code != 200:
            # saving response to file for debugging purpose.
            save_to_file(response)
            continue
        else:
            save_to_file(response)
            return response
    return None

def get_data_from_json(raw_json_data):
    # getting data from json (type 2 of their A/B testing page)

    cleaned_data = clean(raw_json_data).replace('<!--', "").replace("-->", "")
    properties_list = []

    try:
        json_data = json.loads(cleaned_data)
        # search_results = json_data.get('searchResults').get('listResults', [])
        search_results = json_data.get('cat1').get('searchResults').get('listResults', [])
        # print(search_results[0])
        # print(search_results[1])
        for properties in search_results:
            address = properties.get('addressStreet')
            property_info = properties.get('hdpData', {}).get('homeInfo')
            if (property_info):

                city = property_info.get('city')
                # print(property_info.get('daysOnZillow'))
                # print(properties.get('statusType'))
                state = property_info.get('state')
                postal_code = property_info.get('zipcode')
                price = properties.get('price')
                bedrooms = properties.get('beds')
                bathrooms = properties.get('baths')
                area = properties.get('area')
                info = f'{bedrooms} bds, {bathrooms} ba ,{area} sqft'
                daysOnZillow = property_info.get('daysOnZillow')
                property_url = properties.get('detailUrl')
                title = properties.get('statusText')

                data = {'address': address,
                        'city': city,
                        'state': state,
                        'postal_code': postal_code,
                        'price': price,
                        'bed': bedrooms,
                        'bath': bathrooms,
                        'area': area,
                        # 'facts and features': info,
                        'daysOnZillow': daysOnZillow,
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
    #parser = html.fromstring(response.text)
    parser = html.fromstring(webpage)

    # parser = html.fromstring(response.text)
    search_results = parser.xpath("//div[@id='search-results']//article")
    

    if not search_results:
        print("parsing from json data")
        # identified as type 2 page
        raw_json_data = parser.xpath('//script[@data-zrr-shared-data-key="mobileSearchPageStore"]//text()')
        return get_data_from_json(raw_json_data)

    # print("parsing from html page")
    # properties_list = []
    # for properties in search_results:
    #     raw_address = properties.xpath(".//span[@itemprop='address']//span[@itemprop='streetAddress']//text()")
    #     raw_city = properties.xpath(".//span[@itemprop='address']//span[@itemprop='addressLocality']//text()")
    #     raw_state = properties.xpath(".//span[@itemprop='address']//span[@itemprop='addressRegion']//text()")
    #     raw_postal_code = properties.xpath(".//span[@itemprop='address']//span[@itemprop='postalCode']//text()")
    #     raw_price = properties.xpath(".//span[@class='zsg-photo-card-price']//text()")
    #     raw_info = properties.xpath(".//span[@class='zsg-photo-card-info']//text()")
    #     raw_daysOnZillow = properties.xpath(".//span[@class='zsg-photo-card-broker-name']//text()")
    #     url = properties.xpath(".//a[contains(@class,'overlay-link')]/@href")
    #     raw_title = properties.xpath(".//h4//text()")

    #     address = clean(raw_address)
    #     city = clean(raw_city)
    #     state = clean(raw_state)
    #     postal_code = clean(raw_postal_code)
    #     price = clean(raw_price)
    #     info = clean(raw_info).replace(u"\xb7", ',')
    #     daysOnZillow = clean(raw_daysOnZillow)
    #     title = clean(raw_title)
    #     property_url = "https://www.zillow.com" + url[0] if url else None
    #     # is_forsale = properties.xpath('.//span[@class="zsg-icon-for-sale"]')

    #     properties = {'address': address,
    #                   'city': city,
    #                   'state': state,
    #                   'postal_code': postal_code,
    #                   'price': price,
    #                   'facts and features': info,
    #                   'daysOnZillow': daysOnZillow,
    #                   'url': property_url,
    #                   'title': title}
    #     # if is_forsale:
    #     properties_list.append(properties)
    # return properties_list


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
        print ("Writing new data to database")
        # write_data_to_csv(scraped_data)
        write_to_db(scraped_data, zipcode)