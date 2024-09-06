from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_caching import Cache
import json
import os
from context import *


app = Flask(__name__)
CORS(app)

cache = Cache()
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 600
app.config['CACHE_KEY_PREFIX'] = 'chromashop_'
cache.init_app(app)

testMode = False


@app.route('/api/contact', methods=['POST'])
def contact():
    data = request.json

    if data['name'] and data['email'] and data['subject'] and data['message']:
        files = os.listdir('Contacts')

        with open(f'Contacts/{len(files)}.txt', 'a+') as fo:
            fo.write(json.dumps(data, indent=2))

        return "", 201

    return "", 400


@app.route('/api/review', methods=['POST'])
def review():
    data = request.json

    with openBlocking("reviews.txt", "a") as fo:
        fo.write(", ".join(data.values) + "\n")

    return "", 201


@app.route('/api/shops', methods=['GET'])
def shop():
    url = f'{printifyURL}/shops.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/api/items/', methods=['GET'])
@cache.cached()
def getItems():
    url = f'{printifyURL}/shops/{shopID}/products.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/api/item/<itemID>', methods=['GET'])
@cache.cached()
def getItem(itemID):
    url = f'{printifyURL}/shops/{shopID}/products/{itemID}.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/api/order/shipping', methods=['POST'])
def calcShipping():
    url = f'{printifyURL}/shops/{shopID}/orders/shipping.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}',
        'Content-Type': 'application/json'
    }
    data = request.json
    response = requests.post(url, headers=headers, json=data)
    return jsonify(response.json()), response.status_code


def dummyOrder():
    response = createPaypalOrder(14.99)

    return jsonify(response.json()), response.status_code


@app.route('/api/order/create', methods=['POST'])
def createOrder():
    if testMode:
        return dummyOrder()

    url = f'{printifyURL}/shops/{shopID}/orders.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}',
        'Content-Type': 'application/json'
    }
    data = request.json

    addressTo = data['address_to']
    firstName = addressTo['first_name']
    lastName = addressTo['last_name']
    email = addressTo['email']

    date = datetime.datetime.now().strftime('%m/%d/%Y %H:%M:%S')

    orderID = firstName + " " + lastName + " " + date

    data["shipping_method"] = 1
    data["is_printify_express"] = False
    data["external_id"] = orderID

    response = requests.post(url, headers=headers, json=data)

    if not response.ok:
        return jsonify(response.json()), response.status_code

    printifyOrderID = response.json()["id"]

    url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}.json'
    response = requests.get(url, headers=headers)

    if not response.ok:
        return jsonify(response.json()), response.status_code

    totalPrice = 0

    for item in response.json()['line_items']:
        amount = item['quantity'] * item['metadata']['price'] / 100
        totalPrice += amount

    total = totalPrice + response.json()['total_shipping'] / 100
    total = total * 1.0811
    total = int(total * 100) / 100

    response = createPaypalOrder(total)

    with openBlocking("opened.txt", "a") as fo:
        fo.write(f'{response.json()["id"]}: {printifyOrderID}: {date}: {email}\n')

    return jsonify(response.json()), response.status_code


def dummyProcess(paypalOrderID):
    captureResponse = capturePaypalOrder(paypalOrderID)

    emailTemplate = open("orderEmailTemplate.html", "r").read().replace('ORDERNUMBER', '66d648c6e5e6a403d40c2da7')
    sendEmail("Track your Chroma Crash Order", emailTemplate, "orders", "technowaffles46@gmail.com")

    return jsonify(captureResponse.json()), captureResponse.status_code


@app.route('/api/order/process/<paypalOrderID>', methods=['POST'])
def processOrder(paypalOrderID):
    if testMode:
        return dummyProcess(paypalOrderID)

    captureResponse = capturePaypalOrder(paypalOrderID)

    printifyOrderID = ""
    email = ""
    with openBlocking("opened.txt", "r") as fo:
        for line in fo.readlines():
            if line.startswith(paypalOrderID):
                printifyOrderID = line.split(":")[1][1:]
                email = line.split(": ")[3]

    if not captureResponse.ok:
        cancelPrintifyOrder(printifyOrderID)
        return jsonify(captureResponse.json()), captureResponse.status_code

    with openBlocking("captured.txt", "a") as fo:
        fo.write(f'{printifyOrderID}\n')

    emailTemplate = open("orderEmailTemplate.html", "r").read().replace('ORDERNUMBER', printifyOrderID)
    sendEmail("Track your Chroma Crash Order", emailTemplate, "orders", email)

    # sendOrderToProduction(printifyOrderID)

    return jsonify(captureResponse.json()), captureResponse.status_code


@app.route('/api/order/find/<paypalOrderID>', methods=['GET'])
@cache.cached()
def findPrintifyOrderNumber(paypalOrderID):
    if testMode:
        return jsonify({"id": "66d648c6e5e6a403d40c2da7"}), 200

    printifyOrderID = ""
    with openBlocking("opened.txt", "r") as fo:
        for line in fo.readlines():
            if line.startswith(paypalOrderID):
                printifyOrderID = line.split(":")[1][1:]

    if printifyOrderID == "":
        return "", 400

    data = {"id": printifyOrderID}

    return jsonify(data), 200


@app.route('/api/order/track/<printifyOrderID>', methods=['GET'])
@cache.cached()
def trackOrder(printifyOrderID):
    url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}',
        'Content-Type': 'application/json'
    }

    response = requests.get(url, headers=headers)

    return jsonify(response.json()), response.status_code


def cancelPrintifyOrder(printifyOrderID):
    url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}/cancel.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }

    response = requests.post(url, headers=headers)

    return jsonify(response.json()), response.status_code


def generateAccessToken():
    url = f'{paypalURL}/v1/oauth2/token'
    data = "grant_type=client_credentials"
    headers = {
        'Authorization': f'Basic {paypalToken}'
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()['access_token']


@app.route('/api/token', methods=['POST'])
def getClientToken():
    accessToken = generateAccessToken()
    url = f'{paypalURL}/v1/identity/generate-token'
    headers = {
        'Authorization': f'Bearer {accessToken}',
        'Accept-Language': 'en_US',
        'Content-Type': 'application/json'
    }

    response = requests.post(url, headers=headers)

    return jsonify(response.json()), response.status_code


def createPaypalOrder(amount):
    accessToken = generateAccessToken()
    url = f'{paypalURL}/v2/checkout/orders'
    headers = {
        'Authorization': f'Bearer {accessToken}',
        'Content-Type': 'application/json'
    }
    data = {
        'intent': 'CAPTURE',
        'purchase_units': [
            {
                'amount': {
                    'currency_code': 'USD',
                    'value': f'{amount}'
                }
            }
        ]
    }

    response = requests.post(url, headers=headers, json=data)

    return response


def capturePaypalOrder(orderID):
    oAuthToken = generateAccessToken()

    url = f'{paypalURL}/v2/checkout/orders/{orderID}/capture'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {oAuthToken}'
    }

    response = requests.post(url, headers=headers)

    return response


if __name__ == '__main__':
    cleanup()

    app.run(port=5000)
