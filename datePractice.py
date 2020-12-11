from datetime import datetime

date = datetime.today().strftime('%Y-%m-%d')

def testDate():
    print(date)

testDate()