from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Server is running"}), 200

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        print(f"Received message: {user_message}")
        
        # Simple echo response for testing
        return jsonify({
            "status": "success",
            "message": f"Echo: {user_message}"
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    print("Attempting to bind to: http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)