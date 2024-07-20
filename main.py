from flask import Flask, jsonify, request
import requests
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route('/printify-api', methods=['GET'])
def proxy():
    adminToken = open('tokens.txt').read().replace('\n', '')
    url = 'https://api.printify.com/v1/shops.json'
    headers = {
        'Authorization': f'Bearer {adminToken}'
    }
    response = requests.get(url, headers=headers)
    return jsonify(response.json()), response.status_code


if __name__ == '__main__':
    app.run(port=5000)
