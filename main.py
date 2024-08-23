from flask import Flask, jsonify, request
import requests
from flask_cors import CORS
from flask_caching import Cache
import uuid
import base64
import json

app = Flask(__name__)
CORS(app)

cache = Cache()
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 240
app.config['CACHE_KEY_PREFIX'] = 'chromashop_'
cache.init_app(app)

tokens = open('tokens.txt').read().split('\n')

printifyToken = tokens[0]
shopID = 16951213
printifyURL = 'https://api.printify.com/v1'

paypalToken = ":".join(tokens[1:])
paypalToken = base64.b64encode(paypalToken.encode()).decode()
paypalURL = "https://api-m.sandbox.paypal.com"
# paypalURL = "https://sandbox.paypal.com"


@app.route('/api/shops', methods=['GET'])
def shop():
    url = f'{printifyURL}/shops.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/api/items/', methods=['GET'])
def getItems():
    url = f'{printifyURL}/shops/{shopID}/products.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/api/item/<itemID>', methods=['GET'])
def getItem(itemID):
    url = f'https://api.printify.com/v1/shops/{shopID}/products/{itemID}.json'
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


@app.route('/api/order/create', methods=['POST'])
def createOrder():
    url = f'{printifyURL}/shops/{shopID}/orders.json'
    headers = {
        'Authorization': f'Bearer {printifyToken}',
        'Content-Type': 'application/json'
    }
    data = request.json

    orderID = str(uuid.uuid4())

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
        amount = item['metadata']['price'] / 100
        totalPrice += amount

    total = totalPrice + response.json()['total_shipping'] / 100
    total = total * 1.0811
    total = int(total * 100) / 100

    response = createPaypalOrder(total)

    if response.ok:
        with open("orders.txt", "a") as fo:
            fo.write(f'{response.json()["id"]}: {printifyOrderID}\n')

    return jsonify(response.json()), response.status_code


@app.route('/api/order/process/<paypalOrderID>', methods=['POST'])
def processOrder(paypalOrderID):
    captureResponse = capturePaypalOrder(paypalOrderID)

    if not captureResponse.ok:
        return jsonify(captureResponse.json()), captureResponse.status_code

    # printifyOrderID = ""
    # with open("orders.txt", "r") as fo:
    #     for line in fo.readlines():
    #         if line.startswith(paypalOrderID):
    #             printifyOrderID = line.split(":")[1][1:]
    #
    # if not printifyOrderID:
    #     return "FUCK", 500
    #
    # url = f'{printifyURL}/shops/{shopID}/orders/{printifyOrderID}/send_to_production.json'
    # headers = {
    #     'Authorization': f'Bearer {printifyToken}'
    # }
    #
    # response = requests.post(url, headers=headers)
    #
    # if not response.ok:
    #     print(response.text)
    #     return "", response.status_code

    return jsonify(captureResponse.json()), captureResponse.status_code


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
    app.run(port=5000)
