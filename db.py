import sqlite3
from flask import g

DATABASE = 'driveaware.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_app(app):
    app.teardown_appcontext(close_connection)


def init_db():
    db = get_db()
    cursor = db.cursor()
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        userID INTEGER PRIMARY KEY AUTOINCREMENT,
        userName TEXT,
        userEmail TEXT NOT NULL UNIQUE,
        userPassword TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS driveSessions (
        sessionID INTEGER PRIMARY KEY AUTOINCREMENT,
        startTime TIMESTAMP NOT NULL,
        endTime TIMESTAMP NOT NULL,
        distance REAL NOT NULL,
        averageSpeed REAL,
        sessionDrivingScore REAL,
        userID INTEGER,
        FOREIGN KEY (userID) REFERENCES users(userID) ON DELETE CASCADE
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS userStats (
        statID INTEGER PRIMARY KEY AUTOINCREMENT,
        totalDistance REAL NOT NULL,
        averageSpeed REAL NOT NULL,
        totalSessions INTEGER NOT NULL DEFAULT 0,
        totalDrivingScore REAL NOT NULL,
        userID INTEGER UNIQUE,
        FOREIGN KEY (userID) REFERENCES users(userID) ON DELETE CASCADE
    )
    ''')
    # Create trigger
    cursor.execute('''
    CREATE TRIGGER IF NOT EXISTS after_driveSession_insert
    AFTER INSERT ON driveSessions
    BEGIN
        INSERT OR IGNORE INTO userStats (userID, totalDistance, averageSpeed, totalSessions, totalDrivingScore)
        VALUES (
            NEW.userID,
            NEW.distance,
            NEW.averageSpeed,
            1,
            NEW.sessionDrivingScore
        );

        UPDATE userStats
        SET totalDrivingScore = (
                SELECT AVG(sessionDrivingScore)
                FROM driveSessions
                WHERE userID = NEW.userID
            ),
            totalDistance = (
                SELECT SUM(distance)
                FROM driveSessions
                WHERE userID = NEW.userID
            ),
            averageSpeed = (
                SELECT AVG(averageSpeed)
                FROM driveSessions
                WHERE userID = NEW.userID
            ),
            totalSessions = (
                SELECT COUNT(*)
                FROM driveSessions
                WHERE userID = NEW.userID
            )
        WHERE userID = NEW.userID;
    END;
    ''')
    db.commit()

