# this function is going to be used in the app.py 
# to calculate the driving score for a session
# in the "uplooad session" endpoint


def calcDrivingScore(locations, speed, distance, behavior_score, duration_minutes):
    MAX_SCORE = 100.0 #the default score, and then it will go down if you do silly things while driving

    # m/s² - If the acceleration exceeds this value (either positively or negatively), it is flagged as harsh driving behavior
    ACCELERATION_THRESHOLD = 3.0  
    ACCELERATION_WEIGHT = 5.0  # 5 point penalty


    # speed limit is set to 60 because young drivers dont tend to go on highways, and the limit in cities is usually 60
    SPEED_LIMIT = 60  
    SPEED_PENALTY_WEIGHT = 10.0  # 10 Penalty

    MAX_DISTANCE_SCORE = 50.0  # Max score for long distances
    DISTANCE_WEIGHT = 2.0 

    MAX_DURATION_SCORE = 20.0  # Max score for long durations
    DURATION_WEIGHT = 5.0

    total_acceleration_penalty = 0.0
    total_penalty = 0.0
    speeds_mps = []
    time_stamps = []

    # Process location data for acceleration penalties
    locations_sorted = sorted(locations, key=lambda x: x['timestamp'])
    for loc in locations_sorted:
        speed_kmh = loc['speed']
        speed_mps = speed_kmh * (1000 / 3600)  # Convert km/h to m/s
        speeds_mps.append(speed_mps)
        time_stamps.append(loc['timestamp'].timestamp())

    # Calculate acceleration penalties
    for i in range(1, len(speeds_mps)):
        v1 = speeds_mps[i - 1]
        v2 = speeds_mps[i]
        t1 = time_stamps[i - 1]
        t2 = time_stamps[i]
        delta_v = v2 - v1
        delta_t = t2 - t1

        if delta_t > 0:
            acceleration = delta_v / delta_t
            if acceleration > ACCELERATION_THRESHOLD or acceleration < -ACCELERATION_THRESHOLD:
                total_acceleration_penalty += ACCELERATION_WEIGHT

    # calculate speed penalty
    speed_penalty = max(0, abs(speed - SPEED_LIMIT) / 20 * SPEED_PENALTY_WEIGHT)

    # calculate distance score
    distance_score = min(MAX_DISTANCE_SCORE, distance / DISTANCE_WEIGHT)

    # make sure the score is valid so far
    behavior_score = max(0, min(100, behavior_score))

    # calculate duration score
    duration_score = min(MAX_DURATION_SCORE, (duration_minutes / 30) * DURATION_WEIGHT)

    # Combine penalties and scores
    total_penalty = total_acceleration_penalty + speed_penalty
    session_driving_score = (
        MAX_SCORE - total_penalty + distance_score + behavior_score + duration_score
    )

    # make sure the score is valid so far
    session_driving_score = max(0.0, min(MAX_SCORE, session_driving_score))

    return session_driving_score