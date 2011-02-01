import schemaish
from validatish.validator import URL
from validatish.validator import Required
from validatish.validator import All
from validatish.validator import Invalid
import transformer
from ckan.model import HarvestSource


class Unique():
    def __init__(self, key=id):
        self.key = key

    def __call__(self, v):
        qfilter = {self.key: v}
        count = HarvestSource.filter(**qfilter).count()
        if count > 0:
            msg = "must be unique"
            raise Invalid(msg)


harvesting_schema = schemaish.Structure()

harvesting_schema.add('url',
           schemaish.String(
               validator=All(URL(absolute=False,
                                 relative=False),
                             Required(),
                             Unique(key='url'))
               )
           )
harvesting_schema.add('description',
           schemaish.String(
               validator=Required())
           )

transformer.schema_registry['harvest_source'] = harvesting_schema
