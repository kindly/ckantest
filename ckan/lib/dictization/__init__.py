import datetime
from sqlalchemy.orm import class_mapper
import sqlalchemy
from pylons import config

# NOTE   
# The functions in this file contain very generic methods for dictizing objects
# and saving dictized objects. If a specialised use is needed please do NOT extend
# these functions.  Copy code from here as needed.


def table_dictize(obj, context):
    '''Get any model object and represent it as a dict'''

    result_dict = {}

    model = context["model"]
    session = context["session"]

    ModelClass = obj.__class__
    table = class_mapper(ModelClass).mapped_table

    fields = [field.name for field in table.c]

    for field in fields:
        name = field
        value = getattr(obj, name)
        if value is None:
            result_dict[name] = value
        elif isinstance(value, dict):
            result_dict[name] = value
        elif isinstance(value, int):
            result_dict[name] = value
        elif isinstance(value, datetime.datetime):
            result_dict[name] = value.isoformat()
        else:
            result_dict[name] = unicode(value)

    return result_dict


def obj_list_dictize(obj_list, context, sort_key=lambda x:x):
    '''Get a list of model object and represent it as a list of dicts'''

    result_list = []

    for obj in obj_list:
        result_list.append(table_dictize(obj, context))

    return sorted(result_list, key=sort_key)

def obj_dict_dictize(obj_dict, context, sort_key=lambda x:x):
    '''Get a dict whose values are model objects 
    and represent it as a list of dicts'''

    result_list = []

    for key, obj in obj_dict.items():
        result_list.append(table_dictize(obj, context))

    return sorted(result_list, key=sort_key)


def get_unique_constraints(table, context):
    '''Get a list of unique constraints for a sqlalchemy table'''

    list_of_constraints = []

    for contraint in table.constraints:
        if isinstance(contraint, sqlalchemy.UniqueConstraint):
            columns = [column.name for column in contraint.columns]
            list_of_constraints.append(columns)

    return list_of_constraints

def table_dict_save(table_dict, ModelClass, context):
    '''Given a dict and a model class update or create a sqlalchemy object.
    This will use an existing object if "id" is supplied OR if any unique 
    constraints are met. e.g supplying just a tag name will get out that tag obj.
    '''

    model = context["model"]
    session = context["session"]

    table = class_mapper(ModelClass).mapped_table

    obj = None

    unique_constriants = get_unique_constraints(table, context)

    id = table_dict.get("id")
    
    if id:
        obj = session.query(ModelClass).get(id)

    if not obj:
        unique_constriants = get_unique_constraints(table, context)
        for constraint in unique_constriants:
            params = dict((key, table_dict[key]) for key in constraint)
            obj = session.query(ModelClass).filter_by(**params).first()
            if obj:
                break

    if not obj:
        obj = ModelClass()

    for key, value in table_dict.iteritems():
        if isinstance(value, list):
            continue
        setattr(obj, key, value)

    session.add(obj)

    return obj
