from flask import Flask, request, jsonify
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, timezone, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import jwt

app = Flask(__name__) 
# Key to encrypt and decrypt jwt
SECRET_KEY = 'A2Ksc8sKshscl7fwf3FHW2'
# TODO: Implement function to clear expired tokens from backlist
# In-memory token blacklist
token_blacklist = set()


# Temporary in-memory store for users (replace with a database later)
users = {}

# Wrapper function for routes to use jwt
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # JWT is expected in the Authorization header in the format: Bearer <token>
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            parts = auth_header.split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        if token in token_blacklist:
            return jsonify({'message': 'Token has been revoked!'}), 401

        try:
            # Decode the token to obtain the payload
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            current_user = data['email']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401

        # Pass the current_user to the route
        return f(current_user, *args, **kwargs)

    return decorated



@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    if email in users:
        return jsonify({"error": "User already registered"}), 400

    # Hash the password for secure storage
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Store the user in the in-memory store
    users[email] = hashed_password
    return jsonify({"message": "User registered successfully"}), 201



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    
    # Check password with saved hashed version
    user_password_hash = users.get(email)
    if not user_password_hash or not check_password_hash(user_password_hash, password):
        return jsonify({'message': 'Invalid credentials!'}), 401

    # Generate JWT token
    token = jwt.encode({
        'email': email,
        'exp': datetime.now(timezone.utc) + timedelta(minutes=30)
    }, SECRET_KEY, algorithm="HS256")

    return jsonify({'token': token}), 200


# Enpoint to logout a user by revoking their jwt token
@app.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    auth_header = request.headers.get('Authorization', None)
    token = auth_header.split()[1] if auth_header else None
    if token:
        token_blacklist.add(token)
    return jsonify({'message': 'Successfully logged out'}), 200



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
@token_required
def upload_session_json(current_user):
    if request.is_json:
        data = request.get_json()
        # Validate incoming data
        try:
            validated_data = DriveSessionSchema().load(data)
        except ValidationError as err:
            return jsonify(err.messages), 400

        print("Data: ", data)
        # Add data to database
        return jsonify({"message": "Session received successfully", "data": data}), 200
    else:
        return jsonify({"error": "Request must be in JSON format"}), 400

@app.route('/get-user-stats', methods={'POST'})
def get_user_stats():
    return "Hello World"


if __name__ == '__main__':
    app.run(debug =True, host='0.0.0.0')
