CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);
CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, fk INTEGER, title TEXT);
INSERT INTO moz_places(id, url) VALUES (1, 'https://alpha.example.invalid/');
INSERT INTO moz_bookmarks(id, fk, title) VALUES (1, 1, 'Alpha');
