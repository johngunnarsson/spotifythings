import sqlite3
from sqlitestore import SqliteStore


class TagModel(object):

    def __init__(self, id, rfidtag, spotifylink, linktype, imageid, name):
        self.id = id
        self.rfidtag = rfidtag
        self.spotifylink = spotifylink
        self.linktype = linktype
        self.imageid = imageid
        self.name = name


class PersistentStore(SqliteStore):
    # db migrations
    def __init_migrations(self):
        def migration_0(connection):
            cursor = connection.cursor()
            cursor.executescript("""create table tagmapping (
                Id INTEGER PRIMARY KEY AUTOINCREMENT,
                RfidTag TEXT NOT NULL,
                SpotifyLink TEXT NOT NULL,
                LinkType INTEGER NOT NULL,
                ImageId TEXT,
                Name TEXT NOT NULL)""")

            cursor.executescript("""CREATE UNIQUE INDEX RfidTag_UNIQUE ON tagmapping (RfidTag ASC)""");

        def migration_1(connection):
            cursor = connection.cursor()
            cursor.executescript("""create table config (
                Id TEXT NOT NULL PRIMARY KEY,
                Value TEXT)""")

        self.add_migration(migration_0)
        self.add_migration(migration_1)

    def __init__(self, database_file):
        super(PersistentStore, self).__init__(database_file)
        self.__init_migrations()

    def _create_connection(self):
        return sqlite3.connect(self.database_file, isolation_level=None)

    def _execute_transactional(self, action):
        connection = self._create_connection()

        with connection:
            try:
                connection.row_factory = sqlite3.Row
                return action(connection)
            except:
                connection.rollback()
                raise
            else:
                connection.commit()

    def _to_tagmodel(self, row):
        return TagModel(row['Id'], row['RfidTag'], row['SpotifyLink'], row['LinkType'], row['ImageId'], row['Name'])


    def find_all_tags(self):
        def select(connection):
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM tagmapping")
            return [self._to_tagmodel(row) for row in cursor.fetchall()]

        return self._execute_transactional(select)

    def find_by_tagid(self, rfid_tag):
        def select(connection):
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM tagmapping where RfidTag = ?", [rfid_tag])

            row = cursor.fetchone()
            if row is None:
                return None

            return self._to_tagmodel(row)

        return self._execute_transactional(select)


    def find_tags_by_link(self, spotifylink):
        def select(connection):
            cursor = connection.cursor()
            cursor.execute("SELECT RfidTag FROM tagmapping where SpotifyLink = ?", [spotifylink])
            return [row['RfidTag'] for row in cursor.fetchall()]

        return self._execute_transactional(select)



    def add_tag(self, rfid_tag, spotifylink, linktype, imageid, name):
        def insert(connection):
            cursor = connection.cursor()
            cursor.execute("INSERT INTO tagmapping (RfidTag, SpotifyLink, LinkType, ImageId, Name) VALUES (?, ?, ?, ?, ?)", (rfid_tag, spotifylink, linktype, imageid, name))

            return cursor.lastrowid

        return self._execute_transactional(insert)

    def update_tag(self, rfid_tag, spotifylink, linktype, imageid, name):
        def update(connection):
            cursor = connection.cursor()
            cursor.execute("UPDATE tagmapping SET SpotifyLink = ?, LinkType = ?, ImageId = ?, Name = ? WHERE RfidTag = ?", (spotifylink, linktype, imageid, name, rfid_tag))

            return cursor.rowcount

        return self._execute_transactional(update)

    def delete_tag(self, rfid_tag):
        def delete(connection):
            cursor = connection.cursor()
            cursor.execute("DELETE FROM tagmapping WHERE RfidTag = ?", [rfid_tag])

            return cursor.rowcount

        return self._execute_transactional(delete)

    def set_config(self, key, value):
        def upsert(connection):
            cursor = connection.cursor()
            cursor.execute("INSERT OR REPLACE INTO Config (Id, Value) VALUES (?, ?)", [key, value])

        self._execute_transactional(upsert)

    def get_config(self, key, default_value = None):
        def select(connection):
            cursor = connection.cursor()
            cursor.execute("SELECT Value FROM Config where Id = ?", [key])

            row = cursor.fetchone()
            return row['Value'] if row else None

        value = self._execute_transactional(select)

        return value or default_value

    def delete_configs(self, keys):
        def delete(connection):
            cursor = connection.cursor()
            cursor.execute("DELETE FROM Config where Id in ({0})".format(','.join('?'*len(keys))), keys)

        self._execute_transactional(delete)











