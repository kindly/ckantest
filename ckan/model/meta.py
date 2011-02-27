"""SQLAlchemy Metadata and Session object"""
from sqlalchemy import MetaData, __version__ as sqav
from sqlalchemy.orm import scoped_session, sessionmaker
import sqlalchemy.orm as orm

# TODO: remove these imports from here and put them in client model modules
from sqlalchemy import Column, MetaData, Table, types, ForeignKey
from sqlalchemy import or_, and_
from sqlalchemy.types import *
from sqlalchemy.orm import scoped_session, sessionmaker, create_session, SessionExtension
from sqlalchemy.orm import relation, backref

from ckan.model import extension

# __all__ = ['Session', 'engine', 'metadata', 'mapper']

# SQLAlchemy database engine. Updated by model.init_model()
engine = None


class DeleteEmptyRevision(SessionExtension):

    def before_commit(self, session):
        revision = getattr(session, 'revision', None)
        if revision:
            session.flush()
            if not getattr(session, "object_revisioned", False):
                session.delete(revision)
            #if not session.is_modified(revision) and not getattr(revision, "_changed", False):
            #    session.delete(revision)


if sqav.startswith("0.4"):
    # SQLAlchemy session manager. Updated by model.init_model()
    Session = scoped_session(sessionmaker(
        autoflush=False,
        transactional=True,
        extension=[extension.PluginSessionExtension(), DeleteEmptyRevision()],
        ))
else:
    Session = scoped_session(sessionmaker(
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        extension=[extension.PluginSessionExtension(), DeleteEmptyRevision()],
        ))

#mapper = Session.mapper
mapper = orm.mapper

# Global metadata. If you have multiple databases with overlapping table
# names, you'll need a metadata for each database
metadata = MetaData()

