CREATE TABLE
IF NOT EXISTS releases (
 id integer PRIMARY KEY,
 title text NOT NULL,
 episode text NOT NULL,
 quality text NOT NULL,
 tags text NOT NULL,
 category text NOT NULL,
 date text,
 link text
);

CREATE TABLE
IF NOT EXISTS wishlist (
 id integer PRIMARY KEY,
 title text NOT NULL,
 includeprops text,
 excludeprops text
);

CREATE TABLE
IF NOT EXISTS downloads (
 id integer PRIMARY KEY,
 title text NOT NULL,
 episode text NOT NULL,
 release_id integer,
 FOREIGN KEY(release_id) REFERENCES releases(id)
);
