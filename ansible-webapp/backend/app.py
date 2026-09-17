from flask import Flask, jsonify

app = Flask(__name__)


@app.route('/test')
def test():
    return jsonify({
        "status": "success",
        "message": "Backend is working!"
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)