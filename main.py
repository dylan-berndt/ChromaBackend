from flask import Flask, jsonify, request
import requests
from flask_cors import CORS
from flask_caching import Cache

app = Flask(__name__)
CORS(app)

cache = Cache()
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 240
app.config['CACHE_KEY_PREFIX'] = 'chromashop_'
cache.init_app(app)

token = open('tokens.txt').read().replace('\n', '')
shopID = 16951213


@app.route('/printify', methods=['GET'])
def shop():
    url = 'https://api.printify.com/v1/shops.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/printify/items/')
def getItems():
    url = f'https://api.printify.com/v1/shops/{shopID}/products.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


@app.route('/printify/item/<itemID>')
def getItem(itemID):
    url = f'https://api.printify.com/v1/shops/{shopID}/products/{itemID}.json'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


if __name__ == '__main__':
    app.run(port=5000)
