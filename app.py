from flask import Flask, request, jsonify

app = Flask(__name__) 


# Temporary in-memory store for users (replace with a database later)
users = {}

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if email in users:
        return jsonify({"error": "User already registered"}), 400

    users[email] = password
    return jsonify({"message": "User registered successfully"}), 201



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    stored_password = users.get(email)
    if stored_password is None or stored_password != password:
        return jsonify({"error": "Invalid email or password"}), 401

    return jsonify({"message": "Login successful"}), 200





@app.route('/upload-session', methods=['POST'])
def upload_json():
    if request.is_json:
        data = request.get_json()
        //Add logic to add session to database
        return jsonify({"message": "Session received successfully", "data": data}), 200
    else:
        return jsonify({"error": "Request must be in JSON format"}), 400




@app.route("/")
def home():
    return "Hello, Flask!"


if __name__ == '__main__':
    app.run(debug =True)
