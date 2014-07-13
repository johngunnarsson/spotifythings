# -*- coding: utf-8 -*-
import sqlite3
import datetime
import functools
import logging

logger = logging.getLogger(__name__)

class SqliteStore(object):

    def __init__(self, database_file):
        self.database_file = database_file
        self.__migrations = []


    def __init_versioning(self):
        def create_table(connection):
            cursor = connection.cursor()

            # create table
            cursor.executescript("""create table if not exists version (
                Id INTEGER PRIMARY KEY,
                Migrated TEXT NOT NULL)""")

        self._execute_transactional(create_table)

    def __get_last_migration_id(self):
        def select(connection):
            cursor = connection.cursor()
            cursor.execute("SELECT max(Id) as Id FROM version")
            row = cursor.fetchone()
            return row['Id'] if row else -1

        return self._execute_transactional(select)


    def _create_connection(self):
        return sqlite3.connect(self.database_file, isolation_level=None)

    def _execute_transactional(self, action):
        connection = self.__create_connection()

        with connection:
            try:
                connection.row_factory = sqlite3.Row
                return action(connection)
            except:
                connection.rollback()
                raise
            else:
                connection.commit()

    def add_migration(self, migration):
        self.__migrations.append(migration)

    def initialize(self):
        self.__init_versioning()


        def execute_migration(migration, migration_id, connection):
            # execute migration
            migration(connection)

            # mark migration done
            cursor = connection.cursor()
            cursor.execute("INSERT INTO version (Id, Migrated) VALUES (?, ?)", (migration_id, datetime.datetime.now()))

        last_migration_id = self.__get_last_migration_id()

        for migration_id, migration in enumerate(self.__migrations):
            # check if migration need to be applied
            if migration_id > last_migration_id:
                logger.info('Applying migraion: {0}'.format(migration_id))

                # migration not applied
                # create partial function executing both migration itself and marking it applied
                apply_migration = functools.partial(execute_migration, migration, migration_id)

                # execute it transactional
                self._execute_transactional(apply_migration)