import formalchemy
import ckan.model as model

def group_name_validator(val):
    name_validator(val)
    if model.Group.by_name(val):
        raise formalchemy.ValidationError('Group name already exists in database')

class GroupFieldSet(formalchemy.FieldSet):
    def __init__(self):
        formalchemy.FieldSet.__init__(self, model.Group)

    def validate_on_edit(self, orig_group_name, record_id):
        # If not changing name, don't validate this field (it will think it
        # is not unique because name already exists in db). So change it
        # temporarily to something that will always validate ok.
        temp_name = None
        if self.name.value == orig_group_name:
            temp_name = orig_group_name
            self.data['Group-%s-name' % record_id] = u'something_unique'
        validation = self.validate()
        if temp_name:
            # restore it
            self.data['Group-%s-name' % record_id] = temp_name
        return validation

group_fs = GroupFieldSet()
group_fs.configure(options=[
                    group_fs.name.label('Name (required)').validate(group_name_validator),
                    ],
                   exclude=[group_fs.id,
                            group_fs.packages,
                            group_fs.roles,
                            ])