CREATE TABLE log (
    id INTEGER,
    user_id INTEGER NOT NULL,
    username TEXT NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price FLOAT NOT NULL,
    action TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    PRIMARY KEY(id)
);

