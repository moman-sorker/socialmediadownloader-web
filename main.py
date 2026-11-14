from flask import Flask, send_from_directory
import os

app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    base = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base, 'index.html')

if __name__ == '__main__':
    print("Client Panel is running..!")
    app.run(host='0.0.0.0', port=5000)