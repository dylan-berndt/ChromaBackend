import threading
import requests
import base64
import datetime
from contextlib import contextmanager

tokens = open('tokens.txt').read().split('\n')

printifyToken = tokens[0]
shopID = 16951213
printifyURL = 'https://api.printify.com/v1'

paypalToken = ":".join(tokens[1:])
paypalToken = base64.b64encode(paypalToken.encode()).decode()
paypalURL = "https://api-m.sandbox.paypal.com"
# paypalURL = "https://sandbox.paypal.com"

locks = {
    "opened.txt": threading.Lock(),
    "captured.txt": threading.Lock(),
    "finalized.txt": threading.Lock(),
    "reviews.txt": threading.Lock(),
}


@contextmanager
def openBlocking(fileName, fileMode):
    if fileName in locks:
        locks[fileName].acquire()

    try:
        file = open(fileName, fileMode)
        yield file
    finally:
        file.close()
        if fileName in locks:
            locks[fileName].release()


def sendOrderToProduction(printifyOrderID):
    url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}/send_to_production.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }

    response = requests.post(url, headers=headers)

    return response.ok


def cancelOrder(printifyOrderID):
    url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}/cancel.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}',
        'Content-Type': 'application/json'
    }
    response = requests.post(url, headers=headers)
    return response


# Remove orders that are opened and not captured,
# or process orders that are captured but not finalized
def cleanup():
    with openBlocking('opened.txt', 'r+') as fo:
        with openBlocking('captured.txt', 'r') as co:
            captured = [line.rstrip() for line in co.readlines()]

            lines = fo.readlines()
            fo.seek(0)
            for line in lines:
                line = line.rstrip()
                printifyOrderID = line.split(": ")[1]
                createdAt = line.split(": ")[2]

                # Order created but not paid for
                if printifyOrderID not in captured:
                    date = datetime.datetime.strptime(createdAt, '%m/%d/%Y %H:%M:%S')
                    now = datetime.datetime.now()
                    diff = now - date

                    # Order has existed for more than 2 hours
                    if diff.total_seconds() / 3600 > 2:
                        # Goodbye order
                        if not cancelOrder(printifyOrderID).ok:
                            print("AHHH")
                        continue

                fo.write(line + '\n')

            fo.truncate()

    with openBlocking('finalized.txt', 'a') as fo:
        with openBlocking('captured.txt', 'r+') as co:
            lines = co.readlines()
            co.seek(0)
            for line in lines:
                line = line.rstrip()
                printifyOrderID = line

                # Printify is very annoying, so I have to wait a random amount of
                # time to send orders to production
                if sendOrderToProduction(printifyOrderID):
                    # Order finalized, write to finalized and skip writing to
                    # captured, also: YIPPEE
                    fo.write(printifyOrderID + '\n')

                    continue

                co.write(line + '\n')

            co.truncate()

    # I now it's goofy, but it's non-blocking so nyah
    threading.Timer(60 * 60 * 2, cleanup).start()

