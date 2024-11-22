create database DriveAware;
use DriveAware;

create table users(							-- To store user account information
userID int auto_increment primary key,
userName varchar (50),
userEmail varchar(100) not null unique,
userPassword varchar(100) not null,
created_at timestamp default current_timestamp -- YYYY-MM-DD HH:MM:SS
);

create table driveSessions(               -- to store data for each driving session
sessionID int auto_increment primary key,
startTime timestamp not null,
endTime timestamp not null,
distance float not null,
averageSpeed float,
sessionDrivingScore float,
userID int,
foreign key (userID) references users(userID) on delete cascade
);

create table userStats( -- To store user statistics based on their driving sessions.
statID int auto_increment primary key,
totalDistance float not null,
averageSpeed float not null,
totalSessions int not null default 0,
totalDrivingScore float not null,
userID int,
foreign key (userID) references users(userID) on delete cascade
);



-- Trigger to handle updates to userStats after a new driving session is inserted
DELIMITER $$

create trigger after_driveSession_insert
after insert on driveSessions
for each row
begin
    -- Check if the user has an entry in userStats
    if not exists (select 1 
				   from userStats
                   where userID = new.userID) 
			then
        -- Insert a new row into userStats if none exists
        insert into userStats (userID, totalDistance, averageSpeed, totalSessions, totalDrivingScore)
        values (
            new.userID,
            new.distance,
            new.averageSpeed,
            1,
            new.sessionDrivingScore
        );
    else
        -- Update existing userStats
        update userStats
        set totalDrivingScore = (
            select SUM(sessionDrivingScore)
            from driveSessions
            where userID = new.userID
        ),
        totalDistance = (
            select SUM(distance)
            from driveSessions
            where userID = new.userID
        ),
        averageSpeed = (
            select AVG(averageSpeed)
            from driveSessions
            where userID = new.userID
        ),
        totalSessions = (
            select COUNT(*)
            from driveSessions
            where userID = new.userID
        )
        where userID = new.userID;
    end if;
end$$

DELIMITER ;

-- to insert a new user
-- insert into users (userEmail, userPassword) values ('xxxx@xx.', 'xxxxx');

-- to validate the email and password
select userID, userName, userEmail
from users
where userEmail = ? AND userPassword = ?; -- change '?' to the email and password

-- to insert a driving session
-- insert into driveSessions (startTime, endTime, distance, averageSpeed, sessionDrivingScore, userID) values ('2024-11-11 11:00:00', '2024-11-11 11:00:00', 50.0, 60.0, 85.0, 1);

-- to retrive the total driving score for a user
select totalDrivingScore
from userStats
where userID = ?; -- change '?' to user ID

-- to retrive the driving score for a user for the last driving session
select sessionDrivingScore
from driveSessions
where userID = ?; -- change '?' to user ID

-- to retrive all the stats for a user
select totalDistance, averageSpeed, totalSessions, totalDrivingScore
from userStats
where userID = ?; -- change '?' to user ID

-- to retrive the stats for the recent drive session
select sessionID, startTime, endTime, distance, averageSpeed, sessionDrivingScore
from driveSessions
where userID = ?  -- change '?' to user ID
order by startTime desc
limit 1;


-- to get the average driving scores accross all users: (kinda like the "global ranked boards")
select AVG(totalDrivingScore) as averageScore 
from userStats;


-- get the top 5 user by driving score
select userID, totalDrivingScore
from userStats
order by totalDrivingScore DESC
limit 5;

