import sqlalchemy.orm

from ckan.lib.base import *
from ckan.controllers.rest import BaseRestController
from ckan.lib.helpers import json
import ckan.model as model
import ckan.forms
from ckan.lib.search import query_for, QueryOptions
import ckan.authz
import ckan.rating

class Rest2Controller(BaseRestController):

    api_version = '2'
    ref_package_by = 'id'
    ref_group_by = 'id'

