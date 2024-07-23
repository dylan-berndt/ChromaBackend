from flask import Flask, jsonify, request
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

token = open('tokens.txt').read().replace('\n', '')


@app.route('/printify', methods=['GET'])
def shop():
    url = 'https://api.printify.com/v1/shops.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/printify/items/<int:shopID>')
def getItems(shopID):
    url = f'https://api.printify.com/v1/shops/{shopID}/products.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/printify/item/<int:shopID>/<itemID>')
def getItem(shopID, itemID):
    url = f'https://api.printify.com/v1/shops/{shopID}/products/{itemID}.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


if __name__ == '__main__':
    app.run(port=5000)
