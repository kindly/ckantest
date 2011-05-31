from datetime import datetime
"""SQLAlchemy Metadata and Session object"""
from sqlalchemy import MetaData, __version__ as sqav
from sqlalchemy.orm import scoped_session, sessionmaker
import sqlalchemy.orm as orm
from sqlalchemy.orm.session import SessionExtension

# TODO: remove these imports from here and put them in client model modules
from sqlalchemy import Column, MetaData, Table, types, ForeignKey
from sqlalchemy import or_, and_
from sqlalchemy.types import *
from sqlalchemy.orm import scoped_session, sessionmaker, create_session
from sqlalchemy.orm import relation, backref

from ckan.model import extension

class CkanSessionExtension(SessionExtension):

    def before_flush(self, session, flush_context, instances):
        if not hasattr(session, '_object_cache'):
            session._object_cache= {'new': set(),
                                    'deleted': set(),
                                    'changed': set()}

        changed = [obj for obj in session.dirty if 
            session.is_modified(obj, include_collections=False)]

        session._object_cache['new'].update(session.new)
        session._object_cache['deleted'].update(session.deleted)
        session._object_cache['changed'].update(changed)


    def before_commit(self, session):
        session.flush()
        try:
            obj_cache = session._object_cache
            revision = session.revision
        except AttributeError:
            return

        new = obj_cache['new']
        changed = obj_cache['changed']
        deleted = obj_cache['deleted']

        for obj in new | changed | deleted:
            if not hasattr(obj, '__revision_class__'):
                continue

            if 'pending' not in obj.state:
                revision.approved_timestamp = datetime.now()

            revision_cls = obj.__revision_class__
            q = session.query(revision_cls)
            q = q.filter_by(expired_timestamp='9999-12-31', id=obj.id)
            if 'pending' in obj.state:
                q = q.filter(revision_cls.state.in_(
                    'pending-active', 'pending-deleted'))
                revision.state = 'pending'
            results = q.all()

            for rev_obj in results:
                if rev_obj.revision_id == revision.id:
                    rev_obj.revision_timestamp = revision.timestamp
                else:
                    rev_obj.expired_id = revision.id
                    rev_obj.expired_timestamp = revision.timestamp
                session.add(rev_obj)

    def after_commit(self, session):
        if hasattr(session, '_object_cache'):
            del session._object_cache

    def after_rollback(self, session):
        if hasattr(session, '_object_cache'):
            del session._object_cache

# __all__ = ['Session', 'engine', 'metadata', 'mapper']

# SQLAlchemy database engine. Updated by model.init_model()
engine = None

if sqav.startswith("0.4"):
    # SQLAlchemy session manager. Updated by model.init_model()
    Session = scoped_session(sessionmaker(
        autoflush=False,
        transactional=True,
        extension=[CkanSessionExtension(),
                   extension.PluginSessionExtension()],
        ))
else:
    Session = scoped_session(sessionmaker(
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        extension=[CkanSessionExtension(),
                   extension.PluginSessionExtension()],
        ))

#mapper = Session.mapper
mapper = orm.mapper

# Global metadata. If you have multiple databases with overlapping table
# names, you'll need a metadata for each database
metadata = MetaData()

