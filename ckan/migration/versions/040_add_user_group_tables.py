from migrate import *

def upgrade(migrate_engine):
    migrate_engine.execute('''
CREATE TABLE "member" (
    id text NOT NULL,
    user_id text,
    group_id text,
    capacity text
);

ALTER TABLE "group"
    ADD COLUMN parent_id text;

ALTER TABLE group_revision
    ADD COLUMN parent_id text;

ALTER TABLE package_group
    ADD COLUMN capacity text,
    ADD COLUMN type text;

ALTER TABLE package_group_revision
    ADD COLUMN capacity text,
    ADD COLUMN type text;

ALTER TABLE "member"
    ADD CONSTRAINT member_pkey PRIMARY KEY (id);

ALTER TABLE "member"
    ADD CONSTRAINT member_group_id_fkey FOREIGN KEY (group_id) REFERENCES "group"(id);

ALTER TABLE "member"
    ADD CONSTRAINT member_user_id_fkey FOREIGN KEY (user_id) REFERENCES "user"(id);
''')
