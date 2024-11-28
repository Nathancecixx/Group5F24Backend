from flask import Flask, request, jsonify
from marshmallow import Schema, fields, ValidationError
from datetime import datetime, timezone, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import db


app = Flask(__name__) 


# Key to encrypt and decrypt jwt
SECRET_KEY = 'A2Ksc8sKshscl7fwf3FHW2'

# TODO: Implement function to clear expired tokens from backlist
# In-memory token blacklist
token_blacklist = set()


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
            current_userId = data['userId']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401

        # Pass the current user id to the route
        return f(current_userId, *args, **kwargs)

    return decorated



@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    db_conn = db.get_db()
    cursor = db_conn.cursor()
    # Check if the email is already registered
    cursor.execute('SELECT * FROM users WHERE userEmail = ?', (email,))
    user = cursor.fetchone()
    if user:
        return jsonify({"error": "User already registered"}), 400

    # Hash the password for secure storage
    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

    # Insert the user into the database
    cursor.execute('''
        INSERT INTO users (userName, userEmail, userPassword)
        VALUES (?, ?, ?)
    ''', (None, email, hashed_password))
    db_conn.commit()
    return jsonify({"message": "User registered successfully"}), 201



@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400


    #Get the user from db
    db_conn = db.get_db()
    cursor = db_conn.cursor()
    cursor.execute('SELECT userID, userName, userEmail, userPassword FROM users WHERE userEmail = ?', (email,))
    user = cursor.fetchone()
    if not user:
        return jsonify({'message': 'Invalid credentials!'}), 401
    
    
    user_password_hash = user['userPassword']
    if not check_password_hash(user_password_hash, password):
        return jsonify({'message': 'Invalid credentials!'}), 401

    # Generate JWT token
    token = jwt.encode({
        'userId': user['userId'],
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

def calcDrivingScore(locations):
    MAX_SCORE = 100.0
    ACCELERATION_THRESHOLD = 3.0  # m/s²
    ACCELERATION_WEIGHT = 5.0  # Penalty per harsh acceleration/braking event

    # Initialize penalties
    total_acceleration_penalty = 0.0

    # Sort locations by timestamp
    locations_sorted = sorted(locations, key=lambda x: x['timestamp'])

    speeds_mps = []  # Speeds in m/s
    time_stamps = []  # Timestamps in seconds

    for loc in locations_sorted:
        speed_kmh = loc['speed']
        speed_mps = speed_kmh * (1000 / 3600)  # Convert km/h to m/s
        speeds_mps.append(speed_mps)

        # Append the timestamp
        timestamp = loc['timestamp'].timestamp()  # Convert to Unix timestamp
        time_stamps.append(timestamp)

    # Acceleration penalty
    for i in range(1, len(speeds_mps)):
        v1 = speeds_mps[i - 1]
        v2 = speeds_mps[i]
        t1 = time_stamps[i - 1]
        t2 = time_stamps[i]
        delta_v = v2 - v1
        delta_t = t2 - t1

        # Avoid division by zero and negative delta_t
        if delta_t <= 0:
            continue

        acceleration = delta_v / delta_t  # m/s²

        if acceleration > ACCELERATION_THRESHOLD or acceleration < -ACCELERATION_THRESHOLD:
            total_acceleration_penalty += ACCELERATION_WEIGHT

    # Calculate total penalty
    total_penalty = total_acceleration_penalty

    # Calculate final driving score
    session_driving_score = MAX_SCORE - total_penalty

    # Ensure the score is within 0 to MAX_SCORE
    session_driving_score = max(0.0, min(MAX_SCORE, session_driving_score))

    return session_driving_score


@app.route('/upload-session', methods=['POST'])
@token_required
def upload_session_json(current_userId):
    if request.is_json:
        data = request.get_json()
        # Validate incoming data
        try:
            validated_data = DriveSessionSchema().load(data)
        except ValidationError as err:
            return jsonify(err.messages), 400

        # Extract data
        startTime = validated_data['startTime']
        locations = validated_data['locations']
        totalDistance = validated_data['totalDistance']

        # Ensure locations are sorted by timestamp
        locations.sort(key=lambda x: x['timestamp'])

        # Compute endTime from the last location's timestamp
        endTime = locations[-1]['timestamp']

        # Compute averageSpeed as the average of speeds from locations
        speeds = [loc['speed'] for loc in locations]
        averageSpeed = sum(speeds) / len(speeds)

        # Compute sessionDrivingScore
        sessionDrivingScore = calcDrivingScore(locations)

        # Convert datetime objects to ISO format strings
        startTime_str = startTime.isoformat()
        endTime_str = endTime.isoformat()

        # Insert the session into the database
        db_conn = db.get_db()
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO driveSessions (startTime, endTime, distance, averageSpeed, sessionDrivingScore, userID)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (startTime_str, endTime_str, totalDistance, averageSpeed, sessionDrivingScore, current_userId))
        db_conn.commit()

        return jsonify({"message": "Session received and stored successfully"}), 200
    else:
        return jsonify({"error": "Request must be in JSON format"}), 400


@app.route('/get-user-stats', methods=['GET'])
@token_required
def get_user_stats(current_userId):
    db_conn = db.get_db()
    cursor = db_conn.cursor()
    cursor.execute('''
        SELECT totalDistance, averageSpeed, totalSessions, totalDrivingScore
        FROM userStats
        WHERE userID = ?
    ''', (current_userId,))
    stats = cursor.fetchone()
    if stats:
        # Convert the sqlite3.Row object to a dictionary
        stats_dict = {
            'totalDistance': stats['totalDistance'],
            'averageSpeed': stats['averageSpeed'],
            'totalSessions': stats['totalSessions'],
            'totalDrivingScore': stats['totalDrivingScore']
        }
        return jsonify(stats_dict), 200
    else:
        return jsonify({"error": "No stats found for user"}), 404


if __name__ == '__main__':
    db.init_app(app)
    with app.app_context():
        db.init_db()
    app.run(debug=True, host='0.0.0.0')
