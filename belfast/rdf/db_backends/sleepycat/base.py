import logging
import glob
import os
from bsddb3.db import DBRunRecoveryError, DBPageNotFoundError
import rdflib
from rdflib.store import NO_STORE, VALID_STORE
from django.conf import settings

from djangotoolbox.db.base import NonrelDatabaseFeatures, \
    NonrelDatabaseOperations, NonrelDatabaseWrapper, NonrelDatabaseClient, \
    NonrelDatabaseValidation, NonrelDatabaseIntrospection, \
    NonrelDatabaseCreation

logger = logging.getLogger(__name__)


## NOTE: this is a *bare-minimum* backend, not intended for use with django
# models, but only to allow accessing the database connection and allow django
# to close the database connection automaticcaly


class DatabaseCreation(NonrelDatabaseCreation):
    pass


class DatabaseFeatures(NonrelDatabaseFeatures):
    can_return_id_from_insert = False
    supports_primary_key_on = set()


class DatabaseOperations(NonrelDatabaseOperations):
    compiler_module = __name__.rsplit('.', 1)[0] + '.compiler'


class DatabaseClient(NonrelDatabaseClient):
    pass


class DatabaseValidation(NonrelDatabaseValidation):
    pass


class DatabaseIntrospection(NonrelDatabaseIntrospection):

    # minimal instrospection to allow django to run tests
    def get_table_list(self, *args, **kwargs):
        return []


class DatabaseWrapper(NonrelDatabaseWrapper):
    def __init__(self, *args, **kwds):
        super(DatabaseWrapper, self).__init__(*args, **kwds)
        self.features = DatabaseFeatures(self)
        self.ops = DatabaseOperations(self)
        self.client = DatabaseClient(self)
        self.creation = DatabaseCreation(self)
        self.validation = DatabaseValidation(self)
        self.introspection = DatabaseIntrospection(self)

        logger.debug('opening Sleepycat RDF DB connection')
        self.db_connection = rdflib.ConjunctiveGraph('Sleepycat')
        try:
            rval = self.db_connection.open(self.settings_dict['NAME'],
                                           create=False)
        except (MemoryError, DBRunRecoveryError, DBPageNotFoundError):
            logger.warn('Sleepycat RDF DB Error; clearing __db.00x files')
            # if we got far enough to open the store, close it
            if self.db_connection.store.is_open():
                self.db_connection.close()
            # this is a hack...
            # Under apache/django the rdf db doesn't get closed and we
            # eventually run out of db sessions (or something like that).
            # Removing the __db.00x files clears the sessions and makes
            # it possible to re-open a connection without losing any
            # of the RDF data.
            db_session_files = glob.glob(os.path.join(self.settings_dict['NAME'], '__db.00?'))
            for dbfile in db_session_files:
                os.remove(dbfile)
            # re-open the db, which should create new __db.00x files
            rval = self.db_connection.open(self.settings_dict['NAME'], create=False)

        if rval == NO_STORE:
            # if store doesn't exist yet, go ahead and create it
            logger.debug('Sleepycat RDF DB does not yet exist, creating it')
            self.db_connection.open(self.settings_dict['NAME'], create=True)

        elif rval != VALID_STORE:
            logger.error('Sleepycat RDF DB is not valid')

    def close(self):
        logger.debug('RDF DB wrapper close requested')
        # when running unit tests, django seems to close the db
        # connection before we expect
        # (but never seems to close it under apache!)
        # belfast rdf testutil plugin sets this variable for testing.
        if getattr(settings, 'RDF_DATABASE_TESTMODE', False):
            logger.debug('RDF DB testmode, not closing Sleepycat RDF DB connection')
            return
        if self.db_connection.store.is_open():
            logger.debug('closing Sleepycat RDF DB connection')
            self.db_connection.close()