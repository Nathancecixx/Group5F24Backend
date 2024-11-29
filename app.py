from scoreAlgorithm import calcDrivingScore
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


@app.route('/upload-session', methods=['POST'])
@token_required
def upload_session_json(current_userId):
    if request.is_json:
        data = request.get_json()

        try:
            validated_data = DriveSessionSchema().load(data)
        except ValidationError as err:
            return jsonify(err.messages), 400

        locations = validated_data.get('locations', [])
        total_distance = validated_data.get('totalDistance', 0)
        start_time = validated_data.get('startTime')

        if not locations or total_distance <= 0:
            return jsonify({"error": "Invalid session data: locations or total distance missing"}), 400

        locations.sort(key=lambda x: x['timestamp']) #sort location by the timestamp

        end_time = locations[-1]['timestamp']

        duration_minutes = (end_time - start_time).total_seconds() / 60 #calculate the session duration in mintues

        average_speed = total_distance / (duration_minutes / 60) if duration_minutes > 0 else 0 # calculate average speed

        behavior_score = 100.0  # intialize with a perfect score, and then it will go down as you make bad choices in life
        SPEED_LIMIT = 60 
        SPEEDING_PENALTY = 5  

        for location in locations:
            if location['speed'] > SPEED_LIMIT:
                behavior_score -= SPEEDING_PENALTY

        behavior_score = max(0, behavior_score)

        # use the calcDrivingScore function found in the scoreAlgorithm file, that will return the
        # driving score based on the session data
        session_driving_score = calcDrivingScore(
            locations=locations,
            speed=average_speed,
            distance=total_distance,
            behavior_score=behavior_score,
            duration_minutes=duration_minutes,
        )

        start_time_str = start_time.isoformat()
        end_time_str = end_time.isoformat()

        # insert the session stuff in the database
        db_conn = db.get_db()
        cursor = db_conn.cursor()
        cursor.execute('''
            INSERT INTO driveSessions (startTime, endTime, distance, averageSpeed, sessionDrivingScore, userID)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (start_time_str, end_time_str, total_distance, average_speed, session_driving_score, current_userId))
        db_conn.commit()

        return jsonify({
            "message": "Session received and stored successfully",
            "drivingScore": session_driving_score,
        }), 200
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


# to get recent session
@app.route('/get-recent-session', methods=['GET'])
@token_required
def get_recent_session(current_userId):
    db_conn = db.get_db()
    cursor = db_conn.cursor()

    # Query to get the most recent driving session for the current user
    cursor.execute('''
        SELECT startTime, endTime, distance, averageSpeed, sessionDrivingScore 
        FROM driveSessions 
        WHERE userID = ? 
        ORDER BY startTime DESC 
        LIMIT 1
    ''', (current_userId,))

    session = cursor.fetchone()

    if session:
        # Convert the result to a dictionary for easy jsonify response
        session_dict = {
            'startTime': session['startTime'],
            'endTime': session['endTime'],
            'totalDistance': session['distance'],
            'averageSpeed': session['averageSpeed'],
            'sessionDrivingScore': session['sessionDrivingScore']
        }
        return jsonify(session_dict), 200
    else:
        return jsonify({"error": "No recent session found for user"}), 404

# recent session ended


if __name__ == '__main__':
    db.init_app(app)
    with app.app_context():
        db.init_db()
    app.run(debug=True, host='0.0.0.0')
