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


CREATE TABLE user_group (
	id text NOT NULL,
	name text NOT NULL,
	parent_id text
);

CREATE TABLE user_group_extra (
	id text NOT NULL,
	user_group_id text NOT NULL,
	"key" text NOT NULL,
	"value" text NOT NULL
);

CREATE TABLE user_group_package (
	id text NOT NULL,
	user_group_id text NOT NULL,
	package_id text NOT NULL,
	capacity text
);

CREATE TABLE user_group_user (
	id text NOT NULL,
	user_group_id text NOT NULL,
	user_id text NOT NULL,
	capacity text
);

ALTER TABLE authorization_override
	ADD CONSTRAINT authorization_override_pkey PRIMARY KEY (id);

ALTER TABLE user_group
	ADD CONSTRAINT user_group_pkey PRIMARY KEY (id);

ALTER TABLE user_group_extra
	ADD CONSTRAINT user_group_extra_pkey PRIMARY KEY (id);

ALTER TABLE user_group_package
	ADD CONSTRAINT user_group_package_pkey PRIMARY KEY (id);

ALTER TABLE user_group_user
	ADD CONSTRAINT user_group_user_pkey PRIMARY KEY (id);

ALTER TABLE authorization_override
	ADD CONSTRAINT authorization_override_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id);

ALTER TABLE user_group_extra
	ADD CONSTRAINT user_group_extra_user_group_id_fkey FOREIGN KEY (user_group_id) REFERENCES user_group(id);

ALTER TABLE user_group_package
	ADD CONSTRAINT user_group_package_package_id_fkey FOREIGN KEY (package_id) REFERENCES package(id);

ALTER TABLE user_group_package
	ADD CONSTRAINT user_group_package_user_group_id_fkey FOREIGN KEY (user_group_id) REFERENCES user_group(id);

ALTER TABLE user_group_user
	ADD CONSTRAINT user_group_user_user_group_id_fkey FOREIGN KEY (user_group_id) REFERENCES user_group(id);

ALTER TABLE user_group_user
	ADD CONSTRAINT user_group_user_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id);

COMMIT;
''')
