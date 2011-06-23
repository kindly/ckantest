from migrate import *

def upgrade(migrate_engine):

    migrate_engine.execute('''

--to drop
--DROP TABLE authorization_group;
--DROP TABLE authorization_group_role;
--DROP TABLE authorization_group_user;
--DROP TABLE user_object_role;
--DROP TABLE group_role;
--DROP TABLE package_role;
--DROP TABLE system_role;
BEGIN;

alter table "user" add column sysadmin bool;
update "user" set sysadmin = (select true from user_object_role where context = 'System' and role = 'admin' and user_object_role.user_id = "user".id);

alter table group_role drop constraint group_role_group_id_fkey;
alter table package_role drop constraint package_role_package_id_fkey;
alter table user_object_role drop constraint  user_object_role_authorized_group_id_fkey;
alter table user_object_role drop constraint  user_object_role_user_id_fkey;

CREATE TABLE authorization_override (
	id text NOT NULL,
	user_id text,
	object_id text NOT NULL,
	object_type text NOT NULL,
	"role" text
);

insert into authorization_override 
select 
    user_object_role.id,
    user_object_role.user_id,
    package_id, 
    'package', 
    user_object_role.role 
from
    user_object_role
join
    package_role on package_role.user_object_role_id = user_object_role.id;

insert into authorization_override 
select 
    user_object_role.id,
    user_object_role.user_id,
    group_id, 
    'group', 
    user_object_role.role 
from
    user_object_role
join
    group_role on group_role.user_object_role_id = user_object_role.id;

ALTER TABLE authorization_override
	ADD CONSTRAINT authorization_override_pkey PRIMARY KEY (id);

ALTER TABLE authorization_override
	ADD CONSTRAINT authorization_override_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id);

COMMIT;
'''
)
