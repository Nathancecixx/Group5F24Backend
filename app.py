from flask import Flask, request, jsonify
from marshmallow import Schema, fields, ValidationError

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



# Define schemas for data validation
class LocationSchema(Schema):
    timestamp = fields.DateTime(required=True)
    latitude = fields.Float(required=True)
    longitude = fields.Float(required=True)
    speed = fields.Float(required=True)

class DriveSessionSchema(Schema):
    startTime = fields.DateTime(required=True)
    locations = fields.List(fields.Nested(LocationSchema), required=True)
    totalDistance = fields.Float(required=True)


@app.route('/upload-session', methods=['POST'])
def upload_json():
    if request.is_json:
        data = request.get_json()
        # Validate incoming data
        try:
            validated_data = DriveSessionSchema().load(data)
        except ValidationError as err:
            return jsonify(err.messages), 400

        print("Data: ", data)
        return jsonify({"message": "Session received successfully", "data": data}), 200
    else:
        return jsonify({"error": "Request must be in JSON format"}), 400



@app.route("/")
def home():
    return "Hello, Flask!"


if __name__ == '__main__':
    app.run(debug =True, host='0.0.0.0')
