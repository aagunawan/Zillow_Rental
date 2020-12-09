import pymongo
from pymongo import MongoClient

cluster = MongoClient("mongodb+srv://aagunawan:dedeku88@cluster0.qfiad.mongodb.net/<dbname>?retryWrites=true&w=majority")
db = cluster["test"]
collection = db["test"]

# post1 = {"_id": 1, "name": "al", "score": 5}
# post2 = {"_id": 2, "name": "oliver", "score": 9}

# collection.insert_many([post1, post2])

results = collection.find({"name": "al"})
for result in results:
    print(result)